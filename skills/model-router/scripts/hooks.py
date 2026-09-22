#!/usr/bin/env python3
"""Claude Code hooks for the model router. Every path exits 0: routing must
never block a prompt or a session.

    hooks.py --session   SessionStart: emit the router rules when the flag is on
    hooks.py --prompt    UserPromptSubmit: handle /model-router toggles, then
                         route the prompt through Jev when the flag is on
    hooks.py --pretool   PreToolUse (matcher Agent): route the delegation
                         prompt, fill `model` when omitted, print the verdict
"""

from __future__ import annotations

import json
import sys

from agent_defs import definition_tier
from learn import installed_claude_code, learn_current
from models import TIERS, describe, learned
from route import escalate, route, summarize
from router_state import is_active, parse_toggle, remember_session_model, session_tier, set_active, status_line

# "Task" is the Agent tool's former name; Claude Code still accepts both.
AGENT_TOOLS = ("Agent", "Task")

SESSION_RULES = """MODEL ROUTER ACTIVE (toggle: /model-router on|off|status|audit|doctor).
The session model is fixed for the whole session and is never switched; Jev
moves the work instead. Two hooks do the routing:
- UserPromptSubmit routes each prompt and tells you where the work goes:
  ESCALATE (tier above the session): hand the substantive work to one Agent
  (general-purpose or a fitting specialist) with a plain, complete prompt;
  you scope, verify the result, and report. Do not do the hard reasoning
  yourself. DELEGATE DOWN (tier below): do the reasoning yourself, hand
  lookups, sweeps, and clearly specified edits to Agents. SAME: do it
  yourself, delegating only what is naturally parallel.
- PreToolUse on Agent routes every delegation prompt and fills `model` when
  you leave it out. Omit `model` on Agent calls. Pass it only when the user
  named a tier; the hook keeps it and shows the disagreement.
Write delegation prompts that state the work plainly: Jev routes on that
text, and a hard task described vaguely gets a cheap model.
Never suggest /model; the user does not switch models by hand.
End every reply with one trailer line, plain text, last line of the message:
  models: <session model> (reply) · <tier> x<n> <agent type> ...
listing each subagent you ran this turn with the model the hook set. Omit
subagents when none ran. The trailer is self-reported; ground truth is
`/model-router audit`, which reads message.model from the transcripts.
Tiers: haiku = lookup/grep/read/run/rename; sonnet = one-module feature, tests,
docs; opus = multi-file refactor, unknown root cause, design, security,
concurrency; fable = invariants end to end, novel algorithms, ambiguous
research, high-stakes review. Full rules: model-router skill."""


def session_rules() -> str:
    # Resolved at session start: the ids are learned, not fixed in this file.
    cache = learned()
    resolved = "; ".join(describe(alias, cache) for alias in TIERS)
    return f"{SESSION_RULES}\nAliases resolve to: {resolved}. Pass only the alias as `model`."

def emit(context: str, event: str, system_message: str | None = None) -> None:
    payload: dict = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
    if system_message:
        # Shown to the user in the terminal; additionalContext is only seen by the model.
        payload["systemMessage"] = system_message
    print(json.dumps(payload))


def on_session() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    # Claude Code does not always include `model`; when it does, keep it per
    # session so the prompt hook can flag a mismatch with the routed tier.
    remember_session_model(payload.get("session_id") or "", payload.get("model") or "")
    if not is_active():
        return 0
    notes = registry_notes()
    emit(session_rules() + "".join(f"\n{n}" for n in notes), "SessionStart",
         system_message=" | ".join(notes) or None)
    return 0


def registry_notes() -> list[str]:
    """Alias moves learned since the last session, and a Claude Code update
    that doctor has not checked yet. Never raises: a failed scan is not news."""
    notes = []
    try:
        notes += [f"[ROUTER] {alias} now resolves to {new} (was {old})" for alias, old, new in learn_current()]
    except Exception:  # noqa: BLE001 - learning is best effort
        pass
    version = installed_claude_code()
    checked = learned().get("claude_code_checked")
    if version and checked != version:
        notes.append(f"[ROUTER] Claude Code {version} not yet checked "
                     f"(last {checked or 'never'}): run /model-router doctor")
    return notes


def on_prompt() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    prompt = (payload.get("prompt") or "").strip()
    # Subagent hand-backs arrive through the same hook. They are not user
    # input, so they must neither toggle the router nor be routed.
    if is_relayed(prompt):
        return 0

    toggle = parse_toggle(prompt)
    if toggle is not None:
        if toggle in ("on", "off"):
            set_active(toggle == "on")
        note = status_line()
        if toggle == "on":
            note += ". " + session_rules()
        elif toggle == "off":
            note += ". Stop running route.py, drop the models trailer; choose Agent models by your own judgment."
        emit(note, "UserPromptSubmit", system_message=status_line())
        return 0

    if not is_active():
        return 0
    # Slash commands, confirmations and one-word replies carry no task to route.
    if not prompt or prompt.startswith("/") or len(prompt.split()) < 4:
        return 0
    result = route(prompt)
    running = session_tier(payload.get("session_id") or "", payload.get("transcript_path") or "")
    routed = result["model"]
    if result["source"] == "fallback" and running in TIERS:
        # An uncalibrated keyword guess never sends work below the session tier.
        routed = escalate(routed, running)
    placement, note = place_work(routed, running)
    emit(summarize(result) + " | " + placement, "UserPromptSubmit",
         system_message=short_verdict(result) + note)
    return 0


