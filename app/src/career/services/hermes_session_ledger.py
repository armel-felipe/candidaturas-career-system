from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from career.utils import read_json, utc_now_iso, write_json


class HermesSessionLedgerError(ValueError):
    """Raised when a session ledger operation would violate its binding."""


_SCHEMA_VERSION = 1
_LEDGER_KEYS = (
    "operation",
    "profile_id",
    "session_key",
    "old_session_id",
    "new_session_id",
    "target_session_id",
    "application_id",
    "run_id",
    "reason",
    "status",
    "created_at",
    "idempotency_key",
    "resolves_idempotency_key",
)


@dataclass(frozen=True)
class HermesSessionLedger:
    """Append-only record of Hermes session boundaries for one application.

    The ledger is deliberately independent from the live Hermes gateway. Phase
    1 records intended/applied operations; later phases can use the same
    contract to coordinate gateway mutations without changing the durable
    application context.
    """

    path: Path
    application_id: str

    def __post_init__(self) -> None:
        path = Path(self.path)
        object.__setattr__(self, "path", path)
        application_id = str(self.application_id).strip()
        if not application_id:
            raise HermesSessionLedgerError("application_id must not be empty")
        object.__setattr__(self, "application_id", application_id)

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f".{self.path.name}.lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _empty_document(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "application_id": self.application_id,
            "records": [],
            "deleted_session_ids": [],
        }

    def _load_document(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_document()

        try:
            document = read_json(self.path)
        except (OSError, json.JSONDecodeError) as exc:
            raise HermesSessionLedgerError(
                f"could not read session ledger {self.path}: {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise HermesSessionLedgerError("session ledger must contain a JSON object")
        if document.get("schema_version") != _SCHEMA_VERSION:
            raise HermesSessionLedgerError("unsupported session ledger schema_version")
        if document.get("application_id") != self.application_id:
            raise HermesSessionLedgerError("session ledger application_id mismatch")
        records = document.get("records")
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise HermesSessionLedgerError("session ledger records must be a list of objects")
        deleted_session_ids = document.setdefault("deleted_session_ids", [])
        if not isinstance(deleted_session_ids, list) or any(
            not str(item).strip() for item in deleted_session_ids
        ):
            raise HermesSessionLedgerError("session ledger deleted_session_ids must be a list")
        return document

    def history(self) -> list[dict[str, Any]]:
        """Return a snapshot of all recorded operations in append order."""
        with self._locked():
            document = self._load_document()
            return [dict(record) for record in document["records"]]

    def current_binding(self) -> dict[str, str] | None:
        """Return the last known profile/session binding, if one exists."""
        records = self.history()
        if not records:
            return None
        record = records[-1]
        current_session_id = record.get("new_session_id")
        if not current_session_id:
            return None
        return {
            "application_id": self.application_id,
            "profile_id": str(record["profile_id"]),
            "session_key": str(record["session_key"]),
            "current_session_id": str(current_session_id),
        }

    def mark_transcript_deleted(self, session_id: str, *, reason: str) -> dict[str, Any]:
        """Record explicit transcript deletion so resume cannot be reported."""
        session_id = str(session_id or "").strip()
        reason = str(reason or "").strip()
        if not session_id or not reason:
            raise HermesSessionLedgerError("session_id and reason are required")
        with self._locked():
            document = self._load_document()
            deleted = document.setdefault("deleted_session_ids", [])
            if session_id not in deleted:
                deleted.append(session_id)
            write_json(self.path, document)
            return {
                "session_id": session_id,
                "reason": reason,
                "status": "transcript_deleted",
            }

    def resumability(self, session_id: str) -> dict[str, Any]:
        """Return whether an old session may still be resumed."""
        session_id = str(session_id or "").strip()
        if not session_id:
            return {"allowed": False, "reason": "session_id_required"}
        with self._locked():
            document = self._load_document()
        if session_id in document.get("deleted_session_ids", []):
            return {"allowed": False, "reason": "transcript_deleted", "session_id": session_id}
        return {"allowed": True, "reason": "session_record_retained", "session_id": session_id}

    def pending_records(self) -> list[dict[str, Any]]:
        """Return unresolved pending boundary operations."""
        records = self.history()
        resolved = {
            str(record.get("resolves_idempotency_key"))
            for record in records
            if record.get("operation") == "reconcile"
            and record.get("resolves_idempotency_key")
        }
        return [
            dict(record)
            for record in records
            if record.get("operation") in {"reset", "resume"}
            and record.get("status") == "pending_verification"
            and record.get("idempotency_key") not in resolved
        ]

    def record_reset(
        self,
        *,
        profile_id: str,
        session_key: str,
        old_session_id: str,
        new_session_id: str,
        run_id: str,
        reason: str,
        idempotency_key: str,
        status: str = "recorded",
    ) -> dict[str, Any]:
        return self._record(
            operation="reset",
            profile_id=profile_id,
            session_key=session_key,
            old_session_id=old_session_id,
            new_session_id=new_session_id,
            target_session_id=None,
            run_id=run_id,
            reason=reason,
            idempotency_key=idempotency_key,
            status=status,
        )

    def record_resume(
        self,
        *,
        profile_id: str,
        session_key: str,
        old_session_id: str,
        target_session_id: str,
        run_id: str,
        reason: str,
        idempotency_key: str,
        status: str = "recorded",
    ) -> dict[str, Any]:
        target_session_id = str(target_session_id).strip()
        return self._record(
            operation="resume",
            profile_id=profile_id,
            session_key=session_key,
            old_session_id=old_session_id,
            new_session_id=target_session_id,
            target_session_id=target_session_id,
            run_id=run_id,
            reason=reason,
            idempotency_key=idempotency_key,
            status=status,
        )

    def record_reconciliation(
        self,
        *,
        profile_id: str,
        session_key: str,
        old_session_id: str,
        current_session_id: str,
        target_session_id: str | None,
        run_id: str,
        reason: str,
        idempotency_key: str,
        resolves_idempotency_key: str,
        status: str,
    ) -> dict[str, Any]:
        return self._record(
            operation="reconcile",
            profile_id=profile_id,
            session_key=session_key,
            old_session_id=old_session_id,
            new_session_id=current_session_id,
            target_session_id=target_session_id,
            run_id=run_id,
            reason=reason,
            idempotency_key=idempotency_key,
            status=status,
            resolves_idempotency_key=resolves_idempotency_key,
        )

    def _record(
        self,
        *,
        operation: str,
        profile_id: str,
        session_key: str,
        old_session_id: str,
        new_session_id: str,
        target_session_id: str | None,
        run_id: str,
        reason: str,
        idempotency_key: str,
        status: str,
        resolves_idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        values = {
            "operation": operation,
            "profile_id": str(profile_id).strip(),
            "session_key": str(session_key).strip(),
            "old_session_id": str(old_session_id).strip(),
            "new_session_id": str(new_session_id).strip(),
            "target_session_id": target_session_id,
            "application_id": self.application_id,
            "run_id": str(run_id).strip(),
            "reason": str(reason).strip(),
            "status": str(status).strip(),
            "idempotency_key": str(idempotency_key).strip(),
            "resolves_idempotency_key": (
                str(resolves_idempotency_key).strip()
                if resolves_idempotency_key is not None
                else None
            ),
        }
        self._validate_values(values)

        with self._locked():
            document = self._load_document()
            records = document["records"]
            for existing in records:
                if existing.get("idempotency_key") != values["idempotency_key"]:
                    continue
                if any(existing.get(key) != values[key] for key in _LEDGER_KEYS if key != "created_at"):
                    raise HermesSessionLedgerError(
                        "idempotency_key already exists with a different payload"
                    )
                return dict(existing)

            self._validate_binding(document, values)
            record = {
                **values,
                "created_at": utc_now_iso(),
            }
            records.append(record)
            write_json(self.path, document)
            return dict(record)

    def _validate_values(self, values: dict[str, Any]) -> None:
        if values["operation"] not in {"reset", "resume", "reconcile"}:
            raise HermesSessionLedgerError("operation must be reset, resume, or reconcile")
        required = (
            "profile_id",
            "session_key",
            "old_session_id",
            "new_session_id",
            "application_id",
            "run_id",
            "reason",
            "status",
            "idempotency_key",
        )
        for field in required:
            if not str(values[field]).strip():
                raise HermesSessionLedgerError(f"{field} must not be empty")
        if values["operation"] == "resume" and not values["target_session_id"]:
            raise HermesSessionLedgerError("target_session_id is required for resume")
        if values["operation"] == "reset" and values["target_session_id"] is not None:
            raise HermesSessionLedgerError("target_session_id must be null for reset")
        if values["operation"] == "reconcile" and not values.get("resolves_idempotency_key"):
            raise HermesSessionLedgerError("resolves_idempotency_key is required for reconcile")

    def _validate_binding(self, document: dict[str, Any], values: dict[str, Any]) -> None:
        records = document["records"]
        if not records:
            return
        current = records[-1]
        for field in ("application_id", "profile_id", "session_key"):
            if current.get(field) != values[field]:
                raise HermesSessionLedgerError(f"session ledger {field} binding mismatch")
