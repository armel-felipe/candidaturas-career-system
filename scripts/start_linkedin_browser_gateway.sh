#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"
mkdir -p "$STATE_DIR"

cat >"$STATE_DIR/env" <<EOF
LINKEDIN_BROWSER_MODE=macos-local
USER_DATA_DIR=.career-state/browser/linkedin
EOF

echo "mode=macos-local"
echo "gateway=not_used"
echo "Authenticate locally with:"
echo "  npm run linkedin:auth"
echo "Extract after authentication with:"
echo "  npm run linkedin:extract:authenticated -- --url \"<url>\""
