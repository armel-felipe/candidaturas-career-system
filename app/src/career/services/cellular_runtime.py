from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.services.agent_requests import CellRequestBuilder
from career.services.database import Database
from career.services.runtime_control import RuntimeControl


class CellularRuntime:
    """Bridge one fresh cellular process to the bounded runtime ledger."""

    def __init__(self, database: Database, *, root: Path, worker_id: str):
        self.database = database
        self.root = root.resolve()
        self.worker_id = worker_id
        self.control = RuntimeControl(database)

    def begin(self, request_json: Path, payload: dict[str, Any]) -> dict[str, Any]:
        builder = CellRequestBuilder(self.database)
        persisted = builder.validate_materialized(
            str(payload["run_id"]),
            str(payload["node_id"]),
            int(payload["attempt"]),
            request_json,
        )
        if persisted != payload:
            raise ValueError("cellular runtime request differs from SQLite projection")
        request_row = self.database.fetch_one(
            "SELECT payload_hash FROM cell_requests "
            "WHERE run_id = ? AND node_id = ? AND attempt = ?",
            (str(payload["run_id"]), str(payload["node_id"]), int(payload["attempt"])),
        )
        if request_row is None:
            raise KeyError("cellular runtime request is not persisted")
        request_bytes = len(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        request_tokens = max(1, math.ceil(request_bytes / 4))
        self.control.register_worker(
            self.worker_id,
            runtime="controlled-harness",
            pid=None,
            metadata={"root": str(self.root), "cellular": True},
        )
        runtime_run = self.control.start_run(
            self.worker_id,
            run_id=str(payload["run_id"]),
            application_id=str(payload["application_id"]),
            node_id=str(payload["node_id"]),
            session_id=f"cell-session-{uuid4().hex}",
            request_bytes=request_bytes,
            request_tokens=request_tokens,
            source="cellular-harness",
            metadata={"fresh_process": True, "attempt": int(payload["attempt"])},
        )
        self.control.record_context_observation(
            runtime_run["runtime_run_id"],
            context_tokens=request_tokens,
            input_tokens=request_tokens,
            history_messages=0,
            tool_calls=0,
            request_bytes=request_bytes,
            source="cellular-request",
            details={"session_boundary": "fresh_process", "request_kind": "cell_request"},
        )
        return {
            **runtime_run,
            "request_hash": str(request_row["payload_hash"]),
            "request_bytes": request_bytes,
            "request_tokens": request_tokens,
        }

    def observe(
        self,
        runtime_run_id: str,
        *,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        isolation_status: str = "ok",
    ) -> dict[str, Any]:
        output_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
        output_tokens = math.ceil(output_bytes / 4) if output_bytes else 0
        return self.control.record_context_observation(
            runtime_run_id,
            context_tokens=output_tokens,
            output_tokens=output_tokens,
            history_messages=0,
            tool_calls=0,
            source="cellular-result",
            details={
                "returncode": int(returncode),
                "isolation_status": str(isolation_status),
            },
        )

    def finish(
        self,
        runtime_run_id: str,
        *,
        status: str,
        error: str | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> dict[str, Any]:
        output_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
        return self.control.finish_run(
            runtime_run_id,
            status=status,
            error=error,
            output_bytes=output_bytes,
        )
