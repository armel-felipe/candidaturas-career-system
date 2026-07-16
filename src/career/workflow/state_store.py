from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from time import sleep

from career.paths import CAREER_STATE
from career.services import application_context
from career.utils import read_json, write_json


DEFAULT_STATE_PATH = CAREER_STATE / "workflow_state.json"
DEFAULT_PAYLOAD = {"completed_states": [], "task_history": [], "fingerprints": {}, "active_job": None}


@dataclass
class WorkflowStateStore:
    path: Path = DEFAULT_STATE_PATH
    payload: dict[str, Any] = field(default_factory=dict)

    def load(self) -> dict[str, Any]:
        if self.path.exists():
            last_error: Exception | None = None
            for _ in range(5):
                try:
                    self.payload = read_json(self.path)
                    break
                except (PermissionError, OSError) as exc:
                    last_error = exc
                    sleep(0.1)
            else:
                raise last_error  # type: ignore[misc]
        else:
            self.payload = dict(DEFAULT_PAYLOAD)
        self.payload.setdefault("completed_states", [])
        self.payload.setdefault("task_history", [])
        self.payload.setdefault("fingerprints", {})
        self.payload.setdefault("active_job", None)
        return self.payload

    def save(self) -> None:
        write_json(self.path, self.payload)

    def reset(self) -> None:
        self.payload = dict(DEFAULT_PAYLOAD)
        self.save()

    @classmethod
    def for_application(cls, application_id: str) -> "WorkflowStateStore":
        return cls(path=application_context.paths_for(application_id).workflow_state)
