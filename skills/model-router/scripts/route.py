#!/usr/bin/env python3
"""Route a task to a Claude tier (haiku / sonnet / opus / fable) using Jev.

Jev (TypeSafe System One) is a calibrated classifier, not an LLM: it answers
typed questions about the task text and returns probabilities. Code owns the
policy. When Jev is unreachable (no key, offline, 5xx) a keyword heuristic
takes over so the caller always gets an answer, tagged with its source.

Usage:
    route.py "task text" [--context "extra facts"] [--json]

The Claude Code hooks live in hooks.py; the on/off flag in router_state.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from models import TIERS, describe, display_name, resolved_id


def _named(alias: str) -> str:
    # Jev sees the model behind each tier, not just the alias.
    return display_name(resolved_id(alias))


API_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai") + "/v1/systemone"
MODEL = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
KEYCHAIN_SERVICE = "TYPESAFE_API_KEY"
DEFAULT_TIMEOUT_S = 4.0
# A 429 retry only makes sense with enough budget left for a second answer.
RETRY_BACKOFF_S = 1.0
MIN_RETRY_BUDGET_S = 1.5


def _timeout_from_env() -> float:
    # Parsed defensively: this runs at import time inside every hook, and a
    # typo in the env must degrade to the default, not crash the hook.
    try:
        value = float(os.environ.get("MODEL_ROUTER_TIMEOUT", DEFAULT_TIMEOUT_S))
    except ValueError:
        return DEFAULT_TIMEOUT_S
    return value if value > 0 else DEFAULT_TIMEOUT_S


# Wall-clock budget for the whole Jev exchange, retries included. It must stay
# well under the hook timeout in settings.json (15 s) or Claude Code kills the
# hook before the fallback can answer.
TIMEOUT_S = _timeout_from_env()

# Below this the argmax is not trusted: the mass is split between tiers, so
# take the highest tier that still holds real probability. Resolution only
# goes up: an underpowered model on a hard task costs more (rework, subtle
# bugs) than an overpowered model on an easy one.
LOW_CONFIDENCE = 0.5
PLAUSIBLE_MASS = 0.2
# Score levels are 0..3; this is the "wrong change ripples" zone.
HARD_COMPLEXITY = 2.5
# Probability that the change is cross-cutting.
CROSS_CUTTING = 0.7

QUESTIONS = {
    "tier": {
        "type": "choice",
        "instructions": (
            "Which Claude model tier is the cheapest one that can complete "
            "`task` correctly on the first attempt in a software codebase? "
            "Pick by the reasoning the work needs, not by how long it takes."
        ),
        "criteria": {
            "haiku": {
                "summary": f"{_named('haiku')}: mechanical or lookup work with no design judgment.",
                "examples": [
                    "find where a symbol, file, or string is defined or used",
                    "list, read, or summarize files; grep or glob sweeps",
                    "run a command and report its output",
                    "rename, reformat, fix a typo, add an import, bump a version",
                    "answer a factual question about a known file",
                ],
            },
            "sonnet": {
                "summary": f"{_named('sonnet')}: well-specified implementation inside a clear boundary.",
                "examples": [
                    "add a feature or fix a bug in one module with a clear spec",
                    "write unit tests for existing code",
                    "write or update documentation",
                    "small refactor within one or a few files",
                    "standard CRUD, endpoint, or component with known patterns",
                ],
            },
            "opus": {
                "summary": f"{_named('opus')}: judgment across modules; wrong changes ripple.",
                "examples": [
                    "multi-file refactor or API change with many call sites",
                    "debugging where the root cause is unknown",
                    "architecture or design decisions and trade-offs",
                    "security review, concurrency, data migrations",
                    "performance work that needs profiling and reasoning",
                ],
            },
            "fable": {
                "summary": f"{_named('fable')}: hardest; novel, ambiguous, or high-stakes with invariants to preserve.",
                "examples": [
                    "deep cross-cutting refactor where invariants must hold end to end",
                    "novel algorithm or data structure design with tight constraints",
                    "ambiguous requirements needing research and synthesis",
                    "high-stakes review where a miss is expensive",
                ],
            },
        },
    },
    "complexity": {
        "type": "score",
        "instructions": "How much reasoning does completing `task` correctly require?",
        "criteria": [
            "Mechanical: lookup, read, run, or a one-line edit with an obvious answer",
            "Contained: clear spec, one module, known patterns",
            "Cross-module: several files interact; needs tracing callers and side effects",
            "Deep: ambiguous, novel, or invariants to preserve across the system",
        ],
    },
    "cross_cutting": {
        "type": "noul",
        "instructions": "Would completing `task` change behavior in more than one module, or touch code with many callers?",
        "criteria": {
            "true": "Multiple modules, shared types, public APIs, or many call sites are affected",
            "false": "Read-only work, or changes stay inside one file or a narrow boundary",
        },
    },
}

# Coarse offline fallback. Highest matching tier wins. Stems carry \w* so
# "migration", "debugging" and "refactoring" match; short words take only
# inflections so "add" does not fire on "address".
FALLBACK_SIGNALS = {
    "fable": r"\b(?:invariant\w*|novel|from scratch|design(?:ing)? (?:an? )?(?:new )?(?:algorithm|protocol|data structure)s?"
             r"|prov(?:e|es|ing)|formal(?:ly)?|ambigu\w*|research\w* and)\b",
    "opus": r"\b(?:refactor\w*|architect\w*|migrat\w*|concurren\w*|race conditions?|races?|deadlock\w*|secur\w*"
            r"|audit\w*|root.?cause\w*|debug\w*|perf|performance|profil\w*|redesign\w*|across"
            r"|all (?:call ?sites|usages|modules|callers))\b",
    "sonnet": r"\b(?:implement\w*|add(?:s|ed|ing)?|fix(?:es|ed|ing)?|write (?:unit )?tests?|test coverage|document\w*"
              r"|docs?|endpoints?|components?|features?|bugs?)\b",
}


def escalate(tier: str, floor: str) -> str:
    return TIERS[max(TIERS.index(tier), TIERS.index(floor))]


def highest_plausible(probabilities: dict) -> str:
    plausible = [t for t in TIERS if probabilities.get(t, 0.0) >= PLAUSIBLE_MASS]
    return plausible[-1] if plausible else max(probabilities, key=probabilities.get)


def api_key() -> str:
    """Env first; the login Keychain covers sessions launched without zsh."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    try:
        found = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return found.stdout.strip() if found.returncode == 0 else ""


