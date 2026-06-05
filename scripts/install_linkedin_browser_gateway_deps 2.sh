#!/usr/bin/env bash
set -eu

if [ "$(uname -s)" = "Darwin" ]; then
  echo "macOS detected. The noVNC/Xvfb gateway is not used on MacBook."
  echo "Install Playwright browsers with: npx playwright install chromium"
  echo "Then authenticate locally with: npm run linkedin:auth"
  exit 0
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo not found. Install manually: apt-get update && apt-get install -y xvfb x11vnc fluxbox novnc websockify"
  exit 1
fi

sudo apt-get update
sudo apt-get install -y xvfb x11vnc fluxbox novnc websockify

echo "LinkedIn browser gateway dependencies installed."
