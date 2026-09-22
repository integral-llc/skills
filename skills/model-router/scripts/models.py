#!/usr/bin/env python3
"""Single source of truth for the tiers the router can pick.

A tier is an Agent-tool alias plus the exact model id that alias resolves to.
The alias is what the hook writes: the Agent tool validates `model` against
a fixed enum and turns an input that fails validation into a deny. The id is
what transcripts must show.

Ids are not maintained by hand. Claude Code writes the requested alias into
each subagent's meta.json and the model that answered into its log, so
learn.py records every alias -> id pairing it observes. Precedence:
Claude Code's own env override, then the learned id, then the seed below.
Only a new alias (a new family or tier) needs a human, because cost order and
the Jev criteria are policy; doctor.py reports when that happens.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state", "model-router")
LEARNED_PATH = os.path.join(STATE_DIR, "resolved.json")


@dataclass(frozen=True)
class Tier:
    alias: str  # value the Agent tool's `model` enum accepts
    seed_id: str  # verified resolution, used until a newer one is observed
    env_override: str  # Claude Code env var that re-points the alias


# Cost order, cheapest first. Seeds verified 2026-09-22 against Claude Code
# 2.1.280 subagent transcripts (meta.json model vs message.model).
REGISTRY: tuple[Tier, ...] = (
    Tier("haiku", "claude-haiku-4-5-20251001", "ANTHROPIC_DEFAULT_HAIKU_MODEL"),
    Tier("sonnet", "claude-sonnet-5", "ANTHROPIC_DEFAULT_SONNET_MODEL"),
    Tier("opus", "claude-opus-5-5", "ANTHROPIC_DEFAULT_OPUS_MODEL"),
    Tier("fable", "claude-fable-5-1", "ANTHROPIC_DEFAULT_FABLE_MODEL"),
)

TIERS: tuple[str, ...] = tuple(t.alias for t in REGISTRY)
BY_ALIAS: dict[str, Tier] = {t.alias: t for t in REGISTRY}
# Agent definitions may also say "inherit": the subagent runs on the main model.
INHERIT = "inherit"
_DATE_SUFFIX = re.compile(r"-\d{8}$")


def tier_of(model: str) -> str | None:
    """Map an alias, a registry id or a family id to its tier.

    "opus[1m]", "claude-opus-5-5" and "claude-opus-4-8" all map to opus: the
    family decides the cost tier, the exact id is checked separately."""
    lowered = (model or "").lower()
    return next((alias for alias in TIERS if alias in lowered), None)


def learned() -> dict:
    try:
        with open(LEARNED_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def resolved_id(alias: str, cache: dict | None = None) -> str:
    """Id the alias resolves to right now, by the precedence in the docstring."""
    tier = BY_ALIAS[alias]
    override = os.environ.get(tier.env_override)
    if override:
        return override
    entry = (cache if cache is not None else learned()).get("aliases", {}).get(alias) or {}
    return entry.get("id") or tier.seed_id


def base_id(model_id: str) -> str:
    """Drop the context suffix and the snapshot date: "claude-haiku-4-5-20251001"
    and "claude-haiku-4-5" name the same model."""
    return _DATE_SUFFIX.sub("", (model_id or "").lower().split("[", 1)[0])


def version_of(model_id: str) -> tuple[int, ...] | None:
    """(5, 5) for "claude-opus-5-5", (4, 5) for "claude-haiku-4-5-20251001";
    None when the id does not have the claude-<family>-<numbers> shape."""
    parts = base_id(model_id).split("-")
    if len(parts) < 3 or parts[0] != "claude" or not all(p.isdigit() for p in parts[2:]):
        return None
    return tuple(int(p) for p in parts[2:])


def display_name(model_id: str) -> str:
    """"claude-haiku-4-5-20251001" -> "Claude Haiku 4.5"; unknown shapes pass through."""
    parts = base_id(model_id).split("-")
    if len(parts) < 3 or parts[0] != "claude" or not all(p.isdigit() for p in parts[2:]):
        return model_id
    return f"Claude {parts[1].capitalize()} {'.'.join(parts[2:])}"


def describe(alias: str, cache: dict | None = None) -> str:
    """"opus (Claude Opus 5.5, claude-opus-5-5)" for grey lines and context."""
    if alias not in BY_ALIAS:
        return alias
    model_id = resolved_id(alias, cache)
    return f"{alias} ({display_name(model_id)}, {model_id})"


def id_matches(alias: str, observed: str, cache: dict | None = None) -> bool:
    """Transcripts may carry a dated id ("-20251001") or a context suffix
    ("[1m]"); both still name the expected model."""
    return base_id(observed) == base_id(resolved_id(alias, cache))
