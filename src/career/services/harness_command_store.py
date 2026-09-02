"""SQLite authority for Hermes/Telegram conversation commands.

The harness previously coordinated a message through several JSON files.  That
made a stale file capable of changing the outcome of a current conversation.
This store is deliberately small: it owns identity, idempotency, claims and
the final user-facing outcome of a turn.  The supervisor remains the domain
executor during the migration, but it receives the scope captured here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from career.services.database import Database


FINAL_STATUSES = frozenset({"awaiting_input", "awaiting_approval", "ready", "completed", "blocked"})
CLAIMABLE_STATUSES = frozenset({"queued", "running"})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalised_context(payload: dict[str, Any]) -> dict[str, str]:
    context = payload.get("runtime_context")
    context = context if isinstance(context, dict) else {}
    runtime = str(context.get("runtime") or "hermes").strip() or "hermes"
    profile_id = str(context.get("profile_id") or "default").strip() or "default"
    session_id = str(payload.get("session_id") or context.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required for harness command")
    return {
        "runtime": runtime,
        "profile_id": profile_id,
        "session_id": session_id,
        "turn_id": str(payload.get("turn_id") or context.get("turn_id") or "").strip(),
        "message_id": str(payload.get("message_id") or "").strip(),
        "application_id": str(context.get("application_id") or "").strip(),
        "run_id": str(context.get("run_id") or "").strip(),
    }


class HarnessCommandStore:
    def __init__(self, database: Database):
        self.db = database
        self.db.migrate()

    @staticmethod
    def idempotency_key(payload: dict[str, Any]) -> str:
        context = _normalised_context(payload)
        external_id = context["message_id"] or context["turn_id"]
        if not external_id:
            external_id = hashlib.sha256(
                str(payload.get("message") or "").strip().encode("utf-8")
            ).hexdigest()
        raw = "\x1f".join((context["runtime"], context["profile_id"], context["session_id"], external_id))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = _normalised_context(payload)
        message = " ".join(str(payload.get("message") or "").split())
        if not message:
            raise ValueError("message is required for harness command")
        key = self.idempotency_key(payload)
        now = _now()
        with self.db.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT * FROM harness_commands WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing is not None:
                return {**dict(existing), "deduplicated": True}
            command_id = f"hcmd_{uuid4().hex}"
            conn.execute(
                """INSERT INTO harness_commands (
                    command_id, idempotency_key, runtime, profile_id, session_id,
                    turn_id, message_id, message, application_id, run_id, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
                (
                    command_id, key, context["runtime"], context["profile_id"],
                    context["session_id"], context["turn_id"] or None,
                    context["message_id"] or None, message,
                    context["application_id"] or None, context["run_id"] or None,
                    now, now,
                ),
            )
            row = conn.execute("SELECT * FROM harness_commands WHERE command_id = ?", (command_id,)).fetchone()
        return {**dict(row), "deduplicated": False}

    def get(self, command_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT * FROM harness_commands WHERE command_id = ?", (command_id,))

    def claim(self, command_id: str, *, worker_id: str, ttl_seconds: int = 900) -> dict[str, Any] | None:
        now = _now()
        expiry = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
        with self.db.transaction(immediate=True) as conn:
            row = conn.execute("SELECT * FROM harness_commands WHERE command_id = ?", (command_id,)).fetchone()
            if row is None:
                return None
            current = dict(row)
            if current["status"] in FINAL_STATUSES:
                return current
            if current["status"] == "running" and str(current.get("claim_expires_at") or "") > now:
                return None
            conn.execute(
                """UPDATE harness_commands SET status = 'running', claimed_by = ?,
                   claim_expires_at = ?, updated_at = ? WHERE command_id = ?""",
                (worker_id, expiry, now, command_id),
            )
            claimed = conn.execute("SELECT * FROM harness_commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(claimed)

    def finish(self, command_id: str, *, status: str, result: dict[str, Any], reply_text: str | None = None) -> dict[str, Any]:
        if status not in FINAL_STATUSES:
            raise ValueError(f"invalid final harness command status: {status}")
        now = _now()
        blocker = str(result.get("blocker_reason") or "").strip() or None
        with self.db.transaction(immediate=True) as conn:
            conn.execute(
                """UPDATE harness_commands
                   SET status = ?, result_json = ?, reply_text = ?, blocker_reason = ?,
                       claimed_by = NULL, claim_expires_at = NULL, updated_at = ?, completed_at = ?
                   WHERE command_id = ?""",
                (status, json.dumps(result, ensure_ascii=False, sort_keys=True), reply_text, blocker, now, now, command_id),
            )
            row = conn.execute("SELECT * FROM harness_commands WHERE command_id = ?", (command_id,)).fetchone()
        if row is None:
            raise ValueError("harness command does not exist")
        return dict(row)
