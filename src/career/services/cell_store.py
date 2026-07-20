from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from career.services.database import Database


class CellStore:
    """Transactional persistence for application-scoped cellular runs."""

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
        worker_id: str | None = None,
        detail: Any | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        detail_json = self._json(detail) if detail is not None else None
        attempt_params: list[Any] = [status, now, detail_json, run_id, node_id, attempt]
        worker_clause = ""
        if worker_id is not None:
            worker_clause = " AND worker_id = ?"
            attempt_params.append(worker_id)

        with self.database.transaction(immediate=True) as conn:
            updated = conn.execute(
                f"""UPDATE cell_attempts
                    SET status = ?, finished_at = ?, detail_json = ?
                    WHERE run_id = ? AND node_id = ? AND attempt = ?{worker_clause}""",
                attempt_params,
            ).rowcount
            if updated != 1:
                raise KeyError(f"unknown or unowned cell attempt: {run_id}/{node_id}/{attempt}")
            conn.execute(
                """UPDATE cell_nodes
                   SET status = ?, reserved_by = NULL, reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ? AND latest_attempt = ?""",
                (status, now, run_id, node_id, attempt),
            )

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
