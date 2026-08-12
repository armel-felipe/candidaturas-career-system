#!/usr/bin/env python3
"""List Notion application records using credentials from .env.

Prefer the official project commands (`npm run notion:list` and
`scripts/notion_sync.py`). This helper is kept for quick manual checks.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_APPLICATIONS_DATABASE_ID")
    if not token or not database_id:
        raise SystemExit("Set NOTION_TOKEN and NOTION_APPLICATIONS_DATABASE_ID in .env before running.")

    request = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        data=json.dumps({"page_size": 20}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read())

    for item in payload.get("results", []):
        print(item.get("id", "unknown"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
