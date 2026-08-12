#!/usr/bin/env bash
set -eu

if [ "$(uname -s)" = "Darwin" ]; then
  echo "macOS detected. The noVNC/Xvfb gateway is not used on MacBook."
  echo "Install Playwright browsers with: npx playwright install chromium"
  echo "Then authenticate locally with: npm run linkedin:auth"
  exit 0
fi

missing=0
for command_name in Xvfb x11vnc fluxbox websockify; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "missing_dependency=$command_name"
    missing=1
  fi
done

if [ ! -d /usr/share/novnc ]; then
  echo "missing_dependency=/usr/share/novnc"
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  echo "Docker image is missing the LinkedIn browser gateway dependencies."
  echo "Do not run apt-get inside the agent container."
  echo "On the server host, run from /opt/agent-projects/candidaturas:"
  echo "  docker compose build vagas_bot_01 vagas_bot_02"
  echo "  docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02"
  exit 1
fi

echo "gateway_dependencies=present"
echo "gateway_dependencies_source=Docker image"

