#!/usr/bin/env bash
set -euo pipefail

record_id="${1:-270}"
env_file=".env"

if [ -f "$env_file" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
fi

: "${NOTION_TOKEN:?Set NOTION_TOKEN in .env before running.}"
: "${NOTION_APPLICATIONS_DATABASE_ID:?Set NOTION_APPLICATIONS_DATABASE_ID in .env before running.}"

filter_json=$(printf '{"filter":{"property":"ID","rich_text":{"equals":"%s"}}}' "$record_id")
url="https://api.notion.com/v1/databases/${NOTION_APPLICATIONS_DATABASE_ID}/query"

curl -sS -X POST "$url" \
  -H "Authorization: Bearer ${NOTION_TOKEN}" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d "$filter_json" | jq '.'
