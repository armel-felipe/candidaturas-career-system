from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from career.services.database import Database


MAX_METADATA_BYTES = 4096
RUN_STATUSES = frozenset({"running", "completed", "blocked", "cancelled", "failed"})


class RuntimeControl:
    """Bounded operational records for workers and agent context pressure."""

    def __init__(self, database: Database):
        self.database = database

    def register_worker(
        self,
        worker_id: str,
        *,
        runtime: str,
        profile_id: str | None = None,
        host: str | None = None,
        pid: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        worker_id = self._required_text(worker_id, "worker_id")
        runtime = self._required_text(runtime, "runtime")
        metadata_json = self._bounded_json(metadata or {}, "metadata")
        now = self._now()
        host = host or platform.node() or "unknown-host"
        with self.database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT INTO runtime_workers
                   (worker_id, runtime, profile_id, host, pid, status,
                    first_seen, last_seen, metadata_json)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                   ON CONFLICT(worker_id) DO UPDATE SET
                       runtime = excluded.runtime,
                       profile_id = excluded.profile_id,
                       host = excluded.host,
                       pid = excluded.pid,
                       status = 'active',
                       last_seen = excluded.last_seen,
                       metadata_json = excluded.metadata_json""",
                (worker_id, runtime, profile_id, host, pid, now, now, metadata_json),
            )
        return {
            "worker_id": worker_id,
            "runtime": runtime,
            "profile_id": profile_id,
            "host": host,
            "pid": pid,
            "first_seen": self._worker_first_seen(worker_id),
            "last_seen": now,
        }

    def start_run(
        self,
        worker_id: str,
        *,
        run_id: str | None = None,
        application_id: str | None = None,
        node_id: str | None = None,
        session_id: str | None = None,
        request_bytes: int | None = None,
        request_tokens: int | None = None,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_metric(request_bytes, "request_bytes")
        self._validate_metric(request_tokens, "request_tokens")
        metadata_json = self._bounded_json(metadata or {}, "metadata")
        runtime_run_id = f"runtime_{uuid4().hex}"
        now = self._now()
        with self.database.transaction(immediate=True) as conn:
            worker = conn.execute(
                "SELECT worker_id FROM runtime_workers WHERE worker_id = ?",
                (worker_id,),
            ).fetchone()
            if worker is None:
                raise KeyError(f"unknown runtime worker: {worker_id}")
            conn.execute(
                """INSERT INTO runtime_runs
                   (runtime_run_id, worker_id, run_id, application_id, node_id,
                    session_id, source, status, started_at, request_bytes,
                    request_tokens, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)""",
                (
                    runtime_run_id,
                    worker_id,
                    run_id,
                    application_id,
                    node_id,
                    session_id,
                    source,
                    now,
                    request_bytes,
                    request_tokens,
                    metadata_json,
                ),
            )
        return {"runtime_run_id": runtime_run_id, "worker_id": worker_id, "status": "running", "started_at": now}

    def record_context_observation(
        self,
        runtime_run_id: str,
        *,
        context_tokens: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        tool_calls: int | None = None,
        history_messages: int | None = None,
        request_bytes: int | None = None,
        source: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for value, name in (
            (context_tokens, "context_tokens"),
            (input_tokens, "input_tokens"),
            (output_tokens, "output_tokens"),
            (tool_calls, "tool_calls"),
            (history_messages, "history_messages"),
            (request_bytes, "request_bytes"),
        ):
            self._validate_metric(value, name)
        details_json = self._bounded_json(details or {}, "details")
        observed_at = self._now()
        with self.database.transaction(immediate=True) as conn:
            run = conn.execute(
                "SELECT runtime_run_id FROM runtime_runs WHERE runtime_run_id = ?",
                (runtime_run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(f"unknown runtime run: {runtime_run_id}")
            cursor = conn.execute(
                """INSERT INTO runtime_observations
                   (runtime_run_id, observed_at, context_tokens, input_tokens,
                    output_tokens, tool_calls, history_messages, request_bytes,
                    source, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    runtime_run_id,
                    observed_at,
                    context_tokens,
                    input_tokens,
                    output_tokens,
                    tool_calls,
                    history_messages,
                    request_bytes,
                    source,
                    details_json,
                ),
            )
        return {
            "observation_id": int(cursor.lastrowid),
            "runtime_run_id": runtime_run_id,
            "observed_at": observed_at,
        }

    def finish_run(
        self,
        runtime_run_id: str,
        *,
        status: str,
        error: str | None = None,
        output_bytes: int | None = None,
    ) -> dict[str, Any]:
        if status not in RUN_STATUSES - {"running"}:
            raise ValueError(f"invalid terminal runtime status: {status}")
        self._validate_metric(output_bytes, "output_bytes")
        finished_at = self._now()
        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                """UPDATE runtime_runs
                   SET status = ?, finished_at = ?, error = ?, output_bytes = ?
                   WHERE runtime_run_id = ? AND status = 'running'""",
                (status, finished_at, error, output_bytes, runtime_run_id),
            ).rowcount
            if updated != 1:
                exists = conn.execute(
                    "SELECT runtime_run_id FROM runtime_runs WHERE runtime_run_id = ?",
                    (runtime_run_id,),
                ).fetchone()
                if exists is None:
                    raise KeyError(f"unknown runtime run: {runtime_run_id}")
                raise ValueError(f"runtime run is already terminal: {runtime_run_id}")
        return {"runtime_run_id": runtime_run_id, "status": status, "finished_at": finished_at}

    def finish_worker(self, worker_id: str, *, status: str = "inactive") -> dict[str, Any]:
        """Mark a short-lived worker inactive after its run has ended."""
        worker_id = self._required_text(worker_id, "worker_id")
        status = self._required_text(status, "status")
        finished_at = self._now()
        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                "UPDATE runtime_workers SET status = ?, last_seen = ? WHERE worker_id = ?",
                (status, finished_at, worker_id),
            ).rowcount
            if updated != 1:
                raise KeyError(f"unknown runtime worker: {worker_id}")
        return {"worker_id": worker_id, "status": status, "last_seen": finished_at}

    def _worker_first_seen(self, worker_id: str) -> str:
        row = self.database.fetch_one(
            "SELECT first_seen FROM runtime_workers WHERE worker_id = ?", (worker_id,)
        )
        if row is None:
            raise KeyError(f"unknown runtime worker: {worker_id}")
        return str(row["first_seen"])

    @staticmethod
    def _required_text(value: str, name: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError(f"{name} is required")
        return value

    @staticmethod
    def _validate_metric(value: int | None, name: str) -> None:
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValueError(f"{name} must be non-negative integer or None")

    @staticmethod
    def _bounded_json(value: dict[str, Any], name: str) -> str:
        try:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
            raise ValueError(f"{name} exceeds {MAX_METADATA_BYTES} bytes")
        return encoded

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
