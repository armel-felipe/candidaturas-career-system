from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

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
                """SELECT status, reservation_expires_at, latest_attempt
                   FROM cell_nodes WHERE run_id = ? AND node_id = ?""",
                (run_id, node_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown cell node: {run_id}/{node_id}")

            active_reservation = (
                row["status"] in {"reserved", "running"}
                and row["reservation_expires_at"] is not None
                and row["reservation_expires_at"] > now
            )
            if active_reservation or row["status"] not in {"planned", "repairing", "reserved", "running"}:
                return {"status": "busy"}

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

        return {
            "status": "reserved",
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "worker_id": worker_id,
            "expires_at": expires_at,
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
    ) -> dict[str, Any]:
        """Finish only the active attempt owned by ``worker_id``.

        Receipts intentionally store a bounded, structured pointer to output
        rather than agent output or other arbitrary payloads.
        """
        receipt_json = self._receipt_json(status, receipt)

        with self.database.transaction(immediate=True) as conn:
            now = self._now()
            node_updated = conn.execute(
                """UPDATE cell_nodes
                   SET status = ?, reserved_by = NULL, reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ? AND latest_attempt = ?
                     AND reserved_by = ? AND status IN ('reserved', 'running')
                     AND reservation_expires_at > ?""",
                (status, now, run_id, node_id, attempt, worker_id, now),
            ).rowcount
            if node_updated != 1:
                raise RuntimeError(f"stale or unowned cell attempt: {run_id}/{node_id}/{attempt}")

            attempt_updated = conn.execute(
                """UPDATE cell_attempts
                   SET status = ?, finished_at = ?, detail_json = ?
                   WHERE run_id = ? AND node_id = ? AND attempt = ? AND worker_id = ?
                     AND status IN ('reserved', 'running') AND finished_at IS NULL""",
                (status, now, receipt_json, run_id, node_id, attempt, worker_id),
            ).rowcount
            if attempt_updated != 1:
                raise RuntimeError(f"stale or unowned cell attempt: {run_id}/{node_id}/{attempt}")

        return {"run_id": run_id, "node_id": node_id, "attempt": attempt, "status": status}

    def acquire_resource_lock(
        self,
        resource_name: str,
        worker_id: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        now = self._now()
        expires_at = self._expires_at(lease_seconds)

        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                """INSERT INTO resource_locks (resource_name, worker_id, acquired_at, expires_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(resource_name) DO UPDATE SET
                       worker_id = excluded.worker_id,
                       acquired_at = excluded.acquired_at,
                       expires_at = excluded.expires_at
                   WHERE resource_locks.expires_at <= excluded.acquired_at
                      OR resource_locks.worker_id = excluded.worker_id""",
                (resource_name, worker_id, now, expires_at),
            ).rowcount
            lock = conn.execute(
                """SELECT worker_id, expires_at FROM resource_locks
                   WHERE resource_name = ?""",
                (resource_name,),
            ).fetchone()

        return {
            "acquired": updated == 1 and lock["worker_id"] == worker_id,
            "resource_name": resource_name,
            "worker_id": lock["worker_id"],
            "expires_at": lock["expires_at"],
        }

    def release_resource_lock(self, resource_name: str, worker_id: str) -> dict[str, Any]:
        with self.database.transaction(immediate=True) as conn:
            released = conn.execute(
                "DELETE FROM resource_locks WHERE resource_name = ? AND worker_id = ?",
                (resource_name, worker_id),
            ).rowcount == 1
        return {"released": released, "resource_name": resource_name}

    def list_ready_nodes(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """SELECT node_id, status, requires_json, latest_attempt
               FROM cell_nodes
               WHERE run_id = ? AND status IN ('planned', 'repairing')
               ORDER BY node_id""",
            (run_id,),
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
