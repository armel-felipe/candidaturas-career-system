#!/usr/bin/env sh
set -eu

cd -- "$(dirname -- "$0")"

echo "This will stop the active heartbeat/opencode run and clear local locks."
printf 'Type STOP to continue: '
read confirm
if [ "$confirm" != "STOP" ]; then
  echo "Cancelled."
  exit 1
fi

echo "Stopping active Career Applications Agent Heartbeat processes..."
pids=$(pgrep -f 'career_cli.py applications heartbeat|opencode.* run --agent build' || true)
if [ -n "$pids" ]; then
  current_pid=$$
  for pid in $pids; do
    if [ "$pid" != "$current_pid" ]; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped PID $pid"
    fi
  done
else
  echo "No active heartbeat/opencode run found."
fi

rm -f .career-state/applications/heartbeat.lock .career-state/applications_v2/heartbeat.lock
find .career-state/applications .career-state/applications_v2 -name .lock -type f -delete 2>/dev/null || true

echo
echo "Done."
