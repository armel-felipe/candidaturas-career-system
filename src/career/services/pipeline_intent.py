from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from career.utils import ValidationFailure, read_json, utc_now_iso, write_json


class PipelineIntentStore:
    """Persist the scoped work requested in one conversation session.

    The session key is supplied by the runtime adapter.  It is deliberately
    not inferred from an active/global application pointer.
    """

    def __init__(self, root: Path):
        self.directory = root / ".career-state" / "harness" / "pipeline_intents"

    def _path(self, session_key: str) -> Path:
        digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def bind(
        self,
        *,
        application_id: str,
        session_key: str,
        requested_steps: Iterable[str] = (),
    ) -> dict[str, Any]:
        application_id = str(application_id or "").strip()
        session_key = str(session_key or "").strip()
        if not application_id or not session_key:
            raise ValidationFailure("application_id and session_key are required")
        path = self._path(session_key)
        current = read_json(path) if path.exists() else {}
        current_application_id = str(current.get("application_id") or "").strip()
        if current_application_id and current_application_id != application_id:
            raise ValidationFailure(
                "session is already bound to a different application_id"
            )
        merged: list[str] = []
        for step in [*(current.get("requested_steps") or []), *requested_steps]:
            normalized = str(step or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        record = {
            "kind": "pipeline_intent",
            "session_key": session_key,
            "application_id": application_id,
            "requested_steps": merged,
            "updated_at": utc_now_iso(),
        }
        write_json(path, record)
        return record

    def resolve(self, session_key: str) -> dict[str, Any] | None:
        session_key = str(session_key or "").strip()
        if not session_key:
            return None
        path = self._path(session_key)
        if not path.exists():
            return None
        record = read_json(path)
        if not isinstance(record, dict) or record.get("session_key") != session_key:
            return None
        if not str(record.get("application_id") or "").strip():
            return None
        return record
