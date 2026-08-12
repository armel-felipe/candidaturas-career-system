from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


MAX_REPLY_AGE_SECONDS = 600


def _reply_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
    hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    return hermes_home / "state" / "career-harness-replies" / f"{digest}.json"


def transform_output(*, response_text: str, session_id: str, **_: object) -> str | None:
    path = _reply_path(session_id)
    if not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > MAX_REPLY_AGE_SECONDS:
            path.unlink(missing_ok=True)
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        reply_text = payload.get("reply_text") if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return None
    path.unlink(missing_ok=True)
    return reply_text.strip() if isinstance(reply_text, str) and reply_text.strip() else None


def register(ctx) -> None:
    ctx.register_hook("transform_llm_output", transform_output)
