#!/usr/bin/env python3
import argparse
import base64
import mimetypes
import sys
from email.message import EmailMessage
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


def existing_attachments(paths: list[Path]) -> list[Path]:
    missing = [path for path in paths if not path.exists() or not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Attachment file(s) not found:\n{formatted}")
    return paths


def read_body(body: str | None, body_file: Path | None) -> str:
    if body is not None and body_file is not None:
        raise SystemExit("Use either --body or --body-file, not both.")
    if body_file is not None:
        if not body_file.exists() or not body_file.is_file():
            raise SystemExit(f"Body file not found: {body_file}")
        return body_file.read_text(encoding="utf-8")
    if body is not None:
        return body
    raise SystemExit("Provide --body or --body-file.")


def build_message(to: str, subject: str, body: str, attachments: list[Path]) -> EmailMessage:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    for attachment in attachments:
        mime_type, _ = mimetypes.guess_type(str(attachment))
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )

    return message


def create_draft(token_path: Path, message: EmailMessage) -> dict:
    build = ensure_gmail_client()
    credentials = load_or_authorize(token_path)
    service = build("gmail", "v1", credentials=credentials)
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return service.users().drafts().create(userId="me", body={"message": {"raw": raw_message}}).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Gmail draft with optional attachments.")
    parser.add_argument("--to", required=True, help="Recipient email address.")
    parser.add_argument("--subject", required=True, help="Draft subject.")
    parser.add_argument("--body", help="Plain-text email body.")
    parser.add_argument("--body-file", type=Path, help="UTF-8 text file with the email body.")
    parser.add_argument("--attach", type=Path, action="append", default=[], help="Attachment path. Repeat as needed.")
    parser.add_argument("--token", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print the draft summary without Gmail API calls.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attachments = existing_attachments(args.attach)
    body = read_body(args.body, args.body_file)
    message = build_message(args.to, args.subject, body, attachments)

    if args.dry_run:
        print("Draft validation passed.")
        print(f"To: {args.to}")
        print(f"Subject: {args.subject}")
        print(f"Attachments: {len(attachments)}")
        return 0

    token_path = args.token or default_token_path()
    draft = create_draft(token_path, message)
    draft_id = draft.get("id", "")
    print(f"Gmail draft created: {draft_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
