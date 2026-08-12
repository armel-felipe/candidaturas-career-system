#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
git_dir=$(git -C "$project_root" rev-parse --git-dir)
repo_root=$(git -C "$project_root" rev-parse --show-toplevel)

case "$git_dir" in
  /*) ;;
  *) git_dir="$repo_root/$git_dir" ;;
esac

source_hook="$project_root/.githooks/pre-commit"
hooks_dir="$git_dir/hooks"
target_hook="$hooks_dir/pre-commit"

if [ ! -f "$source_hook" ]; then
  echo "Hook template not found: $source_hook" >&2
  exit 1
fi

mkdir -p "$hooks_dir"
cp "$source_hook" "$target_hook"
chmod +x "$target_hook"

echo "Installed pre-commit hook at $target_hook"
echo "This hook acts only on files configured by teste_opencode."
