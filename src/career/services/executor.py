from __future__ import annotations

from datetime import datetime, timezone

from career.services.database import Database


class Executor:
    def __init__(self, database: Database):
        self.db = database

    def run(self, specialist: str, context: dict) -> dict:
        message = str(context.get("message", ""))
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """INSERT INTO workflow_events (application_id, event, metadata, created_at)
               VALUES (?, ?, ?, ?)""",
            ("_harness", f"specialist:{specialist}", message[:500], now),
        )
        return {
            "status": "completed",
            "specialist": specialist,
            "message": f"Executed specialist '{specialist}'",
            "finished_at": now,
        }