def _post_within(req: urllib.request.Request, budget: float) -> dict:
    """urlopen's timeout is per socket operation, so a server trickling bytes
    can hold it open indefinitely. A worker thread gives a hard wall clock."""
    box: dict = {}

    def worker() -> None:
        try:
            with urllib.request.urlopen(req, timeout=budget) as resp:
                box["value"] = json.load(resp)
        except BaseException as err:  # noqa: BLE001 - re-raised in the caller
            box["error"] = err

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(budget)
    if thread.is_alive():
        raise TimeoutError(f"no answer within {budget:.1f}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


def ask_jev(task: str, context: str | None) -> dict:
    key = api_key()
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY not in env or Keychain")
    state = {"task": task}
    if context:
        state["context"] = context
    body = json.dumps({"state": state, "model": MODEL, "questions": QUESTIONS}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    deadline = time.monotonic() + TIMEOUT_S
    last_err: Exception | None = None
    for attempt in range(2):
        budget = deadline - time.monotonic()
        if budget <= 0:
            break
        try:
            return _post_within(req, budget)
        except urllib.error.HTTPError as err:
            last_err = err
            retryable = err.code in (429, 529) and attempt == 0
            if not retryable or deadline - time.monotonic() < RETRY_BACKOFF_S + MIN_RETRY_BUDGET_S:
                raise
            time.sleep(RETRY_BACKOFF_S)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            last_err = err
            break
    raise RuntimeError(f"Jev unreachable: {last_err or 'time budget spent'}")


def apply_policy(answers: dict) -> dict:
    tier_ans = answers["tier"]
    complexity = answers["complexity"]
    cross = answers["cross_cutting"]["noul"]

    chosen = tier_ans["choice"]
    if chosen not in TIERS:
        raise ValueError(f"Jev answered unknown tier {chosen!r}")
    reasons: list[str] = []
    if tier_ans["confidence"] < LOW_CONFIDENCE:
        chosen = escalate(chosen, highest_plausible(tier_ans["probabilities"]))
        reasons.append(
            f"tier confidence {tier_ans['confidence']:.2f} < {LOW_CONFIDENCE}: "
            f"took highest tier with p >= {PLAUSIBLE_MASS}"
        )
    if complexity["score"] >= HARD_COMPLEXITY:
        chosen = escalate(chosen, "opus")
        reasons.append(f"complexity {complexity['score']:.2f} >= {HARD_COMPLEXITY}: floor opus")
    if cross >= CROSS_CUTTING:
        chosen = escalate(chosen, "opus")
        reasons.append(f"cross-cutting p={cross:.2f} >= {CROSS_CUTTING}: floor opus")

    return {
        "model": chosen,
        "source": "jev",
        "jev_choice": tier_ans["choice"],
        "confidence": round(tier_ans["confidence"], 3),
        "probabilities": {k: round(v, 3) for k, v in tier_ans["probabilities"].items()},
        "complexity": round(complexity["score"], 2),
        "cross_cutting": round(cross, 3),
        "adjustments": reasons,
    }


def fallback(task: str, error: str) -> dict:
    """Uncalibrated guess. Callers must not route below their own floor on it:
    the hooks lift it to the session tier or leave the Agent model unset."""
    lowered = task.lower()
    chosen = TIERS[0]
    for tier in TIERS[1:]:
        if re.search(FALLBACK_SIGNALS[tier], lowered):
            chosen = tier
    return {
        "model": chosen,
        "source": "fallback",
        "confidence": None,
        "error": error,
        "adjustments": [f"Jev unavailable ({error}); keyword heuristic used"],
    }


def route(task: str, context: str | None = None) -> dict:
    try:
        response = ask_jev(task, context)
        return apply_policy(response["answers"])
    except Exception as err:  # noqa: BLE001 - any failure must degrade, never block
        return fallback(task, str(err)[:120])


def summarize(result: dict) -> str:
    if result["source"] == "fallback":
        return f"model-router: {describe(result['model'])} (offline heuristic; {result['adjustments'][0]})"
    probs = ", ".join(f"{k} {v:.2f}" for k, v in result["probabilities"].items())
    line = (
        f"model-router: {describe(result['model'])} "
        f"(jev {result['jev_choice']} conf {result['confidence']:.2f}; "
        f"complexity {result['complexity']:.1f}/3; cross-cutting {result['cross_cutting']:.2f}; {probs})"
    )
    if result["adjustments"]:
        line += " | " + "; ".join(result["adjustments"])
    return line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", help="task text to route")
    parser.add_argument("--context", help="extra facts: call-site counts, file counts, constraints")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args()

    result = route(args.task, args.context)
    print(json.dumps(result, indent=2) if args.json else summarize(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
