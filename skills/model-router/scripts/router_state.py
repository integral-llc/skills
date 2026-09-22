#!/usr/bin/env python3
"""On/off state for the model router, shared by the hooks, the CLI and the statusline.

State is a flag file, same pattern as the caveman plugin: present means on,
absent means off. It persists across sessions until toggled.

Usage:
    router_state.py on | off | status
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

from models import tier_of

FLAG_PATH = os.path.join(os.path.expanduser("~"), ".claude", ".model-router-active")
# Per-session record of the main model, written by the SessionStart hook so
# the prompt hook can compare the routed tier against what is actually running.
SESSION_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state", "model-router")
# Assistant messages can be large; the last one is always within this window.
TRANSCRIPT_TAIL_BYTES = 512 * 1024
# Session records are only read while the session lives; a month covers resumes.
SESSION_RECORD_MAX_AGE_S = 30 * 24 * 3600
# session_id becomes a file name, so anything beyond a UUID-like token is refused.
_SESSION_ID = re.compile(r"^[\w-]{1,128}$")


def _session_file(session_id: str) -> str | None:
    if not _SESSION_ID.match(session_id or ""):
        return None
    return os.path.join(SESSION_DIR, f"{session_id}.model")


def remember_session_model(session_id: str, model: str) -> None:
    path = _session_file(session_id)
    if not path or not model:
        return
    os.makedirs(SESSION_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(model)
    prune_session_records()


def prune_session_records(now: float | None = None) -> None:
    cutoff = (now if now is not None else time.time()) - SESSION_RECORD_MAX_AGE_S
    try:
        entries = list(os.scandir(SESSION_DIR))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.name.endswith(".model") and entry.stat().st_mtime < cutoff:
                os.unlink(entry.path)
        except OSError:
            continue


def session_tier(session_id: str, transcript_path: str = "") -> str | None:
    """Tier of the main model for this session.

    The transcript is ground truth (a resumed session keeps its old model,
    whatever settings.json says), then what SessionStart reported, then the
    configured default for a session that has not answered yet."""
    model = transcript_model(transcript_path) or recorded_session_model(session_id) or configured_default_model()
    return tier_of(model)


def recorded_session_model(session_id: str) -> str:
    path = _session_file(session_id)
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip().lower()
    except OSError:
        return ""


def transcript_model(transcript_path: str) -> str:
    """`message.model` of the latest assistant message in the session log.

    The path comes from the hook payload; rebuilding it from cwd breaks on
    dots, underscores and a `cd` into a subfolder."""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TRANSCRIPT_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    for line in reversed(tail.splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "assistant":
            model = str((record.get("message") or {}).get("model") or "").lower()
            if model and not model.startswith("<"):
                return model
    return ""


def configured_default_model() -> str:
    settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    try:
        with open(settings_path, encoding="utf-8") as fh:
            return str(json.load(fh).get("model") or "").lower()
    except (OSError, ValueError):
        return ""

# Slash command with optional argument, plus the natural-language switches.
# The phrases must be the whole prompt: matching inside a sentence toggled the
# router on "how do I stop the router from dropping packets".
_COMMAND = re.compile(r"^/model-router(?:\s+(on|off|status))?\s*$", re.IGNORECASE)
_NL_OFF = re.compile(r"^(?:please\s+)?(?:stop|disable|turn off) (?:the )?(?:model[- ])?router\s*[.!]?$", re.IGNORECASE)
_NL_ON = re.compile(r"^(?:please\s+)?(?:start|enable|turn on) (?:the )?(?:model[- ])?router\s*[.!]?$", re.IGNORECASE)


def is_active() -> bool:
    return os.path.isfile(FLAG_PATH)


def set_active(active: bool) -> None:
    if active:
        os.makedirs(os.path.dirname(FLAG_PATH), exist_ok=True)
        with open(FLAG_PATH, "w", encoding="utf-8") as fh:
            fh.write("on\n")
        return
    try:
        os.unlink(FLAG_PATH)
    except FileNotFoundError:
        pass


def parse_toggle(prompt: str) -> str | None:
    """Return "on", "off", "status", or None when the prompt is not a toggle."""
    text = prompt.strip()
    match = _COMMAND.match(text)
    if match:
        return (match.group(1) or "status").lower()
    if _NL_OFF.match(text):
        return "off"
    if _NL_ON.match(text):
        return "on"
    return None


def status_line() -> str:
    return "model-router: on" if is_active() else "model-router: off"


def main(argv: list[str]) -> int:
    action = (argv[1] if len(argv) > 1 else "status").lower()
    if action == "on":
        set_active(True)
    elif action == "off":
        set_active(False)
    elif action != "status":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    print(status_line())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
