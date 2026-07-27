#!/usr/bin/env bash
#
# install-launchd.sh — install the near-real-time Garmin export as a launchd agent.
#
# Templates deploy/com.fit2json.garmin-export.plist with absolute paths and the chosen
# interval, installs it to ~/Library/LaunchAgents, and (re)loads it with launchctl.
#
# Change the poll interval (seconds) by exporting INTERVAL, e.g.:
#   INTERVAL=600 ./scripts/install-launchd.sh

set -euo pipefail

LABEL="com.fit2json.garmin-export"
INTERVAL="${INTERVAL:-900}"   # seconds; 900 = 15 min

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WRAPPER="$SCRIPT_DIR/garmin-export.sh"
TEMPLATE="$REPO_DIR/deploy/$LABEL.plist"
LOG_DIR="${FIT2JSON_LOG_DIR:-$HOME/.fit2json/logs}"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -f "$TEMPLATE" ]; then
  echo "Template not found: $TEMPLATE" >&2
  exit 1
fi

chmod +x "$SCRIPT_DIR"/*.sh
mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

# Fill in the template (use | as sed delimiter since values contain /).
sed -e "s|__WRAPPER__|$WRAPPER|g" \
    -e "s|__LOGDIR__|$LOG_DIR|g" \
    -e "s|__INTERVAL__|$INTERVAL|g" \
    "$TEMPLATE" >"$DEST"

DOMAIN="gui/$(id -u)"

# Reload cleanly: remove any previous instance first (ignore if not loaded).
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

if launchctl bootstrap "$DOMAIN" "$DEST" 2>/dev/null; then
  launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
  launchctl kickstart -k "$DOMAIN/$LABEL" 2>/dev/null || true
else
  # Fallback for older macOS where bootstrap may be unavailable.
  launchctl load -w "$DEST"
fi

echo "Installed launchd agent: $LABEL"
echo "  plist    : $DEST"
echo "  wrapper  : $WRAPPER"
echo "  interval : ${INTERVAL}s"
echo "  logs     : $LOG_DIR/garmin-export.log (and launchd.out.log / launchd.err.log)"
echo
echo "It runs now and then every ${INTERVAL}s. Tail the log with:"
echo "  tail -f \"$LOG_DIR/garmin-export.log\""
echo "Uninstall with: $SCRIPT_DIR/uninstall-launchd.sh"
