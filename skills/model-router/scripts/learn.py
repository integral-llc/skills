#!/usr/bin/env python3
"""Learn which exact model each alias resolves to, from Claude Code's own logs.

Every subagent leaves `subagents/agent-*.meta.json` (the `model` it was
started with, as the hook stamped it) next to `agent-*.jsonl` (each answer's
`message.model` and the Claude Code `version`). Pairing the two gives the
alias -> id resolution as observed, so a new model version is picked up
after a few subagents run on it, with no registry edit. See replay() for the
rule that keeps a stray answer or an older Claude Code build from moving it.

Usage:
    learn.py            # incremental: logs changed since the last scan
    learn.py --full     # rescan every subagent log
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import time

from models import BY_ALIAS, LEARNED_PATH, STATE_DIR, TIERS, base_id, learned, resolved_id, tier_of, version_of

PROJECTS_GLOB = os.path.join(os.path.expanduser("~"), ".claude", "projects", "*", "*", "subagents", "agent-*.jsonl")
# Only the head of a log is read: the first answer names the model.
HEAD_LINES = 400
# Consecutive same-family runs that must agree before an alias is re-pointed.
CONFIRMATIONS = 3
# Replay starts from the seed, so history must reach back past every flip.
HISTORY_PER_ALIAS = 500
# Bumped when the learning rule changes; a state from an older rule is rebuilt.
RULES_VERSION = 3
LEARNING_KEYS = ("aliases", "history", "held", "scanned_until", "rules")


def installed_claude_code() -> str:
    """Version of the `claude` on PATH, from its versioned install path."""
    found = shutil.which("claude")
    if not found:
        return ""
    name = os.path.basename(os.path.realpath(found))
    return name if name[:1].isdigit() else ""


def first_answer(log_path: str) -> dict | None:
    """(model, version, timestamp) of the first real API answer in a log."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            for _, line in zip(range(HEAD_LINES), fh):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                model = (record.get("message") or {}).get("model") or ""
                if record.get("type") == "assistant" and model and not model.startswith("<"):
                    return {"id": model, "claude_code": record.get("version") or "",
                            "seen": record.get("timestamp") or ""}
    except OSError:
        return None
    return None


def requested_alias(log_path: str) -> str | None:
    meta_path = log_path[: -len(".jsonl")] + ".meta.json"
    try:
        with open(meta_path, encoding="utf-8") as fh:
            alias = (json.load(fh) or {}).get("model")
    except (OSError, ValueError):
        return None
    # A full id or "inherit" says nothing about what an alias resolves to.
    return alias if alias in TIERS else None


def observe(since: float) -> list[tuple[str, dict]]:
    """Every (alias, first answer) among logs modified after `since`."""
    found = []
    for log_path in glob.glob(PROJECTS_GLOB):
        try:
            # The log, not meta.json: a running subagent has no answer yet,
            # and its log's mtime moves again once it does.
            if os.path.getmtime(log_path) <= since:
                continue
        except OSError:
            continue
        alias = requested_alias(log_path)
        answer = first_answer(log_path) if alias else None
        if answer:
            found.append((alias, {**answer, "log": os.path.basename(log_path)}))
    return found


def merge(history: list[dict], new: list[dict]) -> list[dict]:
    """History ordered by answer time, one entry per log, newest kept last."""
    by_log = {entry["log"]: entry for entry in history}
    by_log.update({entry["log"]: entry for entry in new})
    return sorted(by_log.values(), key=lambda e: e["seen"])[-HISTORY_PER_ALIAS:]


def cc_version(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in (text or "").split("."))
    except ValueError:
        return ()


