#!/usr/bin/env python3
import argparse
import base64
import json
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


def gmail_token_json_from_env() -> dict | None:
    load_dotenv()
    encoded = os.environ.get("GMAIL_TOKEN_JSON_B64", "").strip()
    if not encoded:
        return None
    try:
        raw = base64.b64decode(encoded).decode("utf-8")
        payload = json.loads(raw)
    except Exception as exc:
        raise SystemExit("GMAIL_TOKEN_JSON_B64 is not valid base64-encoded JSON.") from exc
    if not isinstance(payload, dict):
        raise SystemExit("GMAIL_TOKEN_JSON_B64 must decode to a JSON object.")
    return payload


def env_has_gmail_token_json(path: Path = Path(".env")) -> bool:
    if not path.exists():
        return False
    return any(line.startswith("GMAIL_TOKEN_JSON_B64=") for line in path.read_text(encoding="utf-8").splitlines())


def save_gmail_token_json_to_env(creds, path: Path = Path(".env")) -> None:
    encoded = base64.b64encode(creds.to_json().encode("utf-8")).decode("ascii")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    next_lines: list[str] = []
    for line in lines:
        if line.startswith("GMAIL_TOKEN_JSON_B64="):
            next_lines.append(f"GMAIL_TOKEN_JSON_B64={encoded}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        if next_lines and next_lines[-1].strip():
            next_lines.append("")
        next_lines.append("# Gmail OAuth authorized-user token")
        next_lines.append(f"GMAIL_TOKEN_JSON_B64={encoded}")
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


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

    token_payload = gmail_token_json_from_env()
    if token_payload:
        creds = Credentials.from_authorized_user_info(token_payload, SCOPES)
    elif token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    else:
        creds = None

    if creds is None:
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

    if env_has_gmail_token_json():
        save_gmail_token_json_to_env(creds)
    else:
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
