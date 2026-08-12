#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.career-state/browser-gateway"
LOG_DIR="$STATE_DIR/logs"
DISPLAY_NUMBER="${LINKEDIN_DISPLAY_NUMBER:-99}"
DISPLAY_VALUE=":$DISPLAY_NUMBER"
VNC_PORT="${LINKEDIN_VNC_PORT:-5900}"
NOVNC_PORT="${LINKEDIN_NOVNC_PORT:-6080}"
PUBLIC_NOVNC_PORT="${LINKEDIN_NOVNC_PUBLIC_PORT:-$NOVNC_PORT}"
BIND_HOST="${LINKEDIN_NOVNC_BIND:-0.0.0.0}"
SCREEN="${LINKEDIN_SCREEN:-1366x900x24}"

mkdir -p "$STATE_DIR" "$LOG_DIR"

if [ "$(uname -s)" = "Darwin" ]; then
  cat >"$STATE_DIR/env" <<EOF
LINKEDIN_BROWSER_MODE=macos-local
USER_DATA_DIR=.career-state/browser/linkedin
EOF
  echo "mode=macos-local"
  echo "noVNC gateway is Linux-only. On macOS, use the local Playwright browser:"
  echo "npm run linkedin:auth"
  echo "npm run linkedin:extract:authenticated -- --url \"<url>\""
  exit 0
fi

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing_dependency=$1"
    echo "Run npm run linkedin:browser:install-deps after rebuilding the Docker image."
    exit 1
  fi
}

is_alive() {
  test -f "$1" && kill -0 "$(cat "$1")" >/dev/null 2>&1
}

start_process() {
  name="$1"
  pid_file="$STATE_DIR/$name.pid"
  shift
  if is_alive "$pid_file"; then
    echo "$name=already_running pid=$(cat "$pid_file")"
    return
  fi
  "$@" >"$LOG_DIR/$name.log" 2>&1 &
  echo "$!" >"$pid_file"
  sleep 1
  if ! is_alive "$pid_file"; then
    echo "$name=failed log=$LOG_DIR/$name.log"
    exit 1
  fi
  echo "$name=started pid=$(cat "$pid_file")"
}

need_cmd Xvfb
need_cmd x11vnc
need_cmd fluxbox
need_cmd websockify

if [ ! -d /usr/share/novnc ]; then
  echo "missing_dependency=/usr/share/novnc"
  echo "Run npm run linkedin:browser:install-deps after rebuilding the Docker image."
  exit 1
fi

start_process xvfb Xvfb "$DISPLAY_VALUE" -screen 0 "$SCREEN" -nolisten tcp
start_process fluxbox env DISPLAY="$DISPLAY_VALUE" fluxbox

if [ -n "${LINKEDIN_VNC_PASSWORD:-}" ]; then
  PASS_FILE="$STATE_DIR/vnc.pass"
  x11vnc -storepasswd "$LINKEDIN_VNC_PASSWORD" "$PASS_FILE" >/dev/null 2>&1
  chmod 600 "$PASS_FILE"
  VNC_AUTH_ARGS=(-rfbauth "$PASS_FILE")
else
  VNC_AUTH_ARGS=(-nopw)
fi

start_process x11vnc x11vnc -display "$DISPLAY_VALUE" -localhost -forever -shared -rfbport "$VNC_PORT" "${VNC_AUTH_ARGS[@]}"
start_process novnc websockify --web /usr/share/novnc "$BIND_HOST:$NOVNC_PORT" "127.0.0.1:$VNC_PORT"

cat >"$STATE_DIR/env" <<EOF
DISPLAY=$DISPLAY_VALUE
VNC_PORT=$VNC_PORT
NOVNC_PORT=$NOVNC_PORT
NOVNC_PUBLIC_PORT=$PUBLIC_NOVNC_PORT
NOVNC_BIND=$BIND_HOST
NOVNC_URL=http://127.0.0.1:$PUBLIC_NOVNC_PORT/vnc.html?host=127.0.0.1&port=$PUBLIC_NOVNC_PORT
EOF

echo "display=$DISPLAY_VALUE"
echo "novnc_url=http://127.0.0.1:$PUBLIC_NOVNC_PORT/vnc.html?host=127.0.0.1&port=$PUBLIC_NOVNC_PORT"
echo "ssh_tunnel=ssh -L $PUBLIC_NOVNC_PORT:127.0.0.1:$PUBLIC_NOVNC_PORT <usuario>@<servidor>"
echo "linkedin_auth=DISPLAY=$DISPLAY_VALUE npm run linkedin:auth"
