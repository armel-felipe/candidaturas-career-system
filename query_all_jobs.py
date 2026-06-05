#!/usr/bin/env python3
"""List recent Notion application records using .env credentials."""

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


def text_value(prop: dict) -> str:
    prop_type = prop.get("type")
    if prop_type in {"title", "rich_text"}:
        return "".join(part.get("plain_text", "") for part in prop.get(prop_type, [])).strip()
    if prop_type == "url":
        return str(prop.get("url") or "").strip()
    if prop_type == "number":
        return str(prop.get("number") or "").strip()
    if prop_type == "select":
        selected = prop.get("select") or {}
        return str(selected.get("name") or "").strip()
    return ""


def main() -> int:
    load_env()
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_APPLICATIONS_DATABASE_ID")
    if not token or not database_id:
        raise SystemExit("Set NOTION_TOKEN and NOTION_APPLICATIONS_DATABASE_ID in .env before running.")

    request = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{database_id}/query",
        data=json.dumps({"page_size": 25}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read())

    for index, record in enumerate(payload.get("results", []), start=1):
        props = record.get("properties", {})
        title = ""
        unique_id = ""
        for name, prop in props.items():
            if not isinstance(prop, dict):
                continue
            value = text_value(prop)
            if not value:
                continue
            if not title and prop.get("type") == "title":
                title = value
            if name.casefold() == "id":
                unique_id = value
        print(f"{index}. ID={unique_id or '-'} | {title or record.get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
