from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from career.utils import ValidationFailure, read_json, utc_now_iso, write_json


class ApprovalStore:
    def __init__(self, root: Path):
        self.directory = root / ".career-state" / "approvals"

    def create(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        approval_id = uuid.uuid4().hex
        record = {
            "approval_id": approval_id,
            "action": action,
            "status": "pending",
            "payload": payload,
            "created_at": utc_now_iso(),
            "approved_at": None,
            "consumed_at": None,
        }
        write_json(self.directory / f"{approval_id}.json", record)
        return record

    def create_idempotent(
        self,
        *,
        action: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create one approval for one externally visible operation."""
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValidationFailure("idempotency_key is required")
        approval_id = hashlib.sha256(
            f"{action}\0{key}".encode("utf-8")
        ).hexdigest()[:32]
        path = self.directory / f"{approval_id}.json"
        if path.exists():
            return read_json(path)
        record = {
            "approval_id": approval_id,
            "action": action,
            "idempotency_key": key,
            "status": "pending",
            "payload": payload,
            "created_at": utc_now_iso(),
            "approved_at": None,
            "consumed_at": None,
        }
        write_json(path, record)
        return record

    def approve(self, approval_id: str) -> dict[str, Any]:
        record = self.get(approval_id)
        if record.get("status") != "pending":
            raise ValidationFailure(f"Approval {approval_id} is not pending.")
        record["status"] = "approved"
        record["approved_at"] = utc_now_iso()
        write_json(self.directory / f"{approval_id}.json", record)
        return record

    def consume(self, approval_id: str) -> dict[str, Any]:
        record = self.get(approval_id)
        if record.get("status") != "approved":
            raise ValidationFailure(f"Approval {approval_id} must be approved before consumption.")
        record["status"] = "consumed"
        record["consumed_at"] = utc_now_iso()
        write_json(self.directory / f"{approval_id}.json", record)
        return record

    def get(self, approval_id: str) -> dict[str, Any]:
        path = self.directory / f"{approval_id}.json"
        if not path.exists():
            raise ValidationFailure(f"Approval {approval_id} does not exist.")
        return read_json(path)
