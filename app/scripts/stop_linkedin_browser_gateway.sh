#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"

if [ "$(uname -s)" = "Darwin" ]; then
  rm -f "$STATE_DIR/env"
  echo "mode=macos-local"
  echo "gateway=not_used"
  echo "Nothing to stop. Close any Playwright browser windows opened by npm run linkedin:auth if needed."
  exit 0
fi

stop_one() {
  name="$1"
  pid_file="$STATE_DIR/$name.pid"
  if test -f "$pid_file" && kill -0 "$(cat "$pid_file")" >/dev/null 2>&1; then
    kill "$(cat "$pid_file")" >/dev/null 2>&1 || true
    rm -f "$pid_file"
    echo "$name=stopped"
  else
    rm -f "$pid_file"
    echo "$name=not_running"
  fi
}

stop_one novnc
stop_one x11vnc
stop_one fluxbox
stop_one xvfb
rm -f "$STATE_DIR/env"

