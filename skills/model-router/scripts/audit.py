#!/usr/bin/env python3
"""Show which model actually produced each part of a Claude Code session.

Reads the transcript files Claude Code writes under ~/.claude/projects: the
main session log and, when present, one log per subagent. Every assistant
message records `message.model`, so this is ground truth rather than the
model's own claim.

Usage:
    audit.py                 # latest session for the current directory
    audit.py <session-id>    # a specific session
    audit.py --all           # every session for the current directory
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from models import TIERS, id_matches, learned, resolved_id

PROJECTS_DIR = Path.home() / ".claude" / "projects"


AGENT_TOOLS = ("Agent", "Task")
ROUTER_HOOK = "PreToolUse:Agent"


def project_dir(cwd: str) -> Path | None:
    """Transcript folder for cwd or its nearest ancestor that has one, so the
    audit still works after a `cd` into a subfolder of the session's root."""
    path = Path(cwd).resolve()
    for candidate in (path, *path.parents):
        # Claude Code names the project folder after the cwd, with every
        # separator and every dot or underscore flattened to a dash - so a repo
        # called "where2hit.com" lands in "...-where2hit-com".
        folder = PROJECTS_DIR / re.sub(r"[/._]", "-", str(candidate))
        if folder.is_dir():
            return folder
    return None


def records(transcript: Path):
    # One corrupt byte must not end the audit; the JSON parse drops the line.
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def models_in(transcript: Path) -> Counter:
    counts: Counter = Counter()
    for record in records(transcript):
        if record.get("type") != "assistant":
            continue
        model = (record.get("message") or {}).get("model")
        # "<synthetic>" marks harness-made messages, not an API response.
        if model and not model.startswith("<"):
            counts[model] += 1
    return counts


def agent_calls(transcript: Path) -> list[tuple[str, str, str, str]]:
    """(model param, subagent type, description, router verdict) per Agent call.

    The tool_use input in the transcript is what the model sent, before the
    PreToolUse hook rewrote it; the tier the hook stamped is only in the
    hook's own system message, matched back by tool-use id."""
    calls: list[tuple[str, dict]] = []
    verdicts: dict[str, str] = {}
    for record in records(transcript):
        attachment = record.get("attachment") or {}
        if attachment.get("type") == "hook_system_message" and attachment.get("hookName") == ROUTER_HOOK:
            verdicts[attachment.get("toolUseID") or ""] = attachment.get("content") or ""
            continue
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in AGENT_TOOLS:
                calls.append((block.get("id") or "", block.get("input") or {}))
    return [
        (
            args.get("model") or "default",
            args.get("subagent_type") or "-",
            args.get("description") or "",
            verdicts.get(tool_id, "no router line"),
        )
        for tool_id, args in calls
    ]


def fmt_counts(counts: Counter) -> str:
    return ", ".join(f"{model} x{n}" for model, n in counts.most_common()) or "no assistant messages"


def report(session_log: Path) -> None:
    session_id = session_log.stem
    print(f"session {session_id}")
    print(f"  main:      {fmt_counts(models_in(session_log))}")

    calls = agent_calls(session_log)
    if calls:
        print("  delegations (requested model, router verdict):")
        for model, agent_type, description, verdict in calls:
            print(f"    model={model:<8} {agent_type:<18} {description}")
            print(f"      {verdict}")

    subagent_dir = session_log.with_suffix("") / "subagents"
    logs = sorted(subagent_dir.glob("agent-*.jsonl")) if subagent_dir.is_dir() else []
    if not logs:
        print("  subagents: none")
        return
    print("  subagents ran on:")
    cache = learned()
    for log in logs:
        meta_path = log.with_suffix(".meta.json")
        meta = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        label = f"{meta.get('agentType', '-')}: {meta.get('description', log.stem)}"
        counts = models_in(log)
        print(f"    {fmt_counts(counts):<28} {label}{drift(meta.get('model'), counts, cache)}")


def drift(requested: str | None, counts: Counter, cache: dict) -> str:
    """Flag a subagent whose alias ran on something other than the id the
    registry expects: the sign that an alias moved to a new model."""
    if requested not in TIERS or not counts:
        return ""
    off = [model for model in counts if not id_matches(requested, model, cache)]
    if not off:
        return ""
    return f"  DRIFT: {requested} expected {resolved_id(requested, cache)}, ran {', '.join(off)}"


def main(argv: list[str]) -> int:
    folder = project_dir(os.getcwd())
    if folder is None:
        print(f"no transcripts for {os.getcwd()} under {PROJECTS_DIR}", file=sys.stderr)
        return 1
    logs = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print("no session logs found", file=sys.stderr)
        return 1

    if len(argv) > 1 and argv[1] == "--all":
        for log in logs:
            report(log)
            print()
        return 0
    if len(argv) > 1:
        wanted = folder / f"{argv[1]}.jsonl"
        if not wanted.is_file():
            print(f"no session {argv[1]}", file=sys.stderr)
            return 1
        report(wanted)
        return 0
    report(logs[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
