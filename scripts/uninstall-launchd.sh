#!/usr/bin/env bash
#
# uninstall-launchd.sh — remove the Garmin export launchd agent.
#
# Stops and unloads the agent and deletes the installed plist. Your archived .fit/JSON
# files and cached tokens under ~/.fit2json are left untouched.

set -euo pipefail

LABEL="com.fit2json.garmin-export"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

# bootout covers modern macOS; fall back to legacy unload if needed.
if ! launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null; then
  launchctl unload -w "$DEST" 2>/dev/null || true
fi

rm -f "$DEST"

echo "Uninstalled launchd agent: $LABEL"
echo "Removed: $DEST"
echo "Archived data under ~/.fit2json (library, tokens, logs) was left in place."
