#!/bin/bash
# Combined statusline: ccusage (Max plan metrics) + caveman badge.
# Reads Claude Code's stdin JSON, pipes to ccusage, appends caveman badge if active.

set -e

STATUSLINE_BIN="$(command -v ccstatusline || true)"
CAVEMAN_SCRIPT="$HOME/.claude/plugins/cache/caveman/caveman/63e797cd753b/hooks/caveman-statusline.sh"

INPUT=$(cat)

LINE=""
if [ -n "$STATUSLINE_BIN" ]; then
  LINE=$(printf '%s' "$INPUT" | "$STATUSLINE_BIN" 2>/dev/null || printf 'ccstatusline error')
fi

BADGE=""
if [ -f "$CAVEMAN_SCRIPT" ]; then
  BADGE=$(bash "$CAVEMAN_SCRIPT" 2>/dev/null)
fi

if [ -n "$LINE" ] && [ -n "$BADGE" ]; then
  if printf '%s' "$LINE" | grep -q $'\n'; then
    FIRST=$(printf '%s' "$LINE" | head -n1)
    REST=$(printf '%s' "$LINE" | tail -n +2)
    printf '%s %s\n%s' "$FIRST" "$BADGE" "$REST"
  else
    printf '%s %s' "$LINE" "$BADGE"
  fi
elif [ -n "$LINE" ]; then
  printf '%s' "$LINE"
elif [ -n "$BADGE" ]; then
  printf '%s' "$BADGE"
fi
