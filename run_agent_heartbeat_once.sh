#!/usr/bin/env sh
set -eu

cd -- "$(dirname -- "$0")"

echo "This will start the Career Applications Agent Heartbeat and may consume model credits."
printf 'Type RUN to continue: '
read confirm
if [ "$confirm" != "RUN" ]; then
  echo "Cancelled."
  exit 1
fi

echo "Running Career Applications Agent Heartbeat once..."
npm run applications:agent-heartbeat -- --max-per-run 2

echo
echo "Done. Check .career-state/applications_v2 and the terminal summary above."
