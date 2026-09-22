#!/usr/bin/env python3
"""Look up the `model:` an agent definition declares, so routing can treat it
as a floor. The Agent tool's `model` param overrides the definition, so a
routed tier written below it would silently downgrade a specialist that was
pinned to opus on purpose.

Resolution order matches Claude Code: project agents, user agents, then
plugin agents (`plugin:name`) from installed_plugins.json.
"""

from __future__ import annotations

import json
import os
import re

from models import tier_of

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
INSTALLED_PLUGINS = os.path.join(CLAUDE_DIR, "plugins", "installed_plugins.json")
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
_FIELD = re.compile(r"^(name|model)\s*:\s*[\"']?([^\"'\n#]+?)[\"']?\s*$", re.MULTILINE)


def definition_tier(subagent_type: str, cwd: str = "") -> str | None:
    """Tier pinned by the agent's definition, or None for inherit, built-in
    agents, unknown names, and definitions without a `model:` line."""
    if not subagent_type:
        return None
    plugin, _, name = subagent_type.rpartition(":")
    dirs = _plugin_agent_dirs(plugin) if plugin else _local_agent_dirs(cwd)
    for folder in dirs:
        fields = _find_definition(folder, name)
        if fields is not None:
            return tier_of(fields.get("model", ""))
    return None


def _local_agent_dirs(cwd: str) -> list[str]:
    dirs = [os.path.join(cwd, ".claude", "agents")] if cwd else []
    return dirs + [os.path.join(CLAUDE_DIR, "agents")]


def _plugin_agent_dirs(plugin: str) -> list[str]:
    try:
        with open(INSTALLED_PLUGINS, encoding="utf-8") as fh:
            plugins = json.load(fh).get("plugins") or {}
    except (OSError, ValueError):
        return []
    dirs = []
    for key, installs in plugins.items():
        if key.split("@", 1)[0] != plugin:
            continue
        for install in installs or []:
            path = (install or {}).get("installPath")
            if path:
                dirs.append(os.path.join(path, "agents"))
    return dirs


def _find_definition(folder: str, name: str) -> dict | None:
    """File named after the agent first; else the file whose `name:` matches,
    since the file name and the declared name are allowed to differ."""
    direct = read_fields(os.path.join(folder, f"{name}.md"))
    if direct is not None:
        return direct
    try:
        candidates = sorted(e.path for e in os.scandir(folder) if e.name.endswith(".md"))
    except OSError:
        return None
    for path in candidates:
        fields = read_fields(path)
        if fields is not None and fields.get("name") == name:
            return fields
    return None


def read_fields(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    match = _FRONTMATTER.match(head)
    if not match:
        return {}
    return {key: value.strip() for key, value in _FIELD.findall(match.group(1))}
