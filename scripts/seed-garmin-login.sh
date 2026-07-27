#!/usr/bin/env bash
#
# seed-garmin-login.sh — one-time interactive login to seed the Garmin token cache.
#
# Run this ONCE (it is interactive, so it can handle 2FA/MFA prompts) before enabling
# the background launchd job. It logs in with the credentials in ~/.fit2json.env and
# saves the resulting garth tokens to the token dir, so later non-interactive polls can
# resume the session without triggering CAPTCHA / rate limiting.

set -euo pipefail

IMAGE="${FIT2JSON_IMAGE:-ghcr.io/kerem-ersoz/fit2json:latest}"
LIB_DIR="${FIT2JSON_LIB_DIR:-$HOME/.fit2json/library}"
TOKEN_DIR="${FIT2JSON_TOKEN_DIR:-$HOME/.fit2json/garmintokens}"
ENV_FILE="${FIT2JSON_ENV_FILE:-$HOME/.fit2json.env}"
DAYS="${FIT2JSON_DAYS:-1}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file '$ENV_FILE' not found." >&2
  echo "Create it with your Garmin credentials, e.g.:" >&2
  echo "  printf 'GARMIN_EMAIL=you@example.com\\nGARMIN_PASSWORD=yourpassword\\n' > $ENV_FILE" >&2
  echo "  chmod 600 $ENV_FILE" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop and try again." >&2
  exit 1
fi

mkdir -p "$LIB_DIR/fit" "$LIB_DIR/json" "$TOKEN_DIR"

echo "Seeding Garmin token cache into: $TOKEN_DIR"
echo "(If your account uses 2FA/MFA, enter the code when prompted.)"

# -it keeps this interactive so garth can prompt for an MFA code if needed.
docker run -it --rm \
  --env-file "$ENV_FILE" \
  -e GARMINTOKENS=/tokens \
  -v "$TOKEN_DIR":/tokens \
  -v "$LIB_DIR":/data \
  "$IMAGE" \
  fetch garmin --days "$DAYS" --raw-dir /data/fit --json-dir /data/json

echo
echo "Done. Tokens saved to $TOKEN_DIR."
echo "Next: enable the background job with scripts/install-launchd.sh"
