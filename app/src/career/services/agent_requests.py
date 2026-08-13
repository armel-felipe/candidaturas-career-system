from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.cells.contracts import CELL_CONTRACTS
from career.services.agent_contracts import CONTRACTS
from career.services.database import Database
from career.utils import write_json


class AgentRequestBuilder:
    def __init__(self, database: Database):
        self._db = database

    def build(self, contract_name: str, application_id: str) -> dict[str, Any] | None:
        contract = CONTRACTS.get(contract_name)
        if contract is None:
            return None

        app = self._db.fetch_one(
            "SELECT company, role FROM applications WHERE id = ?",
            (application_id,),
        )

        return {
            "contract": contract,
            "contract_name": contract_name,
            "application_id": application_id,
            "company": app["company"] if app else None,
            "role": app["role"] if app else None,
            "inputs": list(contract["inputs"]),
            "outputs": list(contract["outputs"]),
            "rules": list(contract["rules"]),
        }


class CellRequestBuilder:
    """Build and persist the bounded request projection for one cell attempt."""

    DEFAULT_MAX_BYTES = 128 * 1024

    def __init__(self, database: Database, *, max_bytes: int = DEFAULT_MAX_BYTES):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._db = database
        self.max_bytes = max_bytes

    def build(self, *, run_id: str, node_id: str, attempt: int) -> dict[str, Any]:
        contract = CELL_CONTRACTS.get(node_id)
        if contract is None:
            raise KeyError(f"unknown cell contract: {node_id}")
        run = self._db.fetch_one(
            "SELECT application_id FROM application_runs WHERE run_id = ?", (run_id,)
        )
        if run is None:
            raise KeyError(f"unknown application run: {run_id}")
        inputs = self._db.fetch_all(
            """SELECT input_name, source_kind, source_node_id, source_attempt,
                      source_id, version, path, content_hash, required
               FROM cell_inputs
               WHERE run_id = ? AND node_id = ? AND attempt = ?
               ORDER BY input_name""",
            (run_id, node_id, attempt),
        )
        payload = {
            "kind": "cell_request",
            "contract": {
                "node_id": contract.node_id,
                "version": contract.version,
                "requires": list(contract.requires),
                "produces": list(contract.produces),
                "validators": list(contract.validators),
                "resources": list(contract.resources),
                "max_attempts": contract.max_attempts,
            },
            "application_id": run["application_id"],
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "inputs": inputs,
            "limits": {"target_context_tokens": 12000, "hard_context_tokens": 32000},
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_bytes = len(payload_json.encode("utf-8"))
        if payload_bytes > self.max_bytes:
            raise ValueError(
                f"cell request exceeds maximum bytes: {payload_bytes}>{self.max_bytes}"
            )
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        with self._db.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT payload_hash, payload_json FROM cell_requests "
                "WHERE run_id = ? AND node_id = ? AND attempt = ?",
                (run_id, node_id, attempt),
            ).fetchone()
            if existing is not None:
                if existing["payload_hash"] == payload_hash:
                    return json.loads(existing["payload_json"])
                attempt_state = conn.execute(
                    "SELECT status FROM cell_attempts "
                    "WHERE run_id = ? AND node_id = ? AND attempt = ?",
                    (run_id, node_id, attempt),
                ).fetchone()
                if not attempt_state or attempt_state["status"] != "reserved":
                    raise ValueError("cell request projection is immutable")
                conn.execute(
                    """UPDATE cell_requests
                       SET payload_json = ?, payload_hash = ?, payload_bytes = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                    (
                        payload_json,
                        payload_hash,
                        payload_bytes,
                        run_id,
                        node_id,
                        attempt,
                    ),
                )
                return payload
            conn.execute(
                """INSERT INTO cell_requests
                   (request_id, run_id, node_id, attempt, contract_version,
                    payload_json, payload_hash, payload_bytes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    uuid4().hex,
                    run_id,
                    node_id,
                    attempt,
                    contract.version,
                    payload_json,
                    payload_hash,
                    payload_bytes,
                ),
            )
        return payload

    @staticmethod
    def materialize(payload: dict[str, Any], attempt_dir: Path) -> tuple[Path, Path]:
        """Write only the bounded projection, never source file contents."""
        attempt_dir.mkdir(parents=True, exist_ok=True)
        request_json = attempt_dir / "request.json"
        request_md = attempt_dir / "request.md"
        write_json(request_json, payload)
        contract = payload["contract"]
        lines = [
            f"# Cell request: {payload['node_id']}",
            "",
            f"- application_id: `{payload['application_id']}`",
            f"- run_id: `{payload['run_id']}`",
            f"- attempt: `{payload['attempt']}`",
            f"- contract_version: `{contract['version']}`",
            "",
            "## Inputs",
        ]
        for item in payload["inputs"]:
            lines.append(
                f"- `{item['input_name']}` — {item['source_kind']} — "
                f"`{item['content_hash']}` — `{item.get('path') or 'record'}`"
            )
        request_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return request_json, request_md
