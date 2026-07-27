#!/usr/bin/env bash
#
# garmin-export.sh — near-real-time Garmin export via Docker.
#
# Designed to be driven by launchd every ~15 minutes. It resumes a cached Garmin
# session (see GARMINTOKENS), downloads only new activities (skip-already-downloaded),
# archives raw .fit files, and writes one JSON per new activity.
#
# All paths/values below can be overridden via environment variables.

set -euo pipefail

IMAGE="${FIT2JSON_IMAGE:-ghcr.io/kerem-ersoz/fit2json:latest}"
LIB_DIR="${FIT2JSON_LIB_DIR:-$HOME/.fit2json/library}"          # -> /data in container
TOKEN_DIR="${FIT2JSON_TOKEN_DIR:-$HOME/.fit2json/garmintokens}" # -> /tokens
ENV_FILE="${FIT2JSON_ENV_FILE:-$HOME/.fit2json.env}"            # GARMIN_EMAIL / GARMIN_PASSWORD
LOG_DIR="${FIT2JSON_LOG_DIR:-$HOME/.fit2json/logs}"
DAYS="${FIT2JSON_DAYS:-1}"

LOG_FILE="$LOG_DIR/garmin-export.log"

mkdir -p "$LIB_DIR/fit" "$LIB_DIR/json" "$TOKEN_DIR" "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >>"$LOG_FILE"
}

# Docker Desktop may not be running (laptop asleep, just booted, etc.).
# Log clearly and exit 0 so launchd doesn't treat it as a crash / spam retries.
if ! command -v docker >/dev/null 2>&1; then
  log "docker CLI not found on PATH; skipping this run."
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  log "Docker daemon not running; skipping this run."
  exit 0
fi

if [ ! -f "$ENV_FILE" ]; then
  log "Env file '$ENV_FILE' not found; create it with GARMIN_EMAIL/GARMIN_PASSWORD. Skipping."
  exit 0
fi

log "Starting Garmin export (image=$IMAGE, days=$DAYS)."

if docker run --rm \
    --env-file "$ENV_FILE" \
    -e GARMINTOKENS=/tokens \
    -v "$TOKEN_DIR":/tokens \
    -v "$LIB_DIR":/data \
    "$IMAGE" \
    fetch garmin --days "$DAYS" --raw-dir /data/fit -o /data/json \
    >>"$LOG_FILE" 2>&1; then
  log "Garmin export finished OK."
else
  status=$?
  log "Garmin export failed (exit $status). See output above."
fi

# Always exit 0: a transient failure shouldn't turn into launchd retry storms.
exit 0