def replay(alias: str, history: list[dict], seed: str) -> tuple[str, str | None]:
    """(resolved id, reason a newer answer was held back) for one alias.

    Aliases resolve per Claude Code build: `opus` answered as claude-opus-5
    on 2.1.278 and claude-opus-5-5 on 2.1.280, and an older build left running
    in another terminal keeps producing the old id. So only answers from the
    newest build seen count. Within it, history is replayed from the seed and
    the alias moves only when CONFIRMATIONS consecutive same-family answers
    agree on an id that is not older than the current one. The result is the
    same whether it is computed incrementally or rebuilt from scratch."""
    family = [e for e in history if tier_of(e["id"]) == alias]
    if not family:
        return seed, None
    newest = max(cc_version(e["claude_code"]) for e in family)
    runs = [e for e in family if cc_version(e["claude_code"]) == newest]
    current = seed
    for i, entry in enumerate(runs):
        window = runs[max(0, i - CONFIRMATIONS + 1): i + 1]
        agreeing = len(window) == CONFIRMATIONS and len({base_id(e["id"]) for e in window}) == 1
        if agreeing and base_id(entry["id"]) != base_id(current) and not is_older(entry["id"], current):
            current = entry["id"]
    return current, held_reason(alias, runs, current)


def is_older(candidate: str, current: str) -> bool:
    new, old = version_of(candidate), version_of(current)
    return new is not None and old is not None and new < old


def held_reason(alias: str, runs: list[dict], current: str) -> str | None:
    latest = runs[-1]["id"]
    if base_id(latest) == base_id(current):
        return None
    streak = 0
    for entry in reversed(runs):
        if base_id(entry["id"]) != base_id(latest):
            break
        streak += 1
    build = runs[-1]["claude_code"]
    if is_older(latest, current):
        return (f"{alias} answered as older {latest} in {streak} runs on Claude Code {build}; kept {current}. "
                "Pin it with the env override if intended")
    return f"{alias} answered as {latest} ({streak}/{CONFIRMATIONS} runs on Claude Code {build}); still {current}"


def learn(full: bool = False) -> list[tuple[str, str, str]]:
    """Fold new observations into the learned state.

    Returns (alias, previous id, new id) for every alias whose resolution
    differs from before the call. `full` rebuilds the learning from every log,
    so a state written under an older rule is recomputed rather than trusted."""
    prior = learned()
    kept = {k: v for k, v in prior.items() if k not in LEARNING_KEYS}
    base = kept if full else prior
    started = time.time()
    since = 0.0 if full else float(base.get("scanned_until") or 0.0)
    histories = {a: list(h) for a, h in (base.get("history") or {}).items()}
    for alias, answer in observe(since):
        histories[alias] = merge(histories.get(alias, []), [answer])

    aliases: dict[str, dict] = {}
    held: dict[str, str] = {}
    for alias, history in histories.items():
        if alias not in BY_ALIAS:
            continue
        current, reason = replay(alias, history, BY_ALIAS[alias].seed_id)
        if reason:
            held[alias] = reason
        match = [e for e in history if base_id(e["id"]) == base_id(current)]
        if match:
            aliases[alias] = {k: match[-1][k] for k in ("id", "claude_code", "seen")}

    state = {**kept, "aliases": aliases, "history": histories, "held": held,
             "scanned_until": started, "rules": RULES_VERSION}
    save(state)
    return [(a, resolved_id(a, prior), resolved_id(a, state)) for a in TIERS
            if resolved_id(a, prior) != resolved_id(a, state)]


def save(state: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = f"{LEARNED_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    # Atomic swap: two sessions starting together must not leave half a file.
    os.replace(tmp, LEARNED_PATH)


def learn_current() -> list[tuple[str, str, str]]:
    """Incremental learn, or a full rebuild when the state predates RULES_VERSION."""
    return learn(full=learned().get("rules") != RULES_VERSION)


def main(argv: list[str]) -> int:
    changes = learn(full="--full" in argv) if "--full" in argv else learn_current()
    for alias, old, new in changes:
        print(f"{alias}: {old} -> {new}")
    state = learned()
    for reason in (state.get("held") or {}).values():
        print(f"held: {reason}")
    for alias in TIERS:
        entry = (state.get("aliases") or {}).get(alias)
        source = f"observed {entry['seen']} on Claude Code {entry['claude_code']}" if entry else "seed, not yet observed"
        print(f"  {alias:<7} {resolved_id(alias, state):<28} {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
