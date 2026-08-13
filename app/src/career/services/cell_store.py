from __future__ import annotations

import json
import hashlib
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from career.services.database import Database


class CellStore:
    """Transactional persistence for application-scoped cellular runs."""

    _FINISH_STATUSES = frozenset({"repairing", "validated", "blocked", "superseded", "cancelled"})
    _ACTIVE_ATTEMPT_STATUSES = frozenset({"reserved", "running"})
    _RECEIPT_KEYS = frozenset({"status", "paths", "hashes", "metadata"})
    _MAX_RECEIPT_BYTES = 4096
    _MAX_RECEIPT_PATHS = 16
    _MAX_RECEIPT_HASHES = 16
    _MAX_RECEIPT_METADATA = 16
    _MAX_PATH_LENGTH = 512
    _MAX_METADATA_KEY_LENGTH = 64
    _MAX_METADATA_STRING_LENGTH = 256
    _SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
    _MAX_INPUTS = 64
    _MAX_INPUT_NAME_LENGTH = 128
    _MAX_INPUT_STRING_LENGTH = 512
    _MAX_HANDOVER_BYTES = 16 * 1024
    _MAX_RECEIPT_DETAILS_BYTES = 4096

    def __init__(self, database: Database):
        self.database = database

    def create_run(self, application_id: str, run_id: str, *, graph: Any) -> dict[str, Any]:
        now = self._now()
        graph_json = self._json(graph)
        nodes = list(self._nodes_from_graph(graph))

        with self.database.transaction() as conn:
            conn.execute(
                """INSERT INTO application_runs
                   (run_id, application_id, graph_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, application_id, graph_json, now, now),
            )
            conn.executemany(
                """INSERT INTO cell_nodes
                   (run_id, node_id, requires_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (run_id, node_id, self._json(requires), now, now)
                    for node_id, requires in nodes
                ],
            )

        return {"run_id": run_id, "application_id": application_id, "status": "planned"}

    def reserve_node(
        self,
        run_id: str,
        node_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        now = self._now()
        expires_at = self._expires_at(lease_seconds)

        with self.database.transaction(immediate=True) as conn:
            row = conn.execute(
                """SELECT status, reservation_expires_at, latest_attempt, requires_json
                   FROM cell_nodes WHERE run_id = ? AND node_id = ?""",
                (run_id, node_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown cell node: {run_id}/{node_id}")

            requirements = json.loads(row["requires_json"])
            if requirements:
                placeholders = ",".join("?" for _ in requirements)
                dependency_rows = conn.execute(
                    f"""SELECT node_id, status FROM cell_nodes
                        WHERE run_id = ? AND node_id IN ({placeholders})""",
                    (run_id, *requirements),
                ).fetchall()
                dependency_statuses = {
                    item["node_id"]: item["status"] for item in dependency_rows
                }
                if any(
                    dependency_statuses.get(required) != "validated"
                    for required in requirements
                ):
                    return {"status": "busy"}

            active_reservation = (
                row["status"] in {"reserved", "running"}
                and row["reservation_expires_at"] is not None
                and row["reservation_expires_at"] > now
            )
            if active_reservation or row["status"] not in {"planned", "repairing", "reserved", "running"}:
                return {"status": "busy"}

            if row["status"] in self._ACTIVE_ATTEMPT_STATUSES:
                stale_attempt = int(row["latest_attempt"])
                conn.execute(
                    """UPDATE cell_attempts
                       SET status = 'cancelled', finished_at = ?, detail_json = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?
                         AND status IN ('reserved', 'running') AND finished_at IS NULL""",
                    (
                        now,
                        self._json(
                            {
                                "status": "cancelled",
                                "paths": [],
                                "hashes": {},
                                "metadata": {"reason": "lease_expired"},
                            }
                        ),
                        run_id,
                        node_id,
                        stale_attempt,
                    ),
                )

            attempt = int(row["latest_attempt"]) + 1
            conn.execute(
                """UPDATE cell_nodes
                   SET status = 'reserved', reserved_by = ?, reservation_expires_at = ?,
                       latest_attempt = ?, updated_at = ?
                   WHERE run_id = ? AND node_id = ?""",
                (worker_id, expires_at, attempt, now, run_id, node_id),
            )
            conn.execute(
                """INSERT INTO cell_attempts
                   (run_id, node_id, attempt, worker_id, status, created_at)
                   VALUES (?, ?, ?, ?, 'reserved', ?)""",
                (run_id, node_id, attempt, worker_id, now),
            )
            conn.execute(
                "UPDATE application_runs SET status = 'running', updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )

        return {
            "status": "reserved",
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "worker_id": worker_id,
            "expires_at": expires_at,
        }

    def renew_node_reservation(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        worker_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        now = self._now()
        expires_at = self._expires_at(lease_seconds)
        with self.database.transaction(immediate=True) as conn:
            renewed = conn.execute(
                """UPDATE cell_nodes
                   SET reservation_expires_at = ?, updated_at = ?
                   WHERE run_id = ? AND node_id = ? AND latest_attempt = ?
                     AND reserved_by = ? AND status IN ('reserved', 'running')
                     AND reservation_expires_at > ?""",
                (expires_at, now, run_id, node_id, attempt, worker_id, now),
            ).rowcount == 1
        return {
            "renewed": renewed,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "expires_at": expires_at if renewed else None,
        }

    def register_attempt_inputs(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist the immutable input references before cell execution."""
        normalized = self._normalize_attempt_inputs(inputs)
        with self.database.transaction(immediate=True) as conn:
            active = conn.execute(
                """SELECT status, inputs_registered_at FROM cell_attempts
                   WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                (run_id, node_id, attempt),
            ).fetchone()
            if active is None:
                raise KeyError(f"unknown cell attempt: {run_id}/{node_id}/{attempt}")
            existing_rows = conn.execute(
                """SELECT input_name, source_kind, source_node_id, source_attempt,
                          source_id, version, path, content_hash, required
                   FROM cell_inputs
                   WHERE run_id = ? AND node_id = ? AND attempt = ?
                   ORDER BY input_name""",
                (run_id, node_id, attempt),
            ).fetchall()
            existing = [dict(row) for row in existing_rows]
            rewrite_inputs = False
            if active["inputs_registered_at"] is not None and existing != normalized:
                if active["status"] != "reserved":
                    raise ValueError("attempt inputs are immutable")
                conn.execute(
                    """DELETE FROM cell_inputs
                       WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                    (run_id, node_id, attempt),
                )
                rewrite_inputs = True
            if active["inputs_registered_at"] is None or rewrite_inputs:
                now = self._now()
                conn.executemany(
                    """INSERT INTO cell_inputs
                       (run_id, node_id, attempt, input_name, source_kind,
                        source_node_id, source_attempt, source_id, version, path,
                        content_hash, required, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            run_id,
                            node_id,
                            attempt,
                            item["input_name"],
                            item["source_kind"],
                            item["source_node_id"],
                            item["source_attempt"],
                            item["source_id"],
                            item["version"],
                            item["path"],
                            item["content_hash"],
                            int(item["required"]),
                            now,
                        )
                        for item in normalized
                    ],
                )
                conn.execute(
                    """UPDATE cell_attempts SET inputs_registered_at = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                    (now, run_id, node_id, attempt),
                )
        return {"run_id": run_id, "node_id": node_id, "attempt": attempt, "count": len(normalized)}

    def mark_attempt_running(
        self, run_id: str, node_id: str, attempt: int, worker_id: str
    ) -> bool:
        """Freeze the prepared input set immediately before invoking a handler."""
        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                """UPDATE cell_attempts SET status = 'running'
                   WHERE run_id = ? AND node_id = ? AND attempt = ?
                     AND worker_id = ? AND status = 'reserved'
                     AND inputs_registered_at IS NOT NULL""",
                (run_id, node_id, attempt, worker_id),
            ).rowcount
        return updated == 1

    def validate_attempt_inputs(
        self, run_id: str, node_id: str, attempt: int
    ) -> dict[str, Any]:
        """Verify registered input files still exist and retain their hashes."""
        rows = self.database.fetch_all(
            """SELECT input_name, path, content_hash, required
               FROM cell_inputs
               WHERE run_id = ? AND node_id = ? AND attempt = ?
               ORDER BY input_name""",
            (run_id, node_id, attempt),
        )
        problems: list[str] = []
        for row in rows:
            path_value = row.get("path")
            if not path_value:
                continue
            path = Path(str(path_value))
            if not path.is_file():
                if row["required"]:
                    problems.append(f"missing:{row['input_name']}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row["content_hash"]:
                problems.append(f"hash:{row['input_name']}")
        if problems:
            raise ValueError("input validation failed: " + ",".join(problems))
        return {"valid": True, "count": len(rows)}

    def cancel_expired_reservation(
        self, run_id: str, node_id: str, attempt: int, worker_id: str
    ) -> dict[str, Any]:
        now = self._now()
        receipt = self._receipt_json(
            "cancelled",
            {
                "status": "cancelled",
                "paths": [],
                "hashes": {},
                "metadata": {"reason": "lease_expired"},
            },
        )
        with self.database.transaction(immediate=True) as conn:
            cancelled = conn.execute(
                """UPDATE cell_nodes
                   SET status = 'planned', reserved_by = NULL,
                       reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ? AND latest_attempt = ?
                     AND reserved_by = ? AND status IN ('reserved', 'running')
                     AND reservation_expires_at <= ?""",
                (now, run_id, node_id, attempt, worker_id, now),
            ).rowcount == 1
            if cancelled:
                conn.execute(
                    """UPDATE cell_attempts
                       SET status = 'cancelled', finished_at = ?, detail_json = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?
                         AND worker_id = ? AND status IN ('reserved', 'running')
                         AND finished_at IS NULL""",
                    (now, receipt, run_id, node_id, attempt, worker_id),
                )
        return {"cancelled": cancelled, "run_id": run_id, "node_id": node_id, "attempt": attempt}

    def defer_attempt(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        worker_id: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Return an owned attempt to planned state after transient contention."""
        now = self._now()
        receipt = self._receipt_json(
            "cancelled",
            {
                "status": "cancelled",
                "paths": [],
                "hashes": {},
                "metadata": {"reason": str(reason)[: self._MAX_METADATA_STRING_LENGTH]},
            },
        )
        with self.database.transaction(immediate=True) as conn:
            deferred = conn.execute(
                """UPDATE cell_nodes
                   SET status = 'planned', reserved_by = NULL,
                       reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ? AND latest_attempt = ?
                     AND reserved_by = ? AND status IN ('reserved', 'running')
                     AND reservation_expires_at > ?""",
                (now, run_id, node_id, attempt, worker_id, now),
            ).rowcount == 1
            if deferred:
                attempt_updated = conn.execute(
                    """UPDATE cell_attempts
                       SET status = 'cancelled', finished_at = ?, detail_json = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?
                         AND worker_id = ? AND status IN ('reserved', 'running')
                         AND finished_at IS NULL""",
                    (now, receipt, run_id, node_id, attempt, worker_id),
                ).rowcount
                if attempt_updated != 1:
                    raise RuntimeError(
                        f"stale or unowned cell attempt: {run_id}/{node_id}/{attempt}"
                    )
        return {
            "deferred": deferred,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
        }

    def finish_attempt(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        status: str,
        *,
        worker_id: str,
        receipt: Mapping[str, Any],
        workspace_owner: str = "",
        workspace_fence_token: int | None = None,
        resource_leases: Iterable[Mapping[str, Any]] = (),
        published_artifacts: Iterable[Mapping[str, Any]] = (),
        handover: Mapping[str, Any] | None = None,
        handover_path: str | None = None,
        validation_receipts: Iterable[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Finish only the active attempt owned by ``worker_id``.

        Receipts intentionally store a bounded, structured pointer to output
        rather than agent output or other arbitrary payloads.
        """
        receipt_json = self._receipt_json(status, receipt)
        leases = tuple(resource_leases)
        artifacts = self._published_artifacts(status, receipt, published_artifacts)
        handover_record = self._handover_record(
            run_id, node_id, attempt, status, handover or {}, handover_path
        )
        validation_records = self._validation_records(
            run_id, node_id, attempt, validation_receipts
        )

        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            with self.database.transaction(immediate=True) as conn:
                now = self._now()
                if workspace_owner:
                    if workspace_fence_token is None:
                        raise ValueError(
                            "workspace fence token is required for terminal commit"
                        )
                    workspace_owned = conn.execute(
                        """SELECT 1 FROM workspace_leases
                           WHERE lease_name = 'authoritative-workspace'
                             AND worker_id = ? AND lease_epoch = ?
                             AND expires_at > ?""",
                        (workspace_owner, int(workspace_fence_token), now),
                    ).fetchone()
                    if workspace_owned is None:
                        raise RuntimeError("stale authoritative workspace lease")
                for lease in leases:
                    resource_name = str(lease.get("resource_name", ""))
                    lease_id = str(lease.get("lease_id", ""))
                    if not resource_name or not lease_id:
                        raise ValueError("resource lease requires resource_name and lease_id")
                    owned = conn.execute(
                        """SELECT 1 FROM resource_locks
                           WHERE resource_name = ? AND worker_id = ? AND lease_id = ?
                             AND expires_at > ?""",
                        (resource_name, worker_id, lease_id, now),
                    ).fetchone()
                    if owned is None:
                        raise RuntimeError(f"stale resource lease: {resource_name}")
                node_updated = conn.execute(
                    """UPDATE cell_nodes
                       SET status = ?, reserved_by = NULL, reservation_expires_at = NULL, updated_at = ?
                       WHERE run_id = ? AND node_id = ? AND latest_attempt = ?
                         AND reserved_by = ? AND status IN ('reserved', 'running')
                         AND reservation_expires_at > ?""",
                    (status, now, run_id, node_id, attempt, worker_id, now),
                ).rowcount
                if node_updated != 1:
                    raise RuntimeError(
                        f"stale or unowned cell attempt: {run_id}/{node_id}/{attempt}"
                    )

                attempt_updated = conn.execute(
                    """UPDATE cell_attempts
                       SET status = ?, finished_at = ?, detail_json = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ? AND worker_id = ?
                         AND status IN ('reserved', 'running') AND finished_at IS NULL""",
                    (status, now, receipt_json, run_id, node_id, attempt, worker_id),
                ).rowcount
                if attempt_updated != 1:
                    raise RuntimeError(
                        f"stale or unowned cell attempt: {run_id}/{node_id}/{attempt}"
                    )
                for artifact in artifacts:
                    conn.execute(
                        """INSERT INTO artifacts
                           (artifact_id, run_id, node_id, artifact_name, path, content_hash,
                            input_hash, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            artifact["artifact_id"],
                            run_id,
                            node_id,
                            artifact["artifact_name"],
                            artifact["path"],
                            artifact["sha256"],
                            artifact["input_hash"],
                            now,
                        ),
                    )
                if handover_record is not None:
                    conn.execute(
                        """INSERT INTO cell_handovers
                           (handover_id, run_id, node_id, attempt, status,
                            payload_json, payload_hash, path, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            handover_record["handover_id"],
                            run_id,
                            node_id,
                            attempt,
                            status,
                            handover_record["payload_json"],
                            handover_record["payload_hash"],
                            handover_record["path"],
                            now,
                        ),
                    )
                for item in validation_records:
                    conn.execute(
                        """INSERT INTO validation_receipts
                           (receipt_id, run_id, node_id, attempt, validator,
                            result, report_path, report_sha256, details_json, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            item["receipt_id"],
                            run_id,
                            node_id,
                            attempt,
                            item["validator"],
                            item["result"],
                            item["report_path"],
                            item["report_sha256"],
                            item["details_json"],
                            now,
                        ),
                    )
                if status == "blocked":
                    conn.execute(
                        "UPDATE application_runs SET status = 'blocked', updated_at = ? WHERE run_id = ?",
                        (now, run_id),
                    )

        return {"run_id": run_id, "node_id": node_id, "attempt": attempt, "status": status}

    @classmethod
    def _published_artifacts(
        cls,
        status: str,
        receipt: Mapping[str, Any],
        published_artifacts: Iterable[Mapping[str, Any]],
    ) -> tuple[dict[str, str | None], ...]:
        artifacts = tuple(published_artifacts)
        if status != "validated":
            if artifacts:
                raise ValueError("only validated attempts may record published artifacts")
            return ()

        normalized: list[dict[str, str | None]] = []
        receipt_paths = receipt["paths"]
        receipt_hashes = receipt["hashes"]
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise ValueError("published artifact must be a mapping")
            artifact_name = artifact.get("artifact_name")
            path = artifact.get("path")
            digest = artifact.get("sha256")
            inputs = artifact.get("inputs", {})
            if (
                not isinstance(artifact_name, str)
                or not artifact_name
                or not isinstance(path, str)
                or path not in receipt_paths
                or not isinstance(digest, str)
                or receipt_hashes.get(path) != digest
                or not cls._SHA256_RE.fullmatch(digest)
                or not isinstance(inputs, Mapping)
            ):
                raise ValueError("published artifact does not match the validated receipt")
            normalized.append(
                {
                    "artifact_id": hashlib.sha256(
                        f"{path}\0{digest}".encode("utf-8")
                    ).hexdigest(),
                    "artifact_name": artifact_name,
                    "path": path,
                    "sha256": digest,
                    "input_hash": hashlib.sha256(cls._json(inputs).encode("utf-8")).hexdigest(),
                }
            )
        return tuple(normalized)

    @classmethod
    def _normalize_attempt_inputs(
        cls, inputs: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        if not isinstance(inputs, Mapping):
            raise ValueError("attempt inputs must be a mapping")
        if len(inputs) > cls._MAX_INPUTS:
            raise ValueError("attempt inputs exceed maximum")
        normalized: list[dict[str, Any]] = []
        for raw_name, raw_value in inputs.items():
            name = str(raw_name)
            if not name or len(name) > cls._MAX_INPUT_NAME_LENGTH:
                raise ValueError("input name is invalid")
            if isinstance(raw_value, Path):
                path = raw_value.resolve()
                if not path.is_file():
                    raise ValueError(f"input path is not a file: {path}")
                value: Mapping[str, Any] = {"path": str(path)}
            elif isinstance(raw_value, Mapping):
                value = raw_value
                path = Path(str(value["path"])).resolve() if value.get("path") else None
            else:
                raise ValueError(f"input {name} must be a path or mapping")
            content_hash = str(value.get("sha256") or "")
            if path is not None and not content_hash:
                if not path.is_file():
                    raise ValueError(f"input path is not a file: {path}")
                content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if not cls._SHA256_RE.fullmatch(content_hash):
                raise ValueError(f"input {name} requires a SHA-256 hash")
            source_kind = str(value.get("source_kind") or "file")
            if len(source_kind) > cls._MAX_INPUT_STRING_LENGTH:
                raise ValueError("input source kind is too long")
            source_node_id = value.get("node_id", value.get("source_node_id"))
            source_attempt = value.get("attempt", value.get("source_attempt"))
            if source_attempt is not None:
                source_attempt = int(source_attempt)
                if source_attempt <= 0:
                    raise ValueError("input source attempt must be positive")
            normalized.append(
                {
                    "input_name": name,
                    "source_kind": source_kind,
                    "source_node_id": str(source_node_id) if source_node_id is not None else None,
                    "source_attempt": source_attempt,
                    "source_id": str(value["source_id"]) if value.get("source_id") is not None else None,
                    "version": str(value["version"]) if value.get("version") is not None else None,
                    "path": str(path) if path is not None else None,
                    "content_hash": content_hash,
                    "required": bool(value.get("required", True)),
                }
            )
        return sorted(normalized, key=lambda item: item["input_name"])

    @classmethod
    def _handover_record(
        cls,
        run_id: str,
        node_id: str,
        attempt: int,
        status: str,
        handover: Mapping[str, Any],
        handover_path: str | None,
    ) -> dict[str, Any] | None:
        if status not in {"validated", "blocked", "repairing", "cancelled", "superseded"}:
            return None
        if not isinstance(handover, Mapping):
            raise ValueError("handover must be a mapping")
        for field, expected in (("run_id", run_id), ("node_id", node_id), ("attempt", attempt)):
            if field in handover and str(handover[field]) != str(expected):
                raise ValueError(f"handover {field} does not match attempt")
        payload_json = cls._json(dict(handover))
        if len(payload_json.encode("utf-8")) > cls._MAX_HANDOVER_BYTES:
            raise ValueError("handover exceeds maximum size")
        return {
            "handover_id": uuid4().hex,
            "payload_json": payload_json,
            "payload_hash": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "path": str(handover_path) if handover_path else None,
        }

    @classmethod
    def _validation_records(
        cls,
        run_id: str,
        node_id: str,
        attempt: int,
        receipts: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in receipts:
            if not isinstance(raw, Mapping):
                raise ValueError("validation receipt must be a mapping")
            validator = str(raw.get("validator") or raw.get("command") or "").strip()
            result = str(raw.get("result") or "").strip()
            if not validator or not result:
                raise ValueError("validation receipt requires validator and result")
            report_path = raw.get("report_path")
            report_sha256 = raw.get("report_sha256")
            if report_sha256 is not None and not cls._SHA256_RE.fullmatch(str(report_sha256)):
                raise ValueError("validation receipt report hash is invalid")
            details = raw.get("details", {})
            details_json = cls._json(details)
            if len(details_json.encode("utf-8")) > cls._MAX_RECEIPT_DETAILS_BYTES:
                raise ValueError("validation receipt details exceed maximum size")
            normalized.append(
                {
                    "receipt_id": uuid4().hex,
                    "validator": validator,
                    "result": result,
                    "report_path": str(report_path) if report_path else None,
                    "report_sha256": str(report_sha256) if report_sha256 else None,
                    "details_json": details_json,
                }
            )
        return normalized

    def acquire_resource_lock(
        self,
        resource_name: str,
        worker_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        now = self._now()
        expires_at = self._expires_at(lease_seconds)
        lease_id = f"lease_{uuid4().hex}"

        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                """INSERT INTO resource_locks
                   (resource_name, worker_id, lease_id, acquired_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(resource_name) DO UPDATE SET
                       worker_id = excluded.worker_id,
                       lease_id = excluded.lease_id,
                       acquired_at = excluded.acquired_at,
                       expires_at = excluded.expires_at
                   WHERE resource_locks.expires_at <= excluded.acquired_at
                   """,
                (resource_name, worker_id, lease_id, now, expires_at),
            ).rowcount
            lock = conn.execute(
                """SELECT worker_id, lease_id, acquired_at, expires_at FROM resource_locks
                   WHERE resource_name = ?""",
                (resource_name,),
            ).fetchone()

        return {
            "acquired": updated == 1 and lock["worker_id"] == worker_id,
            "resource_name": resource_name,
            "worker_id": lock["worker_id"],
            "lease_id": lock["lease_id"],
            "acquired_at": lock["acquired_at"],
            "expires_at": lock["expires_at"],
        }

    def renew_resource_lock(
        self,
        resource_name: str,
        worker_id: str,
        lease_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        now = self._now()
        expires_at = self._expires_at(lease_seconds)
        with self.database.transaction(immediate=True) as conn:
            renewed = conn.execute(
                """UPDATE resource_locks SET expires_at = ?
                   WHERE resource_name = ? AND worker_id = ? AND lease_id = ?
                     AND expires_at > ?""",
                (expires_at, resource_name, worker_id, lease_id, now),
            ).rowcount == 1
        return {
            "renewed": renewed,
            "resource_name": resource_name,
            "lease_id": lease_id,
            "expires_at": expires_at if renewed else None,
        }

    def release_resource_lock(
        self, resource_name: str, worker_id: str, *, lease_id: str
    ) -> dict[str, Any]:
        with self.database.transaction(immediate=True) as conn:
            released = conn.execute(
                """DELETE FROM resource_locks
                   WHERE resource_name = ? AND worker_id = ? AND lease_id = ?""",
                (resource_name, worker_id, lease_id),
            ).rowcount == 1
        return {"released": released, "resource_name": resource_name}

    def list_ready_nodes(self, run_id: str) -> list[dict[str, Any]]:
        now = self._now()
        rows = self.database.fetch_all(
            """SELECT node_id, status, requires_json, latest_attempt
               FROM cell_nodes
               WHERE run_id = ? AND (
                   status IN ('planned', 'repairing')
                   OR (status IN ('reserved', 'running') AND reservation_expires_at <= ?)
               )
               ORDER BY node_id""",
            (run_id, now),
        )
        statuses = {
            row["node_id"]: row["status"]
            for row in self.database.fetch_all(
                "SELECT node_id, status FROM cell_nodes WHERE run_id = ?", (run_id,)
            )
        }
        ready: list[dict[str, Any]] = []
        for row in rows:
            requires = json.loads(row.pop("requires_json"))
            if all(statuses.get(required) == "validated" for required in requires):
                row["requires"] = requires
                ready.append(row)
        return ready

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def _expires_at(cls, lease_seconds: int) -> str:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        return (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _receipt_json(cls, status: str, receipt: Mapping[str, Any]) -> str:
        if status not in cls._FINISH_STATUSES:
            raise ValueError(f"invalid finish status: {status}")
        if not isinstance(receipt, Mapping) or set(receipt) != cls._RECEIPT_KEYS:
            raise ValueError("receipt must contain only status, paths, hashes, and metadata")
        if receipt["status"] != status:
            raise ValueError("receipt status must match finish status")

        paths = receipt["paths"]
        hashes = receipt["hashes"]
        metadata = receipt["metadata"]
        if not isinstance(paths, list) or len(paths) > cls._MAX_RECEIPT_PATHS:
            raise ValueError("receipt paths must be a bounded list")
        if any(not isinstance(path, str) or not path or len(path) > cls._MAX_PATH_LENGTH for path in paths):
            raise ValueError("receipt paths must be non-empty bounded strings")
        if not isinstance(hashes, Mapping) or len(hashes) > cls._MAX_RECEIPT_HASHES:
            raise ValueError("receipt hashes must be a bounded mapping")
        if any(
            not isinstance(path, str)
            or path not in paths
            or not isinstance(content_hash, str)
            or not cls._SHA256_RE.fullmatch(content_hash)
            for path, content_hash in hashes.items()
        ):
            raise ValueError("receipt hashes must be SHA-256 values for receipt paths")
        if not isinstance(metadata, Mapping) or len(metadata) > cls._MAX_RECEIPT_METADATA:
            raise ValueError("receipt metadata must be a bounded mapping")
        if any(
            not isinstance(key, str)
            or not key
            or len(key) > cls._MAX_METADATA_KEY_LENGTH
            or not cls._is_small_metadata_value(value)
            for key, value in metadata.items()
        ):
            raise ValueError("receipt metadata must contain only small scalar values")

        canonical_receipt = {
            "status": status,
            "paths": paths,
            "hashes": dict(hashes),
            "metadata": dict(metadata),
        }
        receipt_json = json.dumps(canonical_receipt, sort_keys=True, separators=(",", ":"))
        if len(receipt_json.encode("utf-8")) > cls._MAX_RECEIPT_BYTES:
            raise ValueError("receipt exceeds maximum size")
        return receipt_json

    @classmethod
    def _is_small_metadata_value(cls, value: Any) -> bool:
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        return isinstance(value, str) and len(value) <= cls._MAX_METADATA_STRING_LENGTH

    @staticmethod
    def _nodes_from_graph(graph: Any) -> Iterable[tuple[str, list[str]]]:
        nodes = graph.get("nodes", ()) if isinstance(graph, dict) else getattr(graph, "nodes", ())
        for node in nodes:
            if isinstance(node, str):
                yield node, []
                continue
            if isinstance(node, dict):
                node_id = node.get("id", node.get("node_id"))
                requires = node.get("requires", node.get("dependencies", ()))
            else:
                node_id = getattr(node, "node_id", getattr(node, "id", None))
                requires = getattr(node, "requires", getattr(node, "dependencies", ()))
            if not node_id:
                raise ValueError("every graph node requires an id")
            yield str(node_id), list(requires)
