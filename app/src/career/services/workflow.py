from __future__ import annotations

import json
from datetime import datetime, timezone

from career.services.database import Database


class WorkflowService:
    def __init__(self, database: Database):
        self._db = database

    def record_event(
        self,
        application_id: str,
        event: str,
        fingerprint: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (application_id, event, fingerprint, json.dumps(metadata) if metadata else None, now),
        )

    def get_events(self, application_id: str, limit: int = 50) -> list[dict]:
        return self._db.fetch_all(
            """SELECT * FROM workflow_events
               WHERE application_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (application_id, limit),
        )

    def get_latest_event(self, application_id: str) -> dict | None:
        return self._db.fetch_one(
            """SELECT * FROM workflow_events
               WHERE application_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (application_id,),
        )

    def set_active_application(self, application_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "UPDATE applications SET updated_at = ? WHERE id = ?",
            (now, application_id),
        )

    def get_active_application(self) -> dict | None:
        return self._db.fetch_one(
            "SELECT * FROM applications ORDER BY updated_at DESC LIMIT 1"
        )
