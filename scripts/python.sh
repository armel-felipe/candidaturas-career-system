#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

resolve_python() {
  if [ "${PYTHON:-}" != "" ]; then
    printf '%s\n' "$PYTHON"
    return 0
  fi

  pyenv_root="${PYENV_ROOT:-$HOME/.pyenv}"
  if [ -f "$project_root/.python-version" ]; then
    desired_version=$(tr -d '[:space:]' < "$project_root/.python-version")
    if [ -n "$desired_version" ] && [ -x "$pyenv_root/versions/$desired_version/bin/python3" ]; then
      printf '%s\n' "$pyenv_root/versions/$desired_version/bin/python3"
      return 0
    fi
  fi

  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  echo "missing_command=python3" >&2
  exit 1
}

assert_supported_version() {
  python_cmd="$1"
  "$python_cmd" - "$@" <<'PY'
import sys

minimum = (3, 12)
current = sys.version_info[:2]
if current < minimum:
    raise SystemExit(
        f"python_version_unsupported={sys.version.split()[0]} minimum_required={minimum[0]}.{minimum[1]}"
    )
PY
}

python_cmd=$(resolve_python)
assert_supported_version "$python_cmd"
exec "$python_cmd" "$@"