def place_work(routed: str, running: str | None) -> tuple[str, str]:
    """Where the work goes relative to the fixed session model.

    Returns (instruction for the model, suffix for the user's grey line)."""
    if running is None or routed not in TIERS:
        return ("session model unknown; delegate by the tier table", "")
    gap = TIERS.index(routed) - TIERS.index(running)
    if gap > 0:
        return (
            f"ESCALATE: session is {running}, work needs {routed}. Hand the substantive "
            f"work to one Agent with a complete prompt (omit model; the hook sets {routed}). "
            "Scope, verify, report; do not do the hard reasoning yourself.",
            f" | escalating: session {running}, work goes to a {routed} agent",
        )
    if gap < 0:
        return (
            f"DELEGATE DOWN: session is {running}, work is {routed}-grade. Reason yourself; "
            "hand lookups, sweeps and clearly specified edits to Agents (omit model).",
            f" | session {running}; mechanical parts go to {routed} agents",
        )
    return (f"SAME tier as session ({running}): do it yourself; delegate only parallel work.", "")


def on_pretool() -> int:
    """PreToolUse on Agent: route the delegation prompt, fill `model` when the
    caller left it out, and show the verdict as a grey line per delegation."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") not in AGENT_TOOLS or not is_active():
        return 0
    tool_input = payload.get("tool_input") or {}
    prompt = (tool_input.get("prompt") or "").strip()
    if not prompt:
        return 0

    result = route(prompt)
    # An empty string is what a caller sends when it means "no preference".
    passed = (tool_input.get("model") or "").strip() or None
    label = tool_input.get("description") or tool_input.get("subagent_type") or "Agent"
    floor = definition_tier(tool_input.get("subagent_type") or "", payload.get("cwd") or "")
    decision = pretool_decision(result, passed, floor, label)

    output: dict = {
        "hookSpecificOutput": {"hookEventName": "PreToolUse"},
        "systemMessage": f"[ROUTER] {decision['message']}",
    }
    if decision["fill"]:
        # Fill the tier in the harness so routing does not depend on the model
        # remembering. "allow" is required for updatedInput to apply; deny and
        # ask rules in settings still override it.
        output["hookSpecificOutput"]["permissionDecision"] = "allow"
        output["hookSpecificOutput"]["updatedInput"] = {**tool_input, "model": decision["fill"]}
    print(json.dumps(output))
    return 0


def pretool_decision(result: dict, passed: str | None, floor: str | None, label: str) -> dict:
    """What to write into the Agent call and what to tell the user.

    `fill` is the tier to stamp, or None to leave the call untouched. Three
    things are never overridden downward: an explicit `model`, the `model:`
    pinned in the agent definition, and the agent default when Jev is down."""
    if result["source"] != "jev":
        reason = result.get("error") or "unavailable"
        return {"fill": None, "message": (
            f"offline ({reason}); heuristic {result['model']} not applied, "
            f"{passed or 'agent default'} -> {label}"
        )}

    routed = result["model"]
    target = escalate(routed, floor) if floor else routed
    raised = f", floor {floor} from definition" if target != routed else ""
    conf = fmt_conf(result)
    if passed is None:
        return {"fill": target, "message": f"{describe(target)} -> {label} (jev {routed}, conf {conf}{raised})"}
    if passed not in TIERS:
        return {"fill": None, "message": f"{target} suggested -> {label}, kept unknown model '{passed}' (jev)"}
    if passed == target:
        return {"fill": None, "message": f"{target} -> {label} (agrees, jev)"}
    # An explicit tier stays: the user may have named it. Show the disagreement.
    return {"fill": None, "message": f"{target} suggested -> {label}, kept {passed} (jev{raised})"}


def fmt_conf(result: dict) -> str:
    return "n/a" if result.get("confidence") is None else f"{result['confidence']:.2f}"


def is_relayed(prompt: str) -> bool:
    """Harness-injected text: subagent reports, task notifications, hand-backs."""
    head = prompt[:200]
    return (
        head.startswith("Another Claude session sent a message")
        or head.startswith("<agent-message")
        or head.startswith("[SYSTEM NOTIFICATION")
        or head.startswith("<task-notification>")
    )


def short_verdict(result: dict) -> str:
    """One line for the terminal: tier, confidence, and whether Jev answered."""
    if result["source"] == "fallback":
        return f"[ROUTER] {result['model']} (offline heuristic: {result.get('error') or 'Jev unavailable'})"
    return (
        f"[ROUTER] {result['model']} "
        f"(jev conf {result['confidence']:.2f}, complexity {result['complexity']:.1f}/3)"
    )


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    try:
        if mode == "--session":
            return on_session()
        if mode == "--prompt":
            return on_prompt()
        if mode == "--pretool":
            return on_pretool()
        print(__doc__.strip(), file=sys.stderr)
    except Exception:  # noqa: BLE001 - a broken hook must not break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
