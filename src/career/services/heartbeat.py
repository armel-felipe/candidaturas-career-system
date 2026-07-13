from __future__ import annotations

from typing import Any

from career.services.database import Database
from career.services.queue import QueueBuilder
from career.services.stages import StageMachine


class Heartbeat:
    def __init__(self, database: Database):
        self._database = database
        self._queue = QueueBuilder(database)
        self._stages = StageMachine(database)

    def run(self, max_per_run: int = 3, dry_run: bool = False) -> dict:
        applications = self._queue.get_eligible(max_items=max_per_run)
        processed: list[dict] = []
        errors: list[dict] = []

        for app in applications:
            app_id = str(app["id"])
            current_stage = str(app["stage"])
            running_stage = current_stage.replace("_pending", "_running")

            if running_stage not in self._stages.allowed_transitions(current_stage):
                errors.append({"id": app_id, "error": f"no transition from {current_stage}"})
                continue

            if dry_run:
                processed.append({"id": app_id, "from": current_stage, "to": running_stage, "dry_run": True})
                continue

            success = self._stages.transition(app_id, current_stage, running_stage)
            if success:
                processed.append({"id": app_id, "from": current_stage, "to": running_stage})
            else:
                errors.append({"id": app_id, "error": f"transition failed {current_stage} -> {running_stage}"})

        return {"processed": processed, "errors": errors, "dry_run": dry_run}
