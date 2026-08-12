#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "deprecated_script=$0" >&2
echo "use=$SCRIPT_DIR/start_linkedin_browser_gateway.sh" >&2
exec "$SCRIPT_DIR/start_linkedin_browser_gateway.sh" "$@"

