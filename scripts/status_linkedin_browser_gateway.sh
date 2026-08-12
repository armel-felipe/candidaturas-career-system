#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"

echo "mode=macos-local"
echo "gateway=not_used"
if test -d "$ROOT_DIR/.career-state/browser/linkedin"; then
  echo "user_data_dir=present"
else
  echo "user_data_dir=missing"
fi
if test -f "$STATE_DIR/env"; then
  sed -n '1,20p' "$STATE_DIR/env"
fi
