#!/usr/bin/env sh
set -eu

cd -- "$(dirname -- "$0")"

echo "This will install an automatic agent heartbeat every 60 minutes and may consume model credits over time."
printf 'Type INSTALL to continue: '
read confirm
if [ "$confirm" != "INSTALL" ]; then
  echo "Cancelled."
  exit 1
fi

echo "Installing Career Applications Agent Heartbeat with launchd every 60 minutes..."
sh scripts/install_applications_heartbeat_launchd.sh --interval-minutes 60 --max-per-run 1 --run-agent

echo
echo "Done. Scheduler: launchd."
