#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path


DEFAULT_TOKEN = Path(".secrets/gmail/token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
DEFAULT_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_REDIRECT_URI = "http://localhost:8080/"
DEFAULT_LOCAL_PORT = 8080


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def gmail_oauth_config() -> dict:
    load_dotenv()
    client_id = os.environ.get("GMAIL_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "Missing Gmail OAuth configuration. Set GMAIL_OAUTH_CLIENT_ID and "
            "GMAIL_OAUTH_CLIENT_SECRET in .env."
        )

    auth_uri = os.environ.get("GMAIL_OAUTH_AUTH_URI", DEFAULT_AUTH_URI).strip() or DEFAULT_AUTH_URI
    token_uri = os.environ.get("GMAIL_OAUTH_TOKEN_URI", DEFAULT_TOKEN_URI).strip() or DEFAULT_TOKEN_URI
    redirect_uri = os.environ.get("GMAIL_OAUTH_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": auth_uri,
            "token_uri": token_uri,
            "redirect_uris": [redirect_uri],
        }
    }


def default_token_path() -> Path:
    load_dotenv()
    configured = os.environ.get("GMAIL_TOKEN_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_TOKEN


def oauth_local_port() -> int:
    load_dotenv()
    configured = os.environ.get("GMAIL_OAUTH_LOCAL_PORT", "").strip()
    if not configured:
        return DEFAULT_LOCAL_PORT
    try:
        port = int(configured)
    except ValueError as exc:
        raise SystemExit("GMAIL_OAUTH_LOCAL_PORT must be an integer, for example 8080.") from exc
    if port <= 0 or port > 65535:
        raise SystemExit("GMAIL_OAUTH_LOCAL_PORT must be between 1 and 65535.")
    return port


def ensure_google_dependencies():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "Missing Gmail API Python dependencies. Install them with:\n"
            "python -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        ) from exc
    return Request, Credentials, InstalledAppFlow


def load_or_authorize(token_path: Path):
    Request, Credentials, InstalledAppFlow = ensure_google_dependencies()
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_config(gmail_oauth_config(), SCOPES)
        port = oauth_local_port()
        try:
            creds = flow.run_local_server(port=port)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) in (48, 98):
                raise SystemExit(
                    f"Could not start the local OAuth callback server because port {port} is already in use.\n"
                    "Either close the process using that port, or set both values in .env to another port, for example:\n"
                    "GMAIL_OAUTH_REDIRECT_URI=http://localhost:8081/\n"
                    "GMAIL_OAUTH_LOCAL_PORT=8081\n"
                    "Then add the same redirect URI in Google Cloud and run npm run gmail:auth again."
                ) from exc
            raise

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authorize local access to Gmail drafts.")
    parser.add_argument("--token", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token_path = args.token or default_token_path()
    load_or_authorize(token_path)
    print(f"Gmail authorization ready. Token saved to {token_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
