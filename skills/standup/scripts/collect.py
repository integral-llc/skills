#!/usr/bin/env python3
"""
Collect Claude Code conversation activity for the current project over a
date window. Output is condensed markdown intended for downstream synthesis
by Claude into a standup.

Resolves the project directory by encoding the current working directory
the way Claude Code does (slashes and spaces become dashes), with a
fallback that token-matches if the exact name is not found.

Usage:
    collect.py --yesterday
    collect.py --today
    collect.py --day 2026-04-30
    collect.py --from 2026-04-25 --to 2026-04-30
    collect.py --last 7

No external dependencies. Tested against Python 3.10+.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def encode_project_path(cwd: Path) -> str:
    """Mirror Claude Code's project directory naming."""
    s = str(cwd.resolve())
    # CC replaces / and spaces with -; some CC versions also strip @ and .
    encoded = s.replace("/", "-").replace(" ", "-")
    return encoded


def find_project_dir(cwd: Path) -> Path | None:
    """Locate ~/.claude/projects/<encoded> for the given cwd. Falls back to a
    token-prefix match if the exact name is absent."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None

    cwd_resolved = str(cwd.resolve())
    encoded = cwd_resolved.replace("/", "-").replace(" ", "-")

    # Try the obvious encodings first
    for variant in (encoded, encoded.lstrip("-"), "-" + encoded.lstrip("-")):
        candidate = base / variant
        if candidate.exists() and candidate.is_dir():
            return candidate

    # Fallback: walk subdirectories and find one whose name contains every
    # path token in order. Handles @, ., and other char rewrites.
    parts = [p for p in cwd_resolved.split("/") if p]
    if not parts:
        return None
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        idx = 0
        ok = True
        for part in parts:
            sanitized = re.sub(r"[^A-Za-z0-9-]", "-", part)
            pos = name.find(sanitized, idx)
            if pos < 0:
                ok = False
                break
            idx = pos + len(sanitized)
        if ok:
            return child
    return None


def parse_window(args) -> tuple[datetime, datetime, date]:
    """Return (start_utc, end_utc, effective_date)."""
    today = date.today()
    if args.day:
        d = datetime.strptime(args.day, "%Y-%m-%d").date()
        start, end, eff = d, d, d
    elif args.from_date and args.to_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.to_date, "%Y-%m-%d").date()
        eff = end
    elif args.last:
        end = today
        start = today - timedelta(days=args.last - 1)
        eff = end
    elif args.today:
        start = end = eff = today
    else:
        # Default: yesterday
        y = today - timedelta(days=1)
        start = end = eff = y

    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)
    return start_dt, end_dt, eff


# Tool calls compress to one line; we do not want full diffs in a standup
TOOL_COMPRESSORS = {
    "Bash": lambda inp: f"[bash] {(inp.get('command') or '')[:240]}",
    "Edit": lambda inp: f"[edit] {inp.get('file_path', '?')}",
    "MultiEdit": lambda inp: f"[multiedit] {inp.get('file_path', '?')}",
    "Write": lambda inp: f"[write] {inp.get('file_path', '?')}",
    "Read": lambda inp: f"[read] {inp.get('file_path', '?')}",
    "Glob": lambda inp: f"[glob] {inp.get('pattern', '?')}",
    "Grep": lambda inp: f"[grep] {inp.get('pattern', '?')}",
    "WebFetch": lambda inp: f"[fetch] {inp.get('url', '?')}",
    "WebSearch": lambda inp: f"[search] {inp.get('query', '?')}",
    "TodoWrite": lambda inp: f"[todos] {len(inp.get('todos', []))} items",
}


def extract_text(content) -> str:
    """Pull human-meaningful text out of a CC message content field. Tool
    use blocks compress to a single descriptive line."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = (block.get("text") or "").strip()
            if t:
                parts.append(t)
        elif btype == "tool_use":
            name = block.get("name", "?")
            inp = block.get("input") or {}
            compressor = TOOL_COMPRESSORS.get(name, lambda i: f"[{name}]")
            parts.append(compressor(inp))
        elif btype == "tool_result":
            # Skip tool results entirely; far too verbose for a standup
            continue
    return "\n".join(parts).strip()


def collect_sessions(project_dir: Path, start_dt: datetime, end_dt: datetime):
    """Walk every JSONL in project_dir, yield session dicts whose turns fall
    in [start_dt, end_dt]. Sessions with no qualifying turns are dropped."""
    sessions = []
    for jsonl_path in sorted(project_dir.glob("*.jsonl")):
        if jsonl_path.stat().st_size == 0:
            continue
        turns = []
        with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = obj.get("timestamp")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if ts < start_dt or ts > end_dt:
                    continue
                msg_type = obj.get("type")
                if msg_type not in ("user", "assistant"):
                    continue
                msg = obj.get("message") or {}
                role = msg.get("role", msg_type)
                content = msg.get("content")
                text = extract_text(content)
                if not text:
                    continue
                # Cap individual turn size to keep aggregate output sane
                if len(text) > 1800:
                    text = text[:1800] + " ...[truncated]"
                turns.append((role, text, ts))
        if turns:
            sessions.append({
                "session_id": jsonl_path.stem,
                "started": turns[0][2],
                "ended": turns[-1][2],
                "turns": turns,
            })
    sessions.sort(key=lambda s: s["started"])
    return sessions


def render(sessions, start_dt, end_dt, eff_date, cwd) -> str:
    out: list[str] = []
    out.append("# Claude Code activity")
    out.append("")
    out.append(f"- project: `{cwd}`")
    out.append(f"- window: {start_dt.date()} to {end_dt.date()}")
    out.append(f"- effective date: {eff_date}")
    out.append(f"- sessions: {len(sessions)}")
    total_turns = sum(len(s["turns"]) for s in sessions)
    out.append(f"- total turns: {total_turns}")
    out.append("")

    if not sessions:
        out.append("_No conversations found in this window._")
        return "\n".join(out)

    for i, s in enumerate(sessions, 1):
        started = s["started"].strftime("%Y-%m-%d %H:%M")
        ended = s["ended"].strftime("%H:%M")
        out.append(f"## Session {i} ({started} to {ended})")
        out.append(f"_session id: {s['session_id']}_")
        out.append("")
        for role, text, ts in s["turns"]:
            label = "USER" if role == "user" else "ASSISTANT"
            out.append(f"### {label} ({ts.strftime('%H:%M')})")
            out.append(text)
            out.append("")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Collect Claude Code activity for standup synthesis.",
    )
    p.add_argument("--day", help="Specific date YYYY-MM-DD")
    p.add_argument("--yesterday", action="store_true")
    p.add_argument("--today", action="store_true")
    p.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD")
    p.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD")
    p.add_argument("--last", type=int, help="Last N days inclusive")
    p.add_argument("--cwd", help="Override cwd (testing only)")
    args = p.parse_args()

    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    start_dt, end_dt, eff_date = parse_window(args)

    project_dir = find_project_dir(cwd)
    if project_dir is None:
        sys.stderr.write(
            f"# No Claude Code project history found\n"
            f"# cwd: {cwd}\n"
            f"# tried: ~/.claude/projects/{encode_project_path(cwd)}\n"
        )
        return 2

    sessions = collect_sessions(project_dir, start_dt, end_dt)
    sys.stdout.write(render(sessions, start_dt, end_dt, eff_date, cwd))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
