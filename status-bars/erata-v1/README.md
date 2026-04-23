# erata-v1 status bar

Claude Code statusline: `ccstatusline` (Max plan metrics) + optional caveman plugin badge.

## Layout

Two rendered lines via `ccstatusline`, plus a caveman badge appended to line 1 when the plugin is active.

- Line 1: `model | context-length | git-branch | git-changes` + caveman badge
- Line 2: `reset-timer | weekly-usage | context-bar`

Flex mode `full-minus-40`, 256-color, compact threshold 60.

## Files

- `statusline.sh` - wrapper script invoked by Claude Code. Pipes stdin JSON to `ccstatusline`, appends caveman badge from the plugin hook if present.
- `ccstatusline.settings.json` - segment config for `ccstatusline` v3.

## Install

1. Install `ccstatusline`:
   ```
   bun add -g ccstatusline
   ```
2. Drop config:
   ```
   mkdir -p ~/.config/ccstatusline
   cp ccstatusline.settings.json ~/.config/ccstatusline/settings.json
   ```
3. Drop wrapper:
   ```
   mkdir -p ~/.claude/scripts
   cp statusline.sh ~/.claude/scripts/statusline.sh
   chmod +x ~/.claude/scripts/statusline.sh
   ```
4. Wire in `~/.claude/settings.json`:
   ```json
   "statusLine": {
     "type": "command",
     "command": "bash \"/Users/<you>/.claude/scripts/statusline.sh\""
   }
   ```

## Caveman badge

Optional. Wrapper looks for the plugin hook at
`~/.claude/plugins/cache/caveman/caveman/<hash>/hooks/caveman-statusline.sh`.
Update `CAVEMAN_SCRIPT` in `statusline.sh` if your plugin cache path differs,
or remove the block to drop the badge entirely.
