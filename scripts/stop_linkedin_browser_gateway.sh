#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"

rm -f "$STATE_DIR/env"
echo "mode=macos-local"
echo "gateway=not_used"
echo "Nothing to stop. Close any Playwright browser windows opened by npm run linkedin:auth if needed."
