#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"

if [ "$(uname -s)" = "Darwin" ]; then
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
  exit 0
fi

status_one() {
  name="$1"
  pid_file="$STATE_DIR/$name.pid"
  if test -f "$pid_file" && kill -0 "$(cat "$pid_file")" >/dev/null 2>&1; then
    echo "$name=running pid=$(cat "$pid_file")"
  else
    echo "$name=stopped"
  fi
}

status_one xvfb
status_one fluxbox
status_one x11vnc
status_one novnc

if test -f "$STATE_DIR/env"; then
  sed -n '1,20p' "$STATE_DIR/env"
fi
