#!/usr/bin/env python3
"""Send an existing Gmail draft by ID."""
import argparse
import sys
from pathlib import Path

from gmail_auth import default_token_path, load_or_authorize


def ensure_gmail_client():
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SystemExit(
            "Missing Gmail API Python dependencies. Install them with:\n"
            "python -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        ) from exc
    return build


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an existing Gmail draft.")
    parser.add_argument("--draft-id", required=True, help="Draft ID to send.")
    parser.add_argument("--token", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build = ensure_gmail_client()
    token_path = args.token or default_token_path()
    credentials = load_or_authorize(token_path)
    service = build("gmail", "v1", credentials=credentials)

    # Get the draft message
    draft = service.users().drafts().get(userId="me", id=args.draft_id).execute()
    msg_id = draft["message"]["id"]

    # Send it
    result = service.users().drafts().send(userId="me", body={"id": args.draft_id}).execute()
    print(f"Email sent! Message ID: {result.get('id', 'unknown')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
