from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE
from career.services import application_context
from career.services.database import Database
from career.services.persistence.gate_repository import GateRepository
from career.utils import read_json, utc_now_iso, write_json


DEFAULT_STATE_PATH = CAREER_STATE / "workflow_state.json"
DEFAULT_PAYLOAD = {
    "completed_states": [],
    "task_history": [],
    "fingerprints": {},
    "active_job": None,
}
ACTIVE_POINTER_FILENAME = "active_application.json"


@dataclass
class WorkflowStateStore:
    application_id: str | None = None
    database: Database | None = None
    path: Path = field(default_factory=lambda: DEFAULT_STATE_PATH)
    payload: dict[str, Any] = field(default_factory=dict)

    def load(self) -> dict[str, Any]:
        application_id = self._resolved_application_id()
        if application_id is not None:
            self.payload = self._load_application_projection(application_id)
            return self.payload

        if self._uses_global_pointer_projection():
            pointer = self._load_pointer()
            pointed_application_id = str(pointer.get("application_id") or "").strip()
            if pointed_application_id:
                scoped = self.for_application(pointed_application_id, database=self._database())
                payload = scoped.load()
                if isinstance(pointer.get("active_intake"), dict):
                    payload["active_intake"] = dict(pointer["active_intake"])
                if isinstance(pointer.get("active_job"), dict):
                    payload["active_job"] = dict(pointer["active_job"])
                payload["active_application_id"] = pointed_application_id
                self.payload = payload
                return self.payload

            self.payload = self._empty_payload()
            return self.payload

        if self.path.exists():
            payload = read_json(self.path)
            if isinstance(payload, dict):
                self.payload = {**self._empty_payload(), **payload}
                return self.payload

        self.payload = self._empty_payload()
        return self.payload

    def save(self) -> None:
        application_id = self._resolved_application_id()
        if application_id is None:
            if not self._uses_file_backed_compatibility_store():
                raise RuntimeError("unscoped workflow state writes are not supported")
            write_json(self.path, self.payload)
            return
        companion = self._application_state_path()
        companion.parent.mkdir(parents=True, exist_ok=True)
        current = read_json(companion) if companion.exists() else {
            "kind": "application_state",
            "application_id": application_id,
            "created_at": utc_now_iso(),
        }
        current["kind"] = "application_state"
        current["application_id"] = application_id
        current["updated_at"] = utc_now_iso()
        current["active_job"] = self.payload.get("active_job")
        current["active_intake"] = self.payload.get("active_intake")
        current["active_application_id"] = application_id
        write_json(companion, current)

    def reset(self) -> None:
        application_id = self._resolved_application_id()
        if application_id is None:
            if not self._uses_file_backed_compatibility_store():
                raise RuntimeError("unscoped workflow state resets are not supported")
            self.payload = self._empty_payload()
            write_json(self.path, self.payload)
            return
        companion = self._application_state_path()
        if companion.exists():
            current = read_json(companion)
            current["active_job"] = None
            current["active_intake"] = None
            current["active_application_id"] = None
            current["updated_at"] = utc_now_iso()
            write_json(companion, current)
        self.payload = dict(DEFAULT_PAYLOAD)

    @classmethod
    def for_application(
        cls,
        application_id: str,
        *,
        database: Database | None = None,
        root: Path | None = None,
    ) -> "WorkflowStateStore":
        return cls(
            application_id=application_id,
            database=database,
            path=application_context.paths_for(application_id, root=root).workflow_state,
        )

    @classmethod
    def clear_active_pointer(cls, *, path: Path | None = None) -> None:
        cls._pointer_path(path).unlink(missing_ok=True)

    @classmethod
    def write_active_pointer(
        cls,
        *,
        application_id: str,
        active_job: dict[str, Any] | None,
        active_intake: dict[str, Any] | None,
        path: Path | None = None,
    ) -> None:
        pointer_path = cls._pointer_path(path)
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "active_application_pointer",
            "application_id": application_id,
            "active_job": active_job or None,
            "active_intake": active_intake or None,
            "updated_at": utc_now_iso(),
        }
        write_json(pointer_path, payload)

    def _database(self) -> Database:
        if self.database is None:
            self.database = Database()
        return self.database

    def _resolved_application_id(self) -> str | None:
        if self.application_id:
            return str(self.application_id)
        if self.path.name not in {"workflow_state.json", "state.json"}:
            return None
        parent = self.path.parent
        grandparent = parent.parent
        if grandparent.name != "applications_v2" or not parent.name:
            return None
        return parent.name

    def _load_application_projection(self, application_id: str) -> dict[str, Any]:
        repository = GateRepository(self._database())
        payload = {
            **DEFAULT_PAYLOAD,
            **repository.compatibility_payload(application_id),
        }
        metadata = self._load_application_metadata()
        active_job = metadata.get("active_job")
        active_intake = metadata.get("active_intake")
        if isinstance(active_job, dict):
            payload["active_job"] = active_job
        if isinstance(active_intake, dict):
            payload["active_intake"] = active_intake
            payload["active_application_id"] = active_intake.get("application_id") or application_id
        else:
            payload["active_intake"] = None
            payload["active_application_id"] = application_id
        return payload

    def _load_application_metadata(self) -> dict[str, Any]:
        companion = self._application_state_path()
        if companion.exists():
            payload = read_json(companion)
            if isinstance(payload, dict):
                return payload
        if self.path.exists():
            payload = read_json(self.path)
            if isinstance(payload, dict):
                return payload
        return {}

    def _application_state_path(self) -> Path:
        if self.path.name == "state.json":
            return self.path
        return self.path.with_name("state.json")

    def _load_pointer(self) -> dict[str, Any]:
        candidate_paths = []
        pointer_path = self._pointer_path(None)
        if self.path == DEFAULT_STATE_PATH:
            candidate_paths.append(pointer_path)
        if self.path != pointer_path:
            candidate_paths.append(self.path)
        if self.path != DEFAULT_STATE_PATH:
            candidate_paths.append(pointer_path)
        for candidate in candidate_paths:
            if candidate.exists():
                payload = read_json(candidate)
                if isinstance(payload, dict):
                    return payload
        return {}

    def _uses_global_pointer_projection(self) -> bool:
        return self.path in {DEFAULT_STATE_PATH, self._pointer_path(None)}

    def _uses_file_backed_compatibility_store(self) -> bool:
        return self._resolved_application_id() is None and not self._uses_global_pointer_projection()

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {
            "completed_states": [],
            "task_history": [],
            "fingerprints": {},
            "active_job": None,
            "active_intake": None,
            "active_application_id": None,
        }

    @classmethod
    def _pointer_path(cls, override: Path | None) -> Path:
        if override is not None:
            return override
        return CAREER_STATE / ACTIVE_POINTER_FILENAME
