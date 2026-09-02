from __future__ import annotations

import json
from typing import Any, Iterable

from pathlib import Path

from career.services.application_context import canonical_database
from career.services.session_memory import SessionMemoryService
from career.utils import ValidationFailure, utc_now_iso


class PipelineIntentStore:
    """Persist the scoped work requested in one conversation session.

    The session key is supplied by the runtime adapter.  It is deliberately
    not inferred from an active/global application pointer.
    """

    MEMORY_KEY = "harness_pipeline_intent_v2"
    TTL_SECONDS = 30 * 24 * 60 * 60

    def __init__(self, root: Path):
        # The root parameter remains part of the public test/runtime API, but
        # the record itself is now held in the authoritative control-plane.
        database = canonical_database(root=root)
        database.migrate()
        self._memory = SessionMemoryService(database)

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
        current = self.resolve(session_key) or {}
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
        self._memory.set(
            session_key,
            self.MEMORY_KEY,
            json.dumps(record, ensure_ascii=False, sort_keys=True),
            ttl_seconds=self.TTL_SECONDS,
        )
        return record

    def resolve(self, session_key: str) -> dict[str, Any] | None:
        session_key = str(session_key or "").strip()
        if not session_key:
            return None
        raw = self._memory.get(session_key, self.MEMORY_KEY)
        if not raw:
            return None
        try:
            record = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(record, dict) or record.get("session_key") != session_key:
            return None
        if not str(record.get("application_id") or "").strip():
            return None
        return record
