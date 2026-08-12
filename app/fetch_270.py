#!/usr/bin/env python3
"""Fetch one Notion application record by ID using .env credentials.

Usage:
    python3 fetch_270.py 270
"""

from __future__ import annotations

import json
import os
import sys
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


def plain_text(prop: dict) -> str:
    prop_type = prop.get("type")
    values = prop.get(prop_type) if prop_type else None
    if isinstance(values, list):
        return "".join(part.get("plain_text", "") for part in values if isinstance(part, dict)).strip()
    if isinstance(values, dict):
        return str(values.get("name") or values.get("number") or values.get("id") or "").strip()
    return str(values or "").strip()


def main() -> int:
    load_env()
    unique_id = sys.argv[1] if len(sys.argv) > 1 else "270"
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_APPLICATIONS_DATABASE_ID")
    if not token or not database_id:
        raise SystemExit("Set NOTION_TOKEN and NOTION_APPLICATIONS_DATABASE_ID in .env before running.")

    filter_payload = {"filter": {"property": "ID", "rich_text": {"equals": unique_id}}}
    request = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        data=json.dumps(filter_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read())

    results = payload.get("results", [])
    if not results:
        print(f"No Notion record found for ID={unique_id}")
        return 1

    record = results[0]
    print(f"Record: {record.get('id')}")
    for name, prop in record.get("properties", {}).items():
        if isinstance(prop, dict):
            value = plain_text(prop)
            if value:
                print(f"{name}: {value[:500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
