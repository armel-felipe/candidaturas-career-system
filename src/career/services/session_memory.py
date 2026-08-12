from __future__ import annotations

from datetime import datetime, timezone

from career.services.database import Database


class SessionMemoryService:
    def __init__(self, database: Database):
        self._db = database

    def set(self, session_id: str, key: str, value: str, ttl_seconds: int = 3600) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            """INSERT OR REPLACE INTO session_memory
               (session_id, key, value, created_at, ttl_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, key, value, now, ttl_seconds),
        )

    def get(self, session_id: str, key: str) -> str | None:
        row = self._db.fetch_one(
            """SELECT value FROM session_memory
               WHERE session_id = ? AND key = ?
               AND (strftime('%%s','now') - strftime('%%s', created_at)) < ttl_seconds""",
            (session_id, key),
        )
        return row["value"] if row else None

    def get_all(self, session_id: str) -> dict:
        rows = self._db.fetch_all(
            """SELECT key, value FROM session_memory
               WHERE session_id = ?
               AND (strftime('%%s','now') - strftime('%%s', created_at)) < ttl_seconds""",
            (session_id,),
        )
        return {row["key"]: row["value"] for row in rows}

    def status(self, session_id: str) -> dict:
        return self.get_all(session_id)

    def clean(self, session_id: str) -> None:
        self._db.execute(
            """DELETE FROM session_memory
               WHERE session_id = ?
               AND (strftime('%%s','now') - strftime('%%s', created_at)) >= ttl_seconds""",
            (session_id,),
        )

    def reset(self, session_id: str) -> None:
        self._db.execute(
            "DELETE FROM session_memory WHERE session_id = ?",
            (session_id,),
        )
