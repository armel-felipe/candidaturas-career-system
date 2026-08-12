from __future__ import annotations

from typing import Any

from career.services.database import Database


STAGE_GRAPH: dict[str, list[str]] = {
    "analyze_pending": ["analyze_running", "analyze_retry_pending"],
    "analyze_running": ["generate_pending", "blocked_review", "error"],
    "generate_pending": ["generate_running", "error"],
    "generate_running": ["done", "blocked_review", "error"],
    "repair_pending": ["repair_running", "error"],
    "repair_running": ["generate_pending", "blocked_review_exhausted", "error"],
    "blocked_review": ["repair_pending", "low_fit"],
    "blocked_review_exhausted": ["low_fit"],
    "low_fit": ["done"],
    "done": [],
    "error": ["analyze_pending", "generate_pending"],
}


class StageMachine:
    def __init__(self, database: Database):
        self._database = database

    def allowed_transitions(self, current_stage: str) -> list[str]:
        return STAGE_GRAPH.get(current_stage, [])

    def transition(self, application_id: str, from_stage: str, to_stage: str) -> bool:
        allowed = self.allowed_transitions(from_stage)
        if to_stage not in allowed:
            return False
        cursor = self._database.execute(
            "UPDATE applications SET stage = ?, updated_at = datetime('now') WHERE id = ? AND stage = ?",
            (to_stage, application_id, from_stage),
        )
        return cursor.rowcount > 0
