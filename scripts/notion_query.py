#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


NOTION_VERSION = "2022-06-28"


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Notion API error {exc.code}: {detail}") from exc


def main() -> int:
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("Set NOTION_TOKEN in the environment or in .env before running this script.", file=sys.stderr)
        return 2

    if len(sys.argv) < 2 or sys.argv[1] not in {"database", "page"}:
        print("Usage: notion_query.py database [database_id] | page <page_id>", file=sys.stderr)
        return 2

    mode = sys.argv[1]
    if mode == "database":
        database_id = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NOTION_APPLICATIONS_DATABASE_ID")
        if not database_id:
            print("Provide database_id or set NOTION_APPLICATIONS_DATABASE_ID.", file=sys.stderr)
            return 2
        result = request("POST", f"https://api.notion.com/v1/databases/{database_id}/query", token, {})
    else:
        if len(sys.argv) < 3:
            print("Provide page_id.", file=sys.stderr)
            return 2
        result = request("GET", f"https://api.notion.com/v1/pages/{sys.argv[2]}", token)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
