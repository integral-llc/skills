#!/usr/bin/env python3
"""Check that everything the router names still exists and still resolves.

    doctor.py

FAIL means routing can break (an alias the Agent tool would reject, an agent
definition no tier covers); WARN means it degrades (Jev offline, a model id
the installed Claude Code does not list). Exit 1 on any FAIL. A clean run
records the Claude Code version, so SessionStart stops nagging until the
next update.
"""

from __future__ import annotations

import glob
import json
import mmap
import os
import re
import shutil
import sys

from agent_defs import CLAUDE_DIR, INSTALLED_PLUGINS, read_fields
from learn import installed_claude_code, learn, save
from models import BY_ALIAS, INHERIT, TIERS, base_id, learned, resolved_id, tier_of
from route import route

# Array literals of short lowercase words, e.g. ["sonnet","opus","haiku","fable"].
_ALIAS_ARRAY = re.compile(rb'\[(?:"[a-z]{2,12}",){2,8}"[a-z]{2,12}"\]')


class Report:
    def __init__(self) -> None:
        self.failed = False

    def line(self, level: str, text: str) -> None:
        self.failed |= level == "FAIL"
        print(f"  {level:<4} {text}")


def binary_path() -> str:
    found = shutil.which("claude")
    return os.path.realpath(found) if found else ""


def agent_enum(blob: mmap.mmap) -> set[str] | None:
    """Smallest alias array holding every registry alias: the Agent `model` enum."""
    best: set[str] | None = None
    for match in _ALIAS_ARRAY.finditer(blob):
        words = set(json.loads(match.group(0)))
        if set(TIERS) <= words and (best is None or len(words) < len(best)):
            best = words
    if best is not None:
        return best
    # No array holds every alias: find the one sharing most, to say what is missing.
    candidates = [set(json.loads(m.group(0))) for m in _ALIAS_ARRAY.finditer(blob)]
    scored = [c for c in candidates if len(c & set(TIERS)) >= len(TIERS) - 1]
    return min(scored, key=len) if scored else None


def check_binary(report: Report, state: dict) -> None:
    path = binary_path()
    if not path:
        report.line("WARN", "claude not on PATH; cannot verify the Agent enum or model ids")
        return
    report.line("ok", f"Claude Code {installed_claude_code() or '?'} at {path}")
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as blob:
        enum = agent_enum(blob)
        if enum is None:
            report.line("WARN", "Agent model enum not found in the binary; alias validity unverified")
        else:
            missing = set(TIERS) - enum
            extra = enum - set(TIERS)
            for alias in sorted(missing):
                report.line("FAIL", f"alias '{alias}' is gone from the Agent enum; the hook would stamp an invalid model")
            for alias in sorted(extra):
                report.line("WARN", f"new alias '{alias}' in the Agent enum: add a Tier to models.py "
                                    "(cost position + Jev criteria are a human call)")
            if not missing and not extra:
                report.line("ok", f"Agent enum matches the registry: {', '.join(TIERS)}")
        for alias in TIERS:
            model_id = resolved_id(alias, state)
            known = blob.find(f'"{base_id(model_id)}'.encode()) != -1
            report.line("ok" if known else "WARN",
                        f"{alias:<7} -> {model_id}" + ("" if known else " (id not listed in this Claude Code build)"))


def check_env(report: Report) -> None:
    for tier in BY_ALIAS.values():
        value = os.environ.get(tier.env_override)
        if value:
            report.line("ok", f"{tier.env_override} overrides {tier.alias} -> {value}")
    for name in ("CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"):
        if os.environ.get(name):
            report.line("WARN", f"{name} is set: it can override the tier the hook stamps")


def check_settings(report: Report) -> None:
    try:
        with open(os.path.join(CLAUDE_DIR, "settings.json"), encoding="utf-8") as fh:
            model = str(json.load(fh).get("model") or "")
    except (OSError, ValueError):
        model = ""
    if tier_of(model):
        report.line("ok", f"session model '{model}' is tier {tier_of(model)}")
    else:
        report.line("WARN", f"session model '{model or 'unset'}' maps to no tier; placement falls back to the tier table")


def agent_files() -> list[str]:
    files = glob.glob(os.path.join(CLAUDE_DIR, "agents", "*.md"))
    files += glob.glob(os.path.join(os.getcwd(), ".claude", "agents", "*.md"))
    try:
        with open(INSTALLED_PLUGINS, encoding="utf-8") as fh:
            plugins = json.load(fh).get("plugins") or {}
    except (OSError, ValueError):
        plugins = {}
    for installs in plugins.values():
        for install in installs or []:
            path = (install or {}).get("installPath")
            if path:
                files += glob.glob(os.path.join(path, "agents", "*.md"))
    return sorted(set(files))


def check_agents(report: Report) -> None:
    files = agent_files()
    bad = 0
    for path in files:
        model = ((read_fields(path) or {}).get("model") or "").strip()
        if model and model != INHERIT and not tier_of(model):
            bad += 1
            report.line("FAIL", f"{path}: model '{model}' maps to no tier")
    if not bad:
        report.line("ok", f"{len(files)} agent definitions: every model value maps to a tier or inherit")


def check_learned(report: Report) -> dict:
    for alias, old, new in learn(full=True):
        report.line("WARN", f"{alias} now resolves to {new} (was {old}); learned from transcripts")
    state = learned()
    for reason in (state.get("held") or {}).values():
        report.line("WARN", f"held back: {reason}")
    for alias in TIERS:
        entry = (state.get("aliases") or {}).get(alias)
        if entry:
            report.line("ok", f"{alias:<7} observed {entry['id']} on Claude Code {entry['claude_code']} at {entry['seen']}")
        else:
            report.line("WARN", f"{alias:<7} never observed; using seed {BY_ALIAS[alias].seed_id}")
    return state


def check_jev(report: Report) -> None:
    result = route("find where parse_toggle is defined")
    if result["source"] == "jev" and result["model"] in TIERS:
        report.line("ok", f"Jev answered '{result['model']}' (conf {result['confidence']:.2f})")
    else:
        report.line("WARN", f"Jev not reachable, keyword fallback in use: {result.get('error')}")


def main() -> int:
    report = Report()
    print("model-router doctor")
    state = check_learned(report)
    check_binary(report, state)
    check_env(report)
    check_settings(report)
    check_agents(report)
    check_jev(report)
    if report.failed:
        print("FAILED: fix the FAIL lines above")
        return 1
    version = installed_claude_code()
    if version:
        save({**learned(), "claude_code_checked": version})
    print("healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
