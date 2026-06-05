#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

require_cmd() {
  name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "missing_command=$name" >&2
    return 1
  fi
  command -v "$name"
}

require_cmd git
require_cmd node
require_cmd npm
require_cmd python3

if command -v hermes >/dev/null 2>&1; then
  command -v hermes
  hermes --version
else
  echo "warning=hermes_not_found agent heartbeat will be blocked until Hermes is installed" >&2
fi

if command -v libreoffice >/dev/null 2>&1; then
  libreoffice --version
elif command -v soffice >/dev/null 2>&1; then
  soffice --version
elif [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
  /Applications/LibreOffice.app/Contents/MacOS/soffice --version
else
  echo "LibreOffice/soffice not found" >&2
  echo "macOS: brew install --cask libreoffice" >&2
  exit 1
fi

PYTHONDONTWRITEBYTECODE=1 npm run validate:structure
PYTHONDONTWRITEBYTECODE=1 npm run runtime:diagnose
