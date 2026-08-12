from __future__ import annotations

from typing import Any

from career.services.database import Database


class QueueBuilder:
    def __init__(self, database: Database):
        self._database = database

    def get_eligible(self, max_items: int = 10) -> list[dict]:
        return self._database.fetch_all(
            """SELECT * FROM applications
               WHERE status = 'active'
                 AND stage IN ('analyze_pending', 'generate_pending', 'repair_pending')
               ORDER BY created_at ASC
               LIMIT ?""",
            (max_items,),
        )

    def get_by_funil_stage(self, funil_stage: str) -> list[dict]:
        return self._database.fetch_all(
            """SELECT * FROM applications
               WHERE funil_stage = ?
                 AND status = 'active'
               ORDER BY created_at ASC""",
            (funil_stage,),
        )
