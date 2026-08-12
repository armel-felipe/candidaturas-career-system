#!/usr/bin/env bash
set -euo pipefail

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
target_host="${TARGET_HOST:-root@srv1876742}"
target_root="${TARGET_ROOT:-/opt/agent-projects/candidaturas}"
ssh_key="${SSH_KEY:-/home/ubuntu/.ssh/id_ed25519}"

if [[ "$target_host" != "root@srv1876742" || "$target_root" != "/opt/agent-projects/candidaturas" ]]; then
  echo "refusing_unexpected_destination=$target_host:$target_root" >&2
  exit 2
fi

for required in \
  "$project_root/app" \
  "$project_root/hermes-src" \
  "$project_root/hermes/runtime/vagas_bot_01" \
  "$project_root/hermes/vagas_bot_01" \
  "$project_root/workspaces/vagas_bot_01/state" \
  "$project_root/workspaces/vagas_bot_02/state"; do
  if [[ ! -e "$required" ]]; then
    echo "missing_required_path=$required" >&2
    exit 3
  fi
done

ssh_command="ssh -i $ssh_key -o BatchMode=yes -o StrictHostKeyChecking=yes"
rsync_command=(rsync -aHAX --numeric-ids --info=progress2 -e "$ssh_command")

"${rsync_command[@]}" \
  --exclude=.git/ \
  --exclude=node_modules/ \
  --exclude=.career-state/ \
  --exclude=outputs/ \
  --exclude=.env \
  --exclude='*.tmp' \
  "$project_root/app/" "$target_host:$target_root/app/"
"${rsync_command[@]}" "$project_root/hermes/" "$target_host:$target_root/hermes/"
"${rsync_command[@]}" \
  --exclude=.git/ \
  --exclude=.env \
  "$project_root/hermes-src/" "$target_host:$target_root/hermes-src/"

