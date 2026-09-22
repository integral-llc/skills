#!/bin/bash
# model-router statusline badge. Prints nothing when the router is off.
# Same contract as caveman-statusline.sh so statusline.sh can concatenate them.

FLAG="$HOME/.claude/.model-router-active"
[ ! -f "$FLAG" ] && exit 0
printf '\033[38;5;75m[ROUTER]\033[0m'
