from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE
from career.services import application_context
from career.services.database import Database
from career.services.persistence.gate_repository import GateRepository


DEFAULT_STATE_PATH = CAREER_STATE / "workflow_state.json"
DEFAULT_PAYLOAD = {
    "completed_states": [],
    "task_history": [],
    "fingerprints": {},
    "active_job": None,
}


@dataclass
class WorkflowStateStore:
    application_id: str | None = None
    database: Database | None = None
    path: Path = DEFAULT_STATE_PATH
    payload: dict[str, Any] = field(default_factory=dict)

    def load(self) -> dict[str, Any]:
        if not self.application_id or self.database is None:
            raise ValueError(
                "workflow state requires an application-scoped store backed by SQLite"
            )
        repository = GateRepository(self.database)
        self.payload = {
            **DEFAULT_PAYLOAD,
            **repository.compatibility_payload(self.application_id),
        }
        return self.payload

    def save(self) -> None:
        raise RuntimeError("workflow state store is a read-only SQLite projection")

    def reset(self) -> None:
        raise RuntimeError("workflow state store is a read-only SQLite projection")

    @classmethod
    def for_application(
        cls,
        application_id: str,
        *,
        database: Database,
        root: Path | None = None,
    ) -> "WorkflowStateStore":
        return cls(
            application_id=application_id,
            database=database,
            path=application_context.paths_for(application_id, root=root).workflow_state,
        )
