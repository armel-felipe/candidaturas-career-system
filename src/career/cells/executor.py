from __future__ import annotations

import base64
import hashlib
import json
import threading
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.cells.capabilities import CapabilitySet, CapabilityViolation
from career.cells.contracts import CELL_CONTRACTS, CellContract
from career.cells.handlers import (
    CellExecutionContext,
    CellHandler,
    CellOutput,
    CellValidator,
    ValidatorResult,
)
from career.cells.manifests import ManifestStore, PublishedArtifact, RunCompletion
from career.cells.planner import NodePlan, RunPlan, compile_run_plan
from career.cells.serial import serial_stage_report
from career.services.application_context import (
    APPLICATIONS_DIR,
    ApplicationPaths,
    WorkspaceLease,
    paths_for,
    workspace_owner_from_env,
)
from career.services.cell_store import CellStore
from career.services.database import Database
from career.utils import read_json, sha256_file, utc_now_iso, write_json


@dataclass(frozen=True)
class CellExecutionResult:
    run_id: str
    node_id: str
    attempt: int
    status: str
    manifest_path: Path
    artifact_manifest_paths: tuple[Path, ...] = ()
    blocker: str = ""
    workspace_owner: str = ""


@dataclass(frozen=True)
class PreparedCellAttempt:
    run_id: str
    application_id: str
    node_id: str
    attempt: int
    worker_id: str
    manifest_path: Path


@dataclass(frozen=True)
class RepairResult:
    run_id: str
    node_id: str
    attempt: int
    repair_scope: str
    reason: str
    invalidated: tuple[str, ...]
    manifest_path: Path


@dataclass(frozen=True)
class ResumeResult:
    run_id: str
    application_id: str
    ready_nodes: tuple[str, ...]
    statuses: Mapping[str, str]


class CellExecutor:
    """Deterministic runner for persisted application cell plans."""

    def __init__(
        self,
        database: Database,
        *,
        applications_root: Path | None = None,
        handlers: Mapping[str, CellHandler] | None = None,
        validators: Mapping[str, CellValidator] | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 300,
        workspace_owner: str | None = None,
        workspace_control_db_id: str | None = None,
        require_authoritative_workspace: bool = False,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.database = database
        self.store = CellStore(database)
        self.applications_root = Path(applications_root or APPLICATIONS_DIR)
        self.handlers = dict(handlers or {})
        self.validators = dict(validators or {})
        self.worker_id = worker_id or f"cell-executor-{uuid4().hex}"
        self.lease_seconds = lease_seconds
        self.workspace_owner = workspace_owner or workspace_owner_from_env()
        self.workspace_lease = WorkspaceLease(
            database,
            default_ttl_seconds=lease_seconds,
            expected_control_db_id=workspace_control_db_id,
            require_authority=require_authoritative_workspace,
        )
        self.workspace_fence_token: int | None = None

    def register_handler(self, node_id: str, handler: CellHandler) -> None:
        self._contract(node_id)
        self.handlers[node_id] = handler

    def register_validator(self, command: str, validator: CellValidator) -> None:
        if not command:
            raise ValueError("validator command is required")
        self.validators[command] = validator

    def release_workspace_lease(self) -> bool:
        """Release the process-owned workspace lease at CLI boundaries."""
        if self.workspace_fence_token is None:
            return True
        released = self.workspace_lease.release(self.workspace_owner)
        if released:
            self.workspace_fence_token = None
        return released

    @staticmethod
    def _receipt_metadata(metadata: Mapping[str, Any]) -> dict[str, str]:
        """Retain only a deterministic metadata digest in SQLite receipts."""
        if not metadata:
            return {}
        serialized = json.dumps(
            dict(metadata), sort_keys=True, separators=(",", ":"), default=str
        )
        return {
            "metadata_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        }

    def plan(
        self,
        application_id: str,
        deliverables: Iterable[str],
        *,
        execution_mode: str = "wave",
    ) -> RunPlan:
        self._renew_workspace_lease()
        paths = self._paths(application_id)
        plan = compile_run_plan(
            application_id,
            deliverables,
            paths,
            execution_mode=execution_mode,
        )
        self.store.create_run(application_id, plan.run_id, graph=plan.as_dict())
        self.database.execute(
            "UPDATE application_runs SET contract_version = ? WHERE run_id = ?",
            (plan.contract_version, plan.run_id),
        )
        return plan

    def ready_nodes(self, run_id: str) -> tuple[str, ...]:
        return tuple(item["node_id"] for item in self.store.list_ready_nodes(run_id))

    def node_status(self, run_id: str, node_id: str) -> str:
        row = self.database.fetch_one(
            "SELECT status FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
        if row is None:
            raise KeyError(f"unknown cell node: {run_id}/{node_id}")
        return str(row["status"])

    def run_ready(
        self,
        run_id: str,
        *,
        _allowed_nodes: set[str] | None = None,
        _max_nodes: int | None = None,
    ) -> tuple[CellExecutionResult, ...]:
        self._renew_workspace_lease()
        plan, paths = self._load_run(run_id)
        if plan.execution_mode == "serial" and _allowed_nodes is None:
            return self.run_serial_stage(run_id)
        if plan.execution_mode == "serial" and _allowed_nodes is not None:
            report = serial_stage_report(plan, self.resume(run_id).statuses)
            if not set(_allowed_nodes) <= set(report.allowed_nodes):
                invalid = ", ".join(sorted(set(_allowed_nodes) - set(report.allowed_nodes)))
                raise ValueError(f"node is outside current serial stage: {invalid}")
        self._recover_canonical_journals(paths, run_id)
        results: list[CellExecutionResult] = []

        for reservation in self._owned_ready_reservations(run_id):
            self._renew_workspace_lease()
            node_id = str(reservation["node_id"])
            if _allowed_nodes is not None and node_id not in _allowed_nodes:
                continue
            node = self._node(plan, node_id)
            results.append(self._execute_reserved(plan, paths, node, reservation))
            if _max_nodes is not None and len(results) >= _max_nodes:
                return tuple(results)

        self._reactivate_ready_superseded(run_id)
        for ready in self.store.list_ready_nodes(run_id):
            self._renew_workspace_lease()
            node_id = str(ready["node_id"])
            if _allowed_nodes is not None and node_id not in _allowed_nodes:
                continue
            # analyze_fit has an external, agent-authored draft/binding. Do
            # not reserve and consume an attempt merely because normalize_job
            # was repaired; wait until the agent has prepared those inputs.
            if node_id == "analyze_fit" and not (
                paths.fit_map_draft.is_file()
                and (paths.app_dir / "fit_map.draft.binding.json").is_file()
            ):
                continue
            if not self._dependencies_validated(run_id, node_id):
                continue
            reservation = self._reserve_node_for_execution(
                paths, run_id, node_id
            )
            if reservation.get("status") != "reserved":
                continue
            if (
                ready.get("status") in {"reserved", "running"}
                and int(reservation["attempt"]) > int(ready["latest_attempt"])
            ):
                try:
                    ManifestStore(paths).reconcile_expired_attempt(
                        node_id, int(ready["latest_attempt"])
                    )
                except Exception as exc:
                    results.append(
                        self._block_reserved(
                            paths,
                            self._node(plan, node_id),
                            reservation,
                            f"reconciliation_error:{type(exc).__name__}:{exc}",
                            (),
                            (),
                        )
                    )
                    continue
            results.append(
                self._execute_reserved(plan, paths, self._node(plan, node_id), reservation)
            )
            if _max_nodes is not None and len(results) >= _max_nodes:
                return tuple(results)
        return tuple(results)

    def run_one_ready(
        self, run_id: str, node_id: str | None = None
    ) -> tuple[CellExecutionResult, ...]:
        """Execute at most one ready node from the current serial stage."""
        self._renew_workspace_lease()
        plan, _paths = self._load_run(run_id)
        if plan.execution_mode != "serial":
            raise ValueError("run_one_ready requires a serial execution mode")
        report = serial_stage_report(plan, self.resume(run_id).statuses)
        if report.status not in {"ready", "running"}:
            if node_id is not None:
                raise ValueError(
                    f"node is not executable in current serial stage: {node_id}"
                )
            return ()
        allowed_nodes = set(report.allowed_nodes)
        if node_id is not None:
            if node_id not in allowed_nodes:
                raise ValueError(f"node is outside current serial stage: {node_id}")
            allowed_nodes = {node_id}
        return self.run_ready(
            run_id,
            _allowed_nodes=allowed_nodes,
            _max_nodes=1,
        )

    def run_serial_stage(self, run_id: str) -> tuple[CellExecutionResult, ...]:
        """Consume only the current serial stage, stopping at its boundary."""
        self._renew_workspace_lease()
        plan, _paths = self._load_run(run_id)
        if plan.execution_mode != "serial":
            raise ValueError("run_serial_stage requires a serial execution mode")

        results: list[CellExecutionResult] = []
        while True:
            current_plan, _current_paths = self._load_run(run_id)
            report = serial_stage_report(
                current_plan, self.resume(run_id).statuses
            )
            if report.status not in {"ready", "running"}:
                break
            current_stage = report.stage
            executed = self.run_one_ready(run_id)
            if not executed:
                break
            results.extend(executed)
            next_report = serial_stage_report(
                current_plan, self.resume(run_id).statuses
            )
            if next_report.stage != current_stage:
                break
        return tuple(results)

    @contextmanager
    def _external_attempt_lock(
        self, paths: ApplicationPaths, run_id: str
    ):
        """Serialize all analyze_fit reservation and recovery filesystem work."""
        import fcntl

        lock_path = (
            paths.requests_dir
            / "cellular"
            / run_id
            / ".analyze_fit.recovery.lock"
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _reserve_node_for_execution(
        self, paths: ApplicationPaths, run_id: str, node_id: str
    ) -> dict[str, Any]:
        if node_id != "analyze_fit":
            return self.store.reserve_node(
                run_id,
                node_id,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
        with self._external_attempt_lock(paths, run_id):
            return self.store.reserve_node(
                run_id,
                node_id,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )

    def prepare_ready_node(
        self, run_id: str, node_id: str, *, _lock_held: bool = False
    ) -> PreparedCellAttempt:
        """Reserve one ready node so an external specialist can fill its inputs."""
        if node_id == "analyze_fit" and not _lock_held:
            _, paths = self._load_run(run_id)
            with self._external_attempt_lock(paths, run_id):
                return self.prepare_ready_node(run_id, node_id, _lock_held=True)
        self._renew_workspace_lease()
        plan, paths = self._load_run(run_id)
        node = self._node(plan, node_id)
        if node_id not in self.ready_nodes(run_id):
            raise RuntimeError(f"cell node is not ready: {run_id}/{node_id}")
        reservation = self.store.reserve_node(
            run_id,
            node_id,
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if reservation.get("status") != "reserved":
            raise RuntimeError(f"cell node could not be reserved: {run_id}/{node_id}")
        record = self._load_or_begin_execution_attempt(
            ManifestStore(paths),
            paths,
            run_id,
            node,
            int(reservation["attempt"]),
            validate_draft_binding=False,
        )
        return PreparedCellAttempt(
            run_id=run_id,
            application_id=plan.application_id,
            node_id=node_id,
            attempt=int(reservation["attempt"]),
            worker_id=self.worker_id,
            manifest_path=record.path,
        )

    @contextmanager
    def keep_prepared_attempt_alive(self, prepared: PreparedCellAttempt):
        if prepared.worker_id != self.worker_id:
            raise RuntimeError("prepared cell attempt belongs to another worker")
        with self._execution_keepalive(
            prepared.run_id, prepared.node_id, prepared.attempt, ()
        ) as state:
            yield state

    def defer_prepared_attempt(
        self, prepared: PreparedCellAttempt, *, reason: str
    ) -> bool:
        """Return an agent-prepared attempt to planned state for a later heartbeat."""
        if prepared.worker_id != self.worker_id:
            raise RuntimeError("prepared cell attempt belongs to another worker")
        deferred = self.store.defer_attempt(
            prepared.run_id,
            prepared.node_id,
            prepared.attempt,
            self.worker_id,
            reason=reason,
        )
        if deferred["deferred"] and prepared.manifest_path.is_file():
            manifest = dict(read_json(prepared.manifest_path))
            manifest["status"] = "cancelled"
            manifest["blocker"] = {"reason": reason}
            manifest["finished_at"] = utc_now_iso()
            write_json(prepared.manifest_path, manifest)
        return bool(deferred["deferred"])

    def recover_stale_external_attempt(
        self, run_id: str, node_id: str
    ) -> dict[str, Any]:
        self._renew_workspace_lease()
        plan, paths = self._load_run(run_id)
        with self._external_attempt_lock(paths, run_id):
            return self._recover_stale_external_attempt_locked(
                run_id, node_id, plan, paths
            )

    def _recover_stale_external_attempt_locked(
        self,
        run_id: str,
        node_id: str,
        plan: RunPlan,
        paths: ApplicationPaths,
    ) -> dict[str, Any]:
        """Requeue a blocked external attempt without consuming a fresh lease.

        ``analyze_fit`` is the only node whose inputs are authored outside the
        executor. A binding failure must quarantine those inputs and return
        the node to ``planned`` so the next preparation creates the next
        attempt with a valid manifest. Expired reservations are reconciled in
        the same transaction; an active lease is never stolen.
        """
        if node_id != "analyze_fit":
            raise ValueError("stale external attempt recovery is only supported for analyze_fit")
        if plan.application_id != paths.application_id:
            raise ValueError("cellular run application identity mismatch")
        row = self.database.fetch_one(
            """SELECT status, latest_attempt, reserved_by,
                      reservation_expires_at
                 FROM cell_nodes
                WHERE run_id = ? AND node_id = ?""",
            (run_id, node_id),
        )
        if row is None:
            raise KeyError(f"unknown cell node: {run_id}/{node_id}")
        latest_attempt = int(row["latest_attempt"] or 0)
        if latest_attempt <= 0:
            return {
                "status": "unchanged",
                "run_id": run_id,
                "node_id": node_id,
                "next_attempt": 1,
            }

        node_status = str(row["status"] or "")
        if node_status == "validated":
            return {
                "status": "unchanged",
                "run_id": run_id,
                "node_id": node_id,
                "next_attempt": latest_attempt + 1,
            }

        now = utc_now_iso()
        expiry = str(row["reservation_expires_at"] or "")
        active_lease = (
            node_status in {"reserved", "running"}
            and bool(expiry)
            and expiry > now
        )
        if active_lease:
            active_manifest = (
                paths.cells_dir / node_id / str(latest_attempt) / "manifest.json"
            )
            active_handoff = (
                paths.requests_dir
                / "cellular"
                / run_id
                / node_id
                / f"{latest_attempt}.handoff.json"
            )
            if active_manifest.is_file() and active_handoff.is_file():
                manifest = read_json(active_manifest)
                expected_active = {
                    "kind": "cell_attempt_manifest",
                    "application_id": paths.application_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "attempt": latest_attempt,
                }
                if all(
                    manifest.get(key) == value
                    for key, value in expected_active.items()
                ):
                    return {
                        "status": "awaiting_agent",
                        "run_id": run_id,
                        "node_id": node_id,
                        "next_attempt": latest_attempt,
                        "handoff_manifest_path": str(active_manifest.resolve()),
                        "handoff_path": str(active_handoff.resolve()),
                    }
            return {
                "status": "blocked",
                "run_id": run_id,
                "node_id": node_id,
                "next_attempt": latest_attempt + 1,
                "blocker_reason": "active_analyze_fit_lease",
            }

        manifest_path = (
            paths.cells_dir / node_id / str(latest_attempt) / "manifest.json"
        )
        blocker_reason = ""
        if manifest_path.is_file():
            try:
                manifest = read_json(manifest_path)
                blocker = manifest.get("blocker")
                if isinstance(blocker, Mapping):
                    blocker_reason = str(blocker.get("reason") or "")
            except (OSError, TypeError, ValueError):
                blocker_reason = ""
        normalized_blocker = blocker_reason.casefold()
        stale_binding = (
            "draft_binding" in normalized_blocker
            or "draft binding" in normalized_blocker
        )
        if node_status in {"reserved", "running"} and not stale_binding:
            binding_path = paths.app_dir / "fit_map.draft.binding.json"
            stale_binding = paths.fit_map_draft.is_file() or binding_path.is_file()
        if not stale_binding:
            return {
                "status": "unchanged",
                "run_id": run_id,
                "node_id": node_id,
                "next_attempt": latest_attempt + 1,
            }

        # Validate once so the existing validator supplies the precise
        # mismatch reasons and quarantines only the draft and its binding.
        try:
            self._validate_fit_map_draft_binding(
                paths, run_id=run_id, attempt=latest_attempt
            )
        except ValueError as exc:
            blocker_reason = str(exc)

        # A stale reservation may have no usable owner after a process crash.
        # Reconcile both tables under one immediate transaction, then create
        # the next external handoff through the same canonical reservation and
        # manifest path used by the normal analyze_fit flow.
        with self.database.transaction(immediate=True) as conn:
            current = conn.execute(
                """SELECT status, latest_attempt, reservation_expires_at
                     FROM cell_nodes
                    WHERE run_id = ? AND node_id = ?""",
                (run_id, node_id),
            ).fetchone()
            if current is None:
                raise KeyError(f"unknown cell node: {run_id}/{node_id}")
            current_expiry = str(current["reservation_expires_at"] or "")
            current_active = (
                str(current["status"] or "") in {"reserved", "running"}
                and bool(current_expiry)
                and current_expiry > now
            )
            if current_active:
                return {
                    "status": "blocked",
                    "run_id": run_id,
                    "node_id": node_id,
                    "next_attempt": int(current["latest_attempt"] or 0) + 1,
                    "blocker_reason": "active_analyze_fit_lease",
                }
            conn.execute(
                """UPDATE cell_nodes
                      SET status = 'planned', reserved_by = NULL,
                          reservation_expires_at = NULL, updated_at = ?
                    WHERE run_id = ? AND node_id = ?""",
                (now, run_id, node_id),
            )
            conn.execute(
                """UPDATE cell_attempts
                      SET status = 'cancelled', finished_at = ?
                    WHERE run_id = ? AND node_id = ? AND attempt = ?
                      AND status IN ('reserved', 'running')
                      AND finished_at IS NULL""",
                (now, run_id, node_id, latest_attempt),
            )

        prepared = self.prepare_ready_node(run_id, node_id, _lock_held=True)
        expected_manifest_path = (
            paths.cells_dir / node_id / str(latest_attempt + 1) / "manifest.json"
        ).resolve()
        if prepared.attempt != latest_attempt + 1:
            raise RuntimeError("stale analyze-fit recovery reserved an unexpected attempt")
        if prepared.manifest_path.resolve() != expected_manifest_path:
            raise RuntimeError("stale analyze-fit recovery produced an unexpected manifest")
        manifest = read_json(prepared.manifest_path)
        expected_manifest = {
            "kind": "cell_attempt_manifest",
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": latest_attempt + 1,
        }
        if any(manifest.get(key) != value for key, value in expected_manifest.items()):
            raise RuntimeError("stale analyze-fit recovery manifest identity mismatch")

        handoff_path = (
            paths.requests_dir
            / "cellular"
            / run_id
            / node_id
            / f"{latest_attempt + 1}.handoff.json"
        )
        handoff = {
            "kind": "cellular_external_attempt_handoff",
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": latest_attempt + 1,
            "status": "reserved",
            "expected_manifest_path": str(expected_manifest_path),
            "manifest_path": str(prepared.manifest_path.resolve()),
            "created_at": utc_now_iso(),
        }
        write_json(handoff_path, handoff)
        persisted_handoff = read_json(handoff_path)
        if any(persisted_handoff.get(key) != value for key, value in handoff.items()):
            raise RuntimeError("stale analyze-fit handoff manifest identity mismatch")

        return {
            "status": "awaiting_agent",
            "run_id": run_id,
            "node_id": node_id,
            "next_attempt": latest_attempt + 1,
            "blocker_reason": blocker_reason or "stale_analyze_fit_binding",
            "handoff_manifest_path": str(prepared.manifest_path.resolve()),
            "handoff_path": str(handoff_path.resolve()),
        }

    def repair(self, run_id: str, node_id: str, reason: str) -> RepairResult:
        self._renew_workspace_lease()
        plan, paths = self._load_run(run_id)
        node = self._node(plan, node_id)
        contract = self._contract(node_id)
        row = self.database.fetch_one(
            "SELECT status, latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
        if row is None:
            raise KeyError(f"unknown cell node: {run_id}/{node_id}")
        if int(row["latest_attempt"]) <= 0:
            raise RuntimeError(f"cannot repair node without a prior attempt: {node_id}")
        if int(row["latest_attempt"]) >= contract.max_attempts:
            raise RuntimeError(f"maximum attempts reached for node: {node_id}")

        invalidated = self._contract_descendants(node_id, {item.node_id for item in plan.nodes})
        defer_invalidation_until_publication = node_id == "analyze_fit"
        reservation_invalidated = () if defer_invalidation_until_publication else invalidated
        now = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            current = conn.execute(
                """SELECT status, reservation_expires_at FROM cell_nodes
                   WHERE run_id = ? AND node_id = ?""",
                (run_id, node_id),
            ).fetchone()
            if (
                current is not None
                and current["status"] in {"reserved", "running"}
                and current["reservation_expires_at"] is not None
                and current["reservation_expires_at"] > now
            ):
                raise RuntimeError(f"cannot repair node with an active lease: {node_id}")
            active_descendants = []
            for descendant in invalidated:
                descendant_row = conn.execute(
                    """SELECT status, reservation_expires_at FROM cell_nodes
                       WHERE run_id = ? AND node_id = ?""",
                    (run_id, descendant),
                ).fetchone()
                if (
                    descendant_row is not None
                    and descendant_row["status"] in {"reserved", "running"}
                    and descendant_row["reservation_expires_at"] is not None
                    and descendant_row["reservation_expires_at"] > now
                ):
                    active_descendants.append(descendant)
            if active_descendants:
                raise RuntimeError(
                    "cannot repair while active descendant lease(s) exist: "
                    + ", ".join(sorted(active_descendants))
                )
            conn.execute(
                """UPDATE cell_nodes
                   SET status = 'repairing', reserved_by = NULL,
                       reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ?""",
                (now, run_id, node_id),
            )
            for descendant in reservation_invalidated:
                descendant_row = conn.execute(
                    """SELECT status, latest_attempt FROM cell_nodes
                       WHERE run_id = ? AND node_id = ?""",
                    (run_id, descendant),
                ).fetchone()
                if descendant_row is None or descendant_row["status"] == "planned":
                    continue
                conn.execute(
                    """UPDATE cell_nodes
                       SET status = 'superseded', reserved_by = NULL,
                           reservation_expires_at = NULL, updated_at = ?
                       WHERE run_id = ? AND node_id = ?""",
                    (now, run_id, descendant),
                )
                if int(descendant_row["latest_attempt"]) > 0:
                    conn.execute(
                        """UPDATE cell_attempts SET status = 'superseded'
                           WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                        (
                            run_id,
                            descendant,
                            int(descendant_row["latest_attempt"]),
                        ),
                    )

        for descendant in reservation_invalidated:
            self._mark_attempt_manifest_superseded(paths, run_id, descendant)

        reservation = self.store.reserve_node(
            run_id,
            node_id,
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if reservation.get("status") != "reserved":
            raise RuntimeError(f"could not reserve repair attempt: {run_id}/{node_id}")
        attempt = int(reservation["attempt"])
        manifest = self._begin_attempt(
            paths,
            run_id,
            node,
            attempt,
            status="repairing",
            repair_reason=reason,
            allow_unvalidated_inputs=True,
            validate_draft_binding=False,
        )
        return RepairResult(
            run_id=run_id,
            node_id=node_id,
            attempt=attempt,
            repair_scope=contract.repair_scope,
            reason=str(reason),
            invalidated=reservation_invalidated,
            manifest_path=manifest.path,
        )

    def repair_and_run(
        self, run_id: str, node_id: str, reason: str
    ) -> tuple[RepairResult, tuple[CellExecutionResult, ...]]:
        """Repair one node and close its reservation in the same operation."""
        repaired = self.repair(run_id, node_id, reason)
        plan, paths = self._load_run(run_id)
        prepared = PreparedCellAttempt(
            run_id=repaired.run_id,
            application_id=plan.application_id,
            node_id=repaired.node_id,
            attempt=repaired.attempt,
            worker_id=self.worker_id,
            manifest_path=repaired.manifest_path,
        )
        if node_id == "analyze_fit":
            # analyze_fit is authored by an external agent. A draft or
            # binding left by the failed attempt belongs to that attempt and
            # must never be executed by the repaired one. Always return the
            # repair lease to planned state so the agent can quarantine any
            # stale draft, prepare a fresh attempt, and bind it to its own
            # immutable manifest.
            self.defer_prepared_attempt(
                prepared,
                reason="repair_waiting_for_fresh_fit_map_draft_binding",
            )
            return repaired, ()
        try:
            results = self.run_ready(run_id)
            if not any(item.node_id == node_id for item in results):
                self.defer_prepared_attempt(
                    prepared,
                    reason="repair_execution_not_started",
                )
            return repaired, results
        except BaseException:
            self.defer_prepared_attempt(
                prepared,
                reason="repair_execution_failed",
            )
            raise

    def resume(self, run_id: str) -> ResumeResult:
        plan, paths = self._load_run(run_id)
        ManifestStore(paths)._load_run_plan_nodes(run_id)
        persisted_nodes = {node.node_id for node in plan.nodes}
        database_rows = self.database.fetch_all(
            "SELECT node_id, status FROM cell_nodes WHERE run_id = ? ORDER BY node_id",
            (run_id,),
        )
        database_nodes = {str(row["node_id"]) for row in database_rows}
        if not persisted_nodes <= database_nodes:
            raise ValueError("database nodes do not match persisted run plan")
        # Gate receipts may register auxiliary completed nodes under the same
        # run ID during canonical reconciliation. They are not executable DAG
        # nodes and must not make an otherwise valid run appear inconsistent.
        statuses = {
            str(row["node_id"]): row["status"]
            for row in database_rows
            if str(row["node_id"]) in persisted_nodes
        }
        ready = list(self.ready_nodes(run_id))
        ready.extend(
            reservation["node_id"]
            for reservation in self._owned_ready_reservations(run_id)
            if reservation["node_id"] not in ready
        )
        return ResumeResult(
            run_id=run_id,
            application_id=plan.application_id,
            ready_nodes=tuple(ready),
            statuses=statuses,
        )

    def finalize(self, run_id: str) -> RunCompletion:
        self._renew_workspace_lease()
        _plan, paths = self._load_run(run_id)
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            if self.workspace_fence_token is None:
                raise RuntimeError("stale authoritative workspace lease")
            with self.database.transaction(immediate=True) as conn:
                now = utc_now_iso()
                owned = conn.execute(
                    """SELECT 1 FROM workspace_leases
                       WHERE lease_name = 'authoritative-workspace'
                         AND worker_id = ? AND lease_epoch = ?
                         AND expires_at > ?""",
                    (
                        self.workspace_owner,
                        int(self.workspace_fence_token),
                        now,
                    ),
                ).fetchone()
                if owned is None:
                    raise RuntimeError("stale authoritative workspace lease")
                run_row = conn.execute(
                    "SELECT status FROM application_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if run_row is None:
                    raise KeyError(f"unknown application run: {run_id}")
                if run_row["status"] == "completed":
                    completion_path = (
                        paths.app_dir
                        / "runs"
                        / run_id
                        / "run_completion_manifest.json"
                    )
                    if completion_path.is_file():
                        try:
                            persisted = read_json(completion_path)
                            validated = ManifestStore(paths).validate_run_completion(
                                run_id, persisted
                            )
                        except Exception:
                            validated = None
                        if validated is not None:
                            return RunCompletion(
                                path=completion_path, manifest=dict(validated)
                            )
                    rebuilt = ManifestStore(paths).finish_run(
                        run_id,
                        validated_artifacts=(),
                        blocked_nodes=(),
                    )
                    conn.execute(
                        "UPDATE application_runs SET status = ?, updated_at = ? "
                        "WHERE run_id = ?",
                        (rebuilt.manifest["status"], now, run_id),
                    )
                    return rebuilt
                completion = ManifestStore(paths).finish_run(
                    run_id,
                    validated_artifacts=(),
                    blocked_nodes=(),
                )
                updated = conn.execute(
                    "UPDATE application_runs SET status = ?, updated_at = ? "
                    "WHERE run_id = ? AND status NOT IN ('completed', 'cancelled')",
                    (completion.manifest["status"], now, run_id),
                ).rowcount
                if updated != 1:
                    completion.path.unlink(missing_ok=True)
                    raise RuntimeError("run is no longer finalizable")
                return completion

    def is_terminal(self, run_id: str) -> bool:
        statuses = self.resume(run_id).statuses.values()
        return bool(statuses) and all(status in {"validated", "blocked"} for status in statuses)

    def mark_validated(self, run_id: str, node_id: str) -> None:
        """Persist a synthetic validated attempt for orchestration tests and imports."""
        self._renew_workspace_lease()
        _plan, paths = self._load_run(run_id)
        self._set_manual_terminal(run_id, paths, node_id, "validated", "")

    def fail(self, run_id: str, node_id: str, reason: str) -> None:
        """Persist a synthetic blocked attempt for orchestration tests and imports."""
        self._renew_workspace_lease()
        _plan, paths = self._load_run(run_id)
        self._set_manual_terminal(run_id, paths, node_id, "blocked", reason)

    def _renew_workspace_lease(self) -> None:
        if self.workspace_fence_token is None:
            if not self.workspace_lease.acquire(
                self.workspace_owner, ttl_seconds=self.lease_seconds
            ):
                current = self.workspace_lease.inspect() or {}
                raise RuntimeError(
                    "workspace lease is owned by another authoritative copy: "
                    f"{current.get('owner') or 'unknown'}"
                )
            self.workspace_fence_token = self.workspace_lease.fence_token
        if not self.workspace_lease.heartbeat(
            self.workspace_owner, ttl_seconds=self.lease_seconds
        ):
            raise RuntimeError("workspace lease heartbeat failed")

    def _execute_reserved(
        self,
        plan: RunPlan,
        paths: ApplicationPaths,
        node: NodePlan,
        reservation: Mapping[str, Any],
    ) -> CellExecutionResult:
        if not self._dependencies_validated(plan.run_id, node.node_id):
            return self._block_reserved(
                paths, node, reservation, "dependency_not_validated", (), ()
            )

        attempt = int(reservation["attempt"])
        prior_fit_map_hash = (
            self._latest_fit_map_revision_hash(plan.run_id, node.node_id)
            if node.node_id == "analyze_fit" and attempt > 1
            else None
        )
        manifest_store = ManifestStore(paths)
        try:
            attempt_record = self._load_or_begin_execution_attempt(
                manifest_store, paths, plan.run_id, node, attempt
            )
        except Exception as exc:
            attempt_record = self._load_or_begin_unmaterialized_attempt(
                manifest_store, paths, plan.run_id, node, attempt
            )
            return self._block_reserved(
                paths,
                node,
                reservation,
                f"input_materialization_error:{type(exc).__name__}:{exc}",
                (),
                (),
                attempt_record=attempt_record,
            )
        context = self._context_from_manifest(paths, node, attempt_record.path)
        acquired_resources: list[Mapping[str, Any]] = []
        keepalive_context = None
        authority_fence_context = None
        try:
            for resource in node.resources:
                lock = self.store.acquire_resource_lock(
                    resource,
                    self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                if not lock["acquired"]:
                    return self._defer_reserved(
                        paths,
                        node,
                        reservation,
                        f"resource_busy:{resource}",
                        attempt_record,
                    )
                acquired_resources.append(lock)

            handler = self.handlers.get(node.node_id)
            if handler is None:
                return self._block_reserved(
                    paths, node, reservation, "handler_not_registered", (), ()
                )
            node_lease = self.store.renew_node_reservation(
                plan.run_id,
                node.node_id,
                attempt,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if not node_lease["renewed"]:
                return self._cancel_expired_execution(
                    paths, node, reservation, attempt_record.path
                )
            for lock in acquired_resources:
                renewed = self.store.renew_resource_lock(
                    str(lock["resource_name"]),
                    self.worker_id,
                    str(lock["lease_id"]),
                    lease_seconds=self.lease_seconds,
                )
                if not renewed["renewed"]:
                    return self._block_reserved(
                        paths,
                        node,
                        reservation,
                        f"resource_lease_expired:{lock['resource_name']}",
                        (),
                        (),
                        attempt_record=attempt_record,
                    )
            keepalive_context = self._execution_keepalive(
                plan.run_id,
                node.node_id,
                attempt,
                acquired_resources,
            )
            keepalive = keepalive_context.__enter__()
            try:
                with context.capabilities.enforce_writes():
                    output = handler(context)
                if keepalive["failure"]:
                    failure = str(keepalive["failure"])
                    if failure == "node_lease_expired":
                        return self._cancel_expired_execution(
                            paths, node, reservation, attempt_record.path
                        )
                    if failure == "workspace_lease_expired":
                        return self._cancel_stale_workspace_execution(
                            reservation, node, attempt_record.path
                        )
                    return self._block_reserved(
                        paths,
                        node,
                        reservation,
                        failure,
                        (),
                        (),
                        attempt_record=attempt_record,
                    )
            except CapabilityViolation as exc:
                return self._cancel_capability_violation(
                    reservation,
                    node,
                    attempt_record.path,
                    str(exc),
                )
            except Exception as exc:
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    f"handler_error:{type(exc).__name__}:{exc}",
                    (),
                    (),
                )
            lease_failure = self._renew_execution_leases(
                plan.run_id, node.node_id, attempt, acquired_resources
            )
            if lease_failure == "node_lease_expired":
                return self._cancel_expired_execution(
                    paths, node, reservation, attempt_record.path
                )
            if lease_failure == "workspace_lease_expired":
                return self._cancel_stale_workspace_execution(
                    reservation, node, attempt_record.path
                )
            if lease_failure is not None:
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    lease_failure,
                    (),
                    (),
                    attempt_record=attempt_record,
                )
            if not isinstance(output, CellOutput):
                return self._block_reserved(
                    paths, node, reservation, "handler_returned_invalid_output", (), ()
                )

            expected_artifacts = {Path(path).name for path in node.produces}
            actual_artifacts = set(output.artifacts)
            if actual_artifacts != expected_artifacts:
                missing = sorted(expected_artifacts - actual_artifacts)
                arbitrary = sorted(actual_artifacts - expected_artifacts)
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    "output_contract_mismatch:"
                    f"missing={','.join(missing) or '-'};"
                    f"arbitrary={','.join(arbitrary) or '-'}",
                    (),
                    (),
                    attempt_record=attempt_record,
                )

            try:
                staged_paths = self._stage_output(context, output)
            except Exception as exc:
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    f"staging_error:{type(exc).__name__}:{exc}",
                    (),
                    (),
                )
            validator_results = self._run_validators(context, output, node.validators)
            if keepalive["failure"]:
                if keepalive["failure"] == "workspace_lease_expired":
                    return self._cancel_stale_workspace_execution(
                        reservation, node, attempt_record.path
                    )
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    str(keepalive["failure"]),
                    staged_paths,
                    validator_results,
                    attempt_record=attempt_record,
                )
            lease_failure = self._renew_execution_leases(
                plan.run_id, node.node_id, attempt, acquired_resources
            )
            if lease_failure == "node_lease_expired":
                return self._cancel_expired_execution(
                    paths, node, reservation, attempt_record.path
                )
            if lease_failure == "workspace_lease_expired":
                return self._cancel_stale_workspace_execution(
                    reservation, node, attempt_record.path
                )
            if lease_failure is not None:
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    lease_failure,
                    staged_paths,
                    validator_results,
                    attempt_record=attempt_record,
                )
            failures = [item for item in validator_results if item.result != "passed"]
            if failures:
                reason = failures[0].reason or f"validator_failed:{failures[0].command}"
                return self._block_reserved(
                    paths, node, reservation, reason, staged_paths, validator_results
                )
            authority_fence_context = self.database.authority_ledger_lock()
            authority_fence_context.__enter__()
            if self.database.authority_ledger_path is not None:
                try:
                    self.database.assert_authoritative_storage()
                except ValueError:
                    return self._cancel_stale_workspace_execution(
                        reservation, node, attempt_record.path
                    )
            if output.handover:
                try:
                    manifest_store.write_handover(
                        node.node_id, attempt, output.handover
                    )
                except Exception as exc:
                    return self._block_reserved(
                        paths,
                        node,
                        reservation,
                        f"handover_error:{type(exc).__name__}:{exc}",
                        staged_paths,
                        validator_results,
                    )
            try:
                CellStore._receipt_json(
                    "validated",
                    {
                        "status": "validated",
                        "paths": [],
                        "hashes": {},
                        "metadata": self._receipt_metadata(output.metadata),
                    },
                )
                contents = {
                    artifact_name: (
                        raw_content.encode("utf-8")
                        if isinstance(raw_content, str)
                        else raw_content
                    )
                    for artifact_name, raw_content in output.artifacts.items()
                }
                published = manifest_store.publish_files(
                    node.node_id,
                    attempt,
                    contents,
                    inputs=context.inputs,
                    validators=[
                        self._validator_mapping(item) for item in validator_results
                    ],
                )
            except Exception as exc:
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    f"publication_error:{type(exc).__name__}:{exc}",
                    staged_paths,
                    validator_results,
                )
            if keepalive["failure"]:
                manifest_store.rollback_publications(
                    node.node_id, attempt, published
                )
                if keepalive["failure"] == "workspace_lease_expired":
                    return self._cancel_stale_workspace_execution(
                        reservation, node, attempt_record.path
                    )
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    str(keepalive["failure"]),
                    (),
                    validator_results,
                    attempt_record=manifest_store._load_attempt(node.node_id, attempt),
                )
            lease_failure = self._renew_execution_leases(
                plan.run_id, node.node_id, attempt, acquired_resources
            )
            if lease_failure is not None:
                manifest_store.rollback_publications(
                    node.node_id, attempt, published
                )
                if lease_failure == "node_lease_expired":
                    return self._cancel_expired_execution(
                        paths, node, reservation, attempt_record.path
                    )
                if lease_failure == "workspace_lease_expired":
                    return self._cancel_stale_workspace_execution(
                        reservation, node, attempt_record.path
                    )
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    lease_failure,
                    (),
                    validator_results,
                    attempt_record=manifest_store._load_attempt(node.node_id, attempt),
                )
            canonical_journal: Path | None = None
            try:
                if node.node_id in {"capture_source", "normalize_job"}:
                    canonical_journal = self._begin_canonical_journal(
                        paths, plan.run_id, node.node_id, attempt
                    )
                    if node.node_id == "capture_source":
                        self._commit_captured_source(paths, output, published)
                    elif output.handover:
                        self._commit_normalized_derived(paths)
                self.store.finish_attempt(
                    plan.run_id,
                    node.node_id,
                    attempt,
                    "validated",
                    worker_id=self.worker_id,
                    receipt={
                        "status": "validated",
                        "paths": [str(item.path) for item in published],
                        "hashes": {
                            str(item.path): item.manifest["sha256"] for item in published
                        },
                        "metadata": self._receipt_metadata(output.metadata),
                    },
                    workspace_owner=self.workspace_owner,
                    workspace_fence_token=self.workspace_fence_token,
                    resource_leases=acquired_resources,
                    published_artifacts=tuple(
                        {
                            "artifact_name": item.manifest["artifact_name"],
                            "path": str(item.path),
                            "sha256": item.manifest["sha256"],
                            "inputs": item.manifest["inputs"],
                        }
                        for item in published
                    ),
                )
                if node.node_id == "analyze_fit" and prior_fit_map_hash is not None:
                    current_fit_map_path = next(
                        (
                            item.path
                            for item in published
                            if item.manifest["artifact_name"] == "fit_map.json"
                        ),
                        None,
                    )
                    current_fit_map_hash = (
                        self._fit_map_revision_hash(current_fit_map_path)
                        if current_fit_map_path is not None
                        else None
                    )
                    if current_fit_map_hash != prior_fit_map_hash:
                        self._supersede_contract_descendants(
                            paths,
                            plan.run_id,
                            node.node_id,
                            {item.node_id for item in plan.nodes},
                        )
                if canonical_journal is not None:
                    self._clear_canonical_journal(
                        canonical_journal, plan.run_id, node.node_id, attempt
                    )
            except Exception as exc:
                if canonical_journal is not None and canonical_journal.is_file():
                    self._restore_canonical_journal(canonical_journal)
                manifest_store.rollback_publications(
                    node.node_id, attempt, published
                )
                lease_failure = self._renew_execution_leases(
                    plan.run_id, node.node_id, attempt, acquired_resources
                )
                if lease_failure == "node_lease_expired":
                    return self._cancel_expired_execution(
                        paths, node, reservation, attempt_record.path
                    )
                if lease_failure == "workspace_lease_expired":
                    return self._cancel_stale_workspace_execution(
                        reservation, node, attempt_record.path
                    )
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    lease_failure
                    or f"publication_commit_error:{type(exc).__name__}:{exc}",
                    (),
                    validator_results,
                    attempt_record=manifest_store._load_attempt(node.node_id, attempt),
                )
            return CellExecutionResult(
                run_id=plan.run_id,
                node_id=node.node_id,
                attempt=attempt,
                status="validated",
                manifest_path=attempt_record.path,
                artifact_manifest_paths=tuple(
                    item.manifest_path for item in published
                ),
                workspace_owner=self.workspace_owner,
            )
        finally:
            if authority_fence_context is not None:
                authority_fence_context.__exit__(None, None, None)
            if keepalive_context is not None:
                keepalive_context.__exit__(None, None, None)
            for lock in reversed(acquired_resources):
                self.store.release_resource_lock(
                    str(lock["resource_name"]),
                    self.worker_id,
                    lease_id=str(lock["lease_id"]),
                )

    @staticmethod
    def _commit_captured_source(
        paths: ApplicationPaths,
        output: CellOutput,
        published: Iterable[Any],
    ) -> None:
        source = next(
            (
                item.path.read_bytes()
                for item in published
                if item.manifest.get("artifact_name") == "job_description.md"
            ),
            None,
        )
        if source is None:
            raise RuntimeError("validated source publication is missing")
        metadata = {
            "application_id": paths.application_id,
            "job_description_path": str(paths.job_description),
            "job_fingerprint": hashlib.sha256(source).hexdigest(),
            "source_id": output.handover.get("source_id"),
            "source_type": str(output.handover.get("source_type") or "cell_input"),
        }
        paths.job_description.parent.mkdir(parents=True, exist_ok=True)
        temporary_source = paths.job_description.with_suffix(".md.validated.tmp")
        temporary_source.write_bytes(source)
        temporary_source.replace(paths.job_description)
        write_json(paths.source_metadata, metadata)

    @staticmethod
    def _commit_normalized_derived(paths: ApplicationPaths) -> None:
        """Materialize canonical derived packs only after cell validation."""
        from career.services import derived_context as derived_context_service

        derived_context_service.normalize_job(
            paths,
            job_description_path=paths.job_description,
            persist=True,
        )

    @staticmethod
    def _canonical_targets(paths: ApplicationPaths, node_id: str) -> tuple[Path, ...]:
        if node_id == "capture_source":
            return (paths.job_description, paths.source_metadata)
        if node_id == "normalize_job":
            return (paths.derived_dir,)
        return ()

    @staticmethod
    def _assert_canonical_target_safe(
        paths: ApplicationPaths, target: Path, *, label: str = "canonical target"
    ) -> Path:
        """Reject canonical projections that traverse a symlink or leave the app."""
        app_dir = paths.app_dir.absolute()
        candidate = Path(target).absolute()
        try:
            relative = candidate.relative_to(app_dir)
        except ValueError as exc:
            raise ValueError(f"{label} leaves the application directory") from exc
        current = Path(app_dir.anchor)
        for part in app_dir.parts[1:]:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"{label} uses a symlinked application directory: {current}"
                )
        current = app_dir
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"{label} traverses a symlink: {current}")
        resolved_app = app_dir.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
        if not resolved_candidate.is_relative_to(resolved_app):
            raise ValueError(f"{label} resolves outside the application directory")
        return candidate

    @classmethod
    def _assert_canonical_tree_safe(
        cls, paths: ApplicationPaths, target: Path
    ) -> Path:
        candidate = cls._assert_canonical_target_safe(paths, target)
        if candidate.is_dir():
            for descendant in candidate.rglob("*"):
                cls._assert_canonical_target_safe(
                    paths, descendant, label="canonical tree entry"
                )
        return candidate

    def _begin_canonical_journal(
        self,
        paths: ApplicationPaths,
        run_id: str,
        node_id: str,
        attempt: int,
    ) -> Path:
        entries: list[dict[str, Any]] = []
        for target in self._canonical_targets(paths, node_id):
            resolved = self._assert_canonical_tree_safe(paths, target)
            if resolved.is_dir():
                files = sorted(path for path in resolved.rglob("*") if path.is_file())
                encoded_files = {
                    str(path.relative_to(resolved)): base64.b64encode(
                        path.read_bytes()
                    ).decode("ascii")
                    for path in files
                }
                entries.append(
                    {
                        "path": str(resolved),
                        "kind": "directory",
                        "files": encoded_files,
                        "file_sha256": {
                            relative: hashlib.sha256(
                                base64.b64decode(encoded)
                            ).hexdigest()
                            for relative, encoded in encoded_files.items()
                        },
                    }
                )
            elif resolved.is_file():
                content = resolved.read_bytes()
                entries.append(
                    {
                        "path": str(resolved),
                        "kind": "file",
                        "content": base64.b64encode(content).decode("ascii"),
                        "content_sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
            else:
                entries.append({"path": str(resolved), "kind": "missing"})
        journal = (
            paths.cells_dir
            / node_id
            / str(attempt)
            / "canonical_commit_journal.json"
        )
        operation = {
            "capture_source": "restore_job_description_and_source_metadata",
            "normalize_job": "restore_normalized_derived_projection",
        }.get(node_id)
        if operation is None:
            raise ValueError(f"canonical journal is not supported for node: {node_id}")
        payload = {
            "kind": "canonical_commit_journal",
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": attempt,
            "operation": operation,
            "state": "prepared",
            "entries": entries,
            "created_at": utc_now_iso(),
        }
        write_json(journal, payload)
        snapshot_json = json.dumps(
            entries, sort_keys=True, separators=(",", ":")
        )
        self.database.execute(
            """INSERT OR REPLACE INTO canonical_journal_snapshots
               (run_id, node_id, attempt, application_id, operation, journal_path,
                journal_sha256, snapshot_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                node_id,
                attempt,
                paths.application_id,
                operation,
                str(journal.resolve()),
                hashlib.sha256(journal.read_bytes()).hexdigest(),
                snapshot_json,
                utc_now_iso(),
            ),
        )
        return journal

    def _restore_canonical_journal(self, journal: Path) -> None:
        try:
            payload = self._validate_canonical_journal(journal)
        except Exception:
            self._quarantine_canonical_journal(journal)
            raise
        application_id = str(payload["application_id"])
        journal_absolute = Path(journal).absolute()
        app_root = journal_absolute.parents[4]
        paths = paths_for(application_id, root=app_root.parent)
        for entry in payload.get("entries", []):
            target = self._assert_canonical_tree_safe(
                paths, Path(str(entry["path"])).absolute()
            )
            kind = entry.get("kind")
            if kind == "directory":
                self._assert_canonical_target_safe(paths, target)
                target.mkdir(parents=True, exist_ok=True)
                expected = set((entry.get("files") or {}).keys())
                for current in sorted(
                    (path for path in target.rglob("*") if path.is_file()), reverse=True
                ):
                    if str(current.relative_to(target)) not in expected:
                        self._assert_canonical_target_safe(
                            paths, current, label="canonical restore deletion"
                        )
                        current.unlink(missing_ok=True)
                for relative, encoded in (entry.get("files") or {}).items():
                    restored = self._assert_canonical_target_safe(
                        paths,
                        target / relative,
                        label="canonical restore file",
                    )
                    if not restored.is_relative_to(target):
                        raise ValueError("canonical journal directory entry escapes its target")
                    self._assert_canonical_target_safe(paths, restored.parent)
                    restored.parent.mkdir(parents=True, exist_ok=True)
                    self._assert_canonical_target_safe(paths, restored)
                    restored.write_bytes(base64.b64decode(encoded))
            elif kind == "file":
                self._assert_canonical_target_safe(paths, target.parent)
                target.parent.mkdir(parents=True, exist_ok=True)
                self._assert_canonical_target_safe(paths, target)
                target.write_bytes(base64.b64decode(entry["content"]))
            elif kind == "missing":
                if target.is_file() or target.is_symlink():
                    self._assert_canonical_target_safe(paths, target)
                    target.unlink(missing_ok=True)
                elif target.is_dir():
                    for current in sorted(target.rglob("*"), reverse=True):
                        self._assert_canonical_target_safe(
                            paths, current, label="canonical restore deletion"
                        )
                        if current.is_file() or current.is_symlink():
                            current.unlink(missing_ok=True)
                        elif current.is_dir():
                            current.rmdir()
                    self._assert_canonical_target_safe(paths, target)
                    target.rmdir()
        self._clear_canonical_journal(
            journal,
            str(payload["run_id"]),
            str(payload["node_id"]),
            int(payload["attempt"]),
        )

    def _validate_canonical_journal(self, journal: Path) -> dict[str, Any]:
        journal = Path(journal).absolute()
        payload = read_json(journal)
        if payload.get("kind") != "canonical_commit_journal":
            raise ValueError("canonical journal has invalid kind")
        try:
            attempt = int(journal.parent.name)
            node_id = journal.parent.parent.name
            path_run_id = journal.parent.parent.parent.name
            cells_dir = journal.parent.parent.parent.parent
            app_root = cells_dir.parent
        except (IndexError, ValueError) as exc:
            raise ValueError("canonical journal path is invalid") from exc
        if cells_dir.name != "cells" or journal.name != "canonical_commit_journal.json":
            raise ValueError("canonical journal path is invalid")
        application_id = str(payload.get("application_id") or "")
        run_id = str(payload.get("run_id") or "")
        expected_paths = paths_for(application_id, root=app_root.parent)
        if expected_paths.app_dir.absolute() != app_root.absolute():
            raise ValueError("canonical journal application path mismatch")
        self._assert_canonical_target_safe(
            expected_paths, journal, label="canonical journal path"
        )
        if (
            not run_id
            or run_id != path_run_id
            or payload.get("node_id") != node_id
            or payload.get("attempt") != attempt
        ):
            raise ValueError("canonical journal identity mismatch")
        expected_operation = {
            "capture_source": "restore_job_description_and_source_metadata",
            "normalize_job": "restore_normalized_derived_projection",
        }.get(node_id)
        if payload.get("operation") != expected_operation:
            raise ValueError("canonical journal intended operation mismatch")
        expected_targets = {
            str(self._assert_canonical_tree_safe(expected_paths, path))
            for path in CellExecutor._canonical_targets(expected_paths, node_id)
        }
        entries = payload.get("entries")
        if not isinstance(entries, list) or {
            str(Path(str(entry.get("path") or "")).absolute())
            for entry in entries
            if isinstance(entry, Mapping)
        } != expected_targets:
            raise ValueError("canonical journal targets do not match the cell contract")
        if len(entries) != len(expected_targets):
            raise ValueError("canonical journal has duplicate or missing targets")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("canonical journal snapshot projection is invalid")
            kind = entry.get("kind")
            if kind not in {"missing", "file", "directory"}:
                raise ValueError("canonical journal snapshot kind is invalid")
            if kind == "file":
                try:
                    content = base64.b64decode(
                        str(entry["content"]), validate=True
                    )
                except Exception as exc:
                    raise ValueError(
                        "canonical journal snapshot file content is invalid"
                    ) from exc
                if hashlib.sha256(content).hexdigest() != entry.get("content_sha256"):
                    raise ValueError("canonical journal snapshot file hash mismatch")
            elif kind == "directory":
                files = entry.get("files")
                hashes = entry.get("file_sha256")
                if not isinstance(files, Mapping) or not isinstance(hashes, Mapping):
                    raise ValueError(
                        "canonical journal directory snapshot projection is invalid"
                    )
                if set(files) != set(hashes):
                    raise ValueError("canonical journal directory snapshot hash mismatch")
                for relative, encoded in files.items():
                    relative_path = Path(str(relative))
                    if relative_path.is_absolute() or ".." in relative_path.parts:
                        raise ValueError(
                            "canonical journal directory snapshot path is invalid"
                        )
                    try:
                        content = base64.b64decode(str(encoded), validate=True)
                    except Exception as exc:
                        raise ValueError(
                            "canonical journal directory snapshot content is invalid"
                        ) from exc
                    if hashlib.sha256(content).hexdigest() != hashes.get(relative):
                        raise ValueError(
                            "canonical journal directory snapshot hash mismatch"
                        )
            elif set(entry) != {"path", "kind"}:
                raise ValueError("canonical journal missing snapshot projection is invalid")
        authority = self.database.fetch_one(
            """SELECT application_id, operation, journal_path, journal_sha256,
                      snapshot_json
               FROM canonical_journal_snapshots
               WHERE run_id = ? AND node_id = ? AND attempt = ?""",
            (run_id, node_id, attempt),
        )
        if authority is None:
            raise ValueError("canonical journal has no authoritative snapshot projection")
        canonical_snapshot = json.dumps(
            entries, sort_keys=True, separators=(",", ":")
        )
        if (
            authority["application_id"] != application_id
            or authority["operation"] != expected_operation
            or Path(str(authority["journal_path"])).absolute() != journal
            or authority["journal_sha256"]
            != hashlib.sha256(journal.read_bytes()).hexdigest()
            or authority["snapshot_json"] != canonical_snapshot
        ):
            raise ValueError("canonical journal integrity does not match snapshot projection")
        return dict(payload)

    def _clear_canonical_journal(
        self, journal: Path, run_id: str, node_id: str, attempt: int
    ) -> None:
        Path(journal).unlink(missing_ok=True)
        self.database.execute(
            "DELETE FROM canonical_journal_snapshots "
            "WHERE run_id = ? AND node_id = ? AND attempt = ?",
            (run_id, node_id, attempt),
        )

    @staticmethod
    def _quarantine_canonical_journal(journal: Path) -> Path | None:
        journal = Path(journal)
        if not journal.exists():
            return None
        quarantine = journal.with_name(
            f"canonical_commit_journal.quarantined.{uuid4().hex}.json"
        )
        journal.replace(quarantine)
        return quarantine

    def _recover_canonical_journals(
        self, paths: ApplicationPaths, run_id: str
    ) -> None:
        for journal in paths.cells_dir.glob("*/[0-9]*/canonical_commit_journal.json"):
            try:
                payload = self._validate_canonical_journal(journal)
                if payload.get("run_id") != run_id:
                    continue
                row = self.database.fetch_one(
                    "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
                    (run_id, payload.get("node_id"), payload.get("attempt")),
                )
                if row and row.get("status") == "validated":
                    self._clear_canonical_journal(
                        journal,
                        str(payload["run_id"]),
                        str(payload["node_id"]),
                        int(payload["attempt"]),
                    )
                    continue
                record = ManifestStore(paths)._load_attempt(
                    str(payload["node_id"]), int(payload["attempt"])
                )
                publications = []
                for output in record.manifest.get("outputs", ()):
                    manifest_path = Path(str(output["manifest_path"])).resolve()
                    persisted = read_json(manifest_path)
                    publications.append(
                        PublishedArtifact(
                            path=Path(str(persisted["path"])).resolve(),
                            manifest_path=manifest_path,
                            manifest=dict(persisted),
                        )
                    )
                if publications:
                    ManifestStore(paths).rollback_publications(
                        str(payload["node_id"]), int(payload["attempt"]), publications
                    )
                self._restore_canonical_journal(journal)
            except Exception as exc:
                self._quarantine_canonical_journal(journal)
                raise RuntimeError(
                    f"canonical commit recovery failed for {journal}: {exc}"
                ) from exc

    def _run_validators(
        self,
        context: CellExecutionContext,
        output: CellOutput,
        commands: Iterable[str],
    ) -> tuple[ValidatorResult, ...]:
        results: list[ValidatorResult] = []
        for command in commands:
            validator_context = replace(context, validator_command=command)
            validator = self.validators.get(command)
            if validator is None:
                results.append(
                    self._failed_validator_report(
                        validator_context, f"validator_not_registered:{command}"
                    )
                )
                continue
            try:
                with context.capabilities.enforce_writes():
                    raw_result = validator(validator_context, output)
                result = self._coerce_validator_result(command, raw_result)
                context.capabilities.assert_writable(result.report_path)
                if not result.report_path.is_file():
                    raise ValueError("validator report was not persisted")
                results.append(result)
            except Exception as exc:
                results.append(
                    self._failed_validator_report(
                        validator_context,
                        f"validator_error:{type(exc).__name__}:{exc}",
                    )
                )
        return tuple(results)

    def _renew_execution_leases(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        resource_locks: Iterable[Mapping[str, Any]],
    ) -> str | None:
        if not self.workspace_lease.heartbeat(
            self.workspace_owner, ttl_seconds=self.lease_seconds
        ):
            return "workspace_lease_expired"
        node_lease = self.store.renew_node_reservation(
            run_id,
            node_id,
            attempt,
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if not node_lease["renewed"]:
            return "node_lease_expired"
        for lock in resource_locks:
            renewed = self.store.renew_resource_lock(
                str(lock["resource_name"]),
                self.worker_id,
                str(lock["lease_id"]),
                lease_seconds=self.lease_seconds,
            )
            if not renewed["renewed"]:
                return f"resource_lease_expired:{lock['resource_name']}"
        return None

    @contextmanager
    def _execution_keepalive(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        resource_locks: Iterable[Mapping[str, Any]],
    ):
        """Renew workspace, node, and resource fences during long handlers."""
        state: dict[str, str | None] = {"failure": None}
        stop = threading.Event()
        locks = tuple(dict(item) for item in resource_locks)
        interval = max(min(self.lease_seconds / 3, 30.0), 0.1)

        def heartbeat() -> None:
            database = Database(
                self.database.db_path,
                authority_ledger_path=self.database.authority_ledger_path,
            )
            try:
                database.init_schema()
                store = CellStore(database)
                workspace = WorkspaceLease(
                    database, default_ttl_seconds=self.lease_seconds
                )
                workspace._fence_token = self.workspace_fence_token
                while not stop.wait(interval):
                    if not workspace.heartbeat(
                        self.workspace_owner, ttl_seconds=self.lease_seconds
                    ):
                        state["failure"] = "workspace_lease_expired"
                        return
                    node_lease = store.renew_node_reservation(
                        run_id,
                        node_id,
                        attempt,
                        self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )
                    if not node_lease["renewed"]:
                        state["failure"] = "node_lease_expired"
                        return
                    for lock in locks:
                        renewed = store.renew_resource_lock(
                            str(lock["resource_name"]),
                            self.worker_id,
                            str(lock["lease_id"]),
                            lease_seconds=self.lease_seconds,
                        )
                        if not renewed["renewed"]:
                            state["failure"] = (
                                f"resource_lease_expired:{lock['resource_name']}"
                            )
                            return
            except BaseException as exc:
                state["failure"] = f"lease_heartbeat_error:{type(exc).__name__}:{exc}"
            finally:
                database.close()

        thread = threading.Thread(
            target=heartbeat,
            name=f"cell-lease-{run_id}-{node_id}-{attempt}",
            daemon=True,
        )
        thread.start()
        try:
            yield state
        finally:
            stop.set()
            thread.join(timeout=max(interval * 2, 1.0))
            if thread.is_alive() and state["failure"] is None:
                state["failure"] = "lease_heartbeat_did_not_stop"

    def _stage_output(
        self, context: CellExecutionContext, output: CellOutput
    ) -> tuple[Path, ...]:
        staged: list[Path] = []
        for artifact_name, raw_content in output.artifacts.items():
            name = str(artifact_name)
            if not name or Path(name).name != name:
                raise ValueError("artifact name must be one path segment")
            if not isinstance(raw_content, (bytes, str)):
                raise TypeError("cell artifact content must be bytes or text")
            content = raw_content.encode("utf-8") if isinstance(raw_content, str) else raw_content
            path = context.capabilities.assert_writable(context.staging_dir / name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            staged.append(path)
        return tuple(staged)

    def _block_reserved(
        self,
        paths: ApplicationPaths,
        node: NodePlan,
        reservation: Mapping[str, Any],
        reason: str,
        staged_paths: Iterable[Path],
        validators: Iterable[ValidatorResult],
        *,
        attempt_record=None,
    ) -> CellExecutionResult:
        attempt = int(reservation["attempt"])
        manifest_store = ManifestStore(paths)
        record = attempt_record or self._load_or_begin_execution_attempt(
            manifest_store, paths, str(reservation["run_id"]), node, attempt
        )
        staged = tuple(Path(path) for path in staged_paths)
        hashes = {str(path): self._sha256_file(path) for path in staged if path.is_file()}
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                try:
                    self.database.assert_authoritative_storage()
                except ValueError:
                    return self._cancel_stale_workspace_execution(
                        reservation, node, record.path
                    )
            self.store.finish_attempt(
                str(reservation["run_id"]),
                node.node_id,
                attempt,
                "blocked",
                worker_id=self.worker_id,
                receipt={
                    "status": "blocked",
                    "paths": [str(path) for path in staged],
                    "hashes": hashes,
                    "metadata": {
                        "reason": str(reason)[:256],
                        "workspace_owner": self.workspace_owner,
                    },
                },
                workspace_owner=self.workspace_owner,
                workspace_fence_token=self.workspace_fence_token,
            )
            manifest = dict(read_json(record.path))
            manifest["validators"] = [
                self._validator_mapping(item) for item in validators
            ]
            manifest["status"] = "blocked"
            manifest["blocker"] = {
                "reason": str(reason),
                "repair_scope": node.repair_scope,
            }
            manifest["finished_at"] = utc_now_iso()
            manifest["workspace_owner"] = self.workspace_owner
            write_json(record.path, manifest)
        return CellExecutionResult(
            run_id=str(reservation["run_id"]),
            node_id=node.node_id,
            attempt=attempt,
            status="blocked",
            manifest_path=record.path,
            blocker=str(reason),
            workspace_owner=self.workspace_owner,
        )

    def _defer_reserved(
        self,
        paths: ApplicationPaths,
        node: NodePlan,
        reservation: Mapping[str, Any],
        reason: str,
        attempt_record,
    ) -> CellExecutionResult:
        attempt = int(reservation["attempt"])
        run_id = str(reservation["run_id"])
        deferred = self.store.defer_attempt(
            run_id,
            node.node_id,
            attempt,
            self.worker_id,
            reason=reason,
        )
        if not deferred["deferred"]:
            raise RuntimeError(
                f"stale or unowned cell attempt: {run_id}/{node.node_id}/{attempt}"
            )
        manifest = dict(read_json(attempt_record.path))
        manifest["status"] = "cancelled"
        manifest["blocker"] = {
            "reason": str(reason),
            "repair_scope": node.repair_scope,
        }
        manifest["finished_at"] = utc_now_iso()
        manifest["workspace_owner"] = self.workspace_owner
        write_json(attempt_record.path, manifest)
        return CellExecutionResult(
            run_id=run_id,
            node_id=node.node_id,
            attempt=attempt,
            status="deferred",
            manifest_path=attempt_record.path,
            blocker=str(reason),
            workspace_owner=self.workspace_owner,
        )

    def _begin_attempt(
        self,
        paths: ApplicationPaths,
        run_id: str,
        node: NodePlan,
        attempt: int,
        *,
        status: str,
        repair_reason: str | None = None,
        allow_unvalidated_inputs: bool = False,
        validate_draft_binding: bool = True,
    ):
        inputs, read_paths = self._inputs_for_node(
            run_id,
            paths,
            node,
            attempt=attempt,
            allow_unvalidated=allow_unvalidated_inputs,
            validate_draft_binding=validate_draft_binding,
        )
        write_paths = self._write_paths_for_node(paths, node, attempt, run_id)
        manifest_path = paths.cells_dir / node.node_id / str(attempt) / "manifest.json"
        return ManifestStore(paths).begin_attempt(
            node.node_id,
            attempt,
            run_id=run_id,
            contract_version=node.contract_version,
            inputs=inputs,
            read_paths=(*read_paths, manifest_path),
            write_paths=write_paths,
            context={
                "repair_scope": node.repair_scope,
                "repair_reason": repair_reason,
            },
            status=status,
        )

    def _load_or_begin_execution_attempt(
        self,
        store: ManifestStore,
        paths: ApplicationPaths,
        run_id: str,
        node: NodePlan,
        attempt: int,
        *,
        validate_draft_binding: bool = True,
    ):
        inputs, read_paths = self._inputs_for_node(
            run_id,
            paths,
            node,
            attempt=attempt,
            validate_draft_binding=validate_draft_binding,
        )
        manifest_path = paths.cells_dir / node.node_id / str(attempt) / "manifest.json"
        read_paths = (*read_paths, manifest_path)
        if manifest_path.is_file():
            record = store._load_attempt(node.node_id, attempt)
            if record.manifest.get("run_id") != run_id:
                raise ValueError("attempt manifest belongs to another run")
            if record.manifest.get("contract_version") != node.contract_version:
                raise ValueError("attempt manifest contract version mismatch")
            manifest = dict(record.manifest)
            if manifest.get("status") not in {"reserved", "running", "repairing"}:
                raise RuntimeError(
                    f"attempt cannot execute from status: {manifest.get('status')}"
                )
            manifest["inputs"] = store._normalize_inputs(inputs)
            manifest["capabilities"] = {
                "read_paths": [str(store._target(path)) for path in read_paths],
                "write_paths": [
                    str(store._target(path))
                    for path in self._write_paths_for_node(paths, node, attempt, run_id)
                ],
            }
            manifest["inputs_materialized_at"] = utc_now_iso()
            write_json(record.path, manifest)
            return store._load_attempt(node.node_id, attempt)
        return ManifestStore(paths).begin_attempt(
            node.node_id,
            attempt,
            run_id=run_id,
            contract_version=node.contract_version,
            inputs=inputs,
            read_paths=read_paths,
            write_paths=self._write_paths_for_node(paths, node, attempt, run_id),
            context={"repair_scope": node.repair_scope},
            status="reserved",
        )

    def _load_or_begin_unmaterialized_attempt(
        self,
        store: ManifestStore,
        paths: ApplicationPaths,
        run_id: str,
        node: NodePlan,
        attempt: int,
    ):
        manifest_path = paths.cells_dir / node.node_id / str(attempt) / "manifest.json"
        if manifest_path.is_file():
            return store._load_attempt(node.node_id, attempt)
        return ManifestStore(paths).begin_attempt(
            node.node_id,
            attempt,
            run_id=run_id,
            contract_version=node.contract_version,
            inputs={},
            read_paths=(),
            write_paths=self._write_paths_for_node(paths, node, attempt, run_id),
            context={"repair_scope": node.repair_scope},
            status="reserved",
        )

    def _context_from_manifest(
        self, paths: ApplicationPaths, node: NodePlan, manifest_path: Path
    ) -> CellExecutionContext:
        manifest = read_json(manifest_path)
        capabilities = manifest.get("capabilities", {})
        read_paths = tuple(Path(path) for path in capabilities.get("read_paths", ()))
        write_paths = tuple(Path(path) for path in capabilities.get("write_paths", ()))
        capability_set = CapabilitySet(
            application_root=paths.app_dir,
            read_paths=read_paths,
            write_paths=write_paths,
        )
        compact_context = manifest.get("context", {})
        return CellExecutionContext(
            application_id=paths.application_id,
            run_id=str(manifest["run_id"]),
            node_id=node.node_id,
            attempt=int(manifest["attempt"]),
            paths=paths,
            manifest_path=manifest_path.resolve(),
            staging_dir=(manifest_path.parent / "staging").resolve(),
            inputs=manifest.get("inputs", {}),
            output_paths=tuple(Path(path) for path in node.produces),
            capabilities=capability_set,
            repair_scope=node.repair_scope,
            repair_reason=compact_context.get("repair_reason"),
            control_db_path=self.database.db_path,
        )

    def _inputs_for_node(
        self,
        run_id: str,
        paths: ApplicationPaths,
        node: NodePlan,
        *,
        attempt: int | None = None,
        allow_unvalidated: bool = False,
        validate_draft_binding: bool = True,
    ) -> tuple[dict[str, Mapping[str, Any] | Path], tuple[Path, ...]]:
        inputs: dict[str, Mapping[str, Any] | Path] = {}
        read_paths: list[Path] = []
        dependencies = list(node.requires)
        # CV composition now consumes the validated normalized language as a
        # first-class input. Existing runs may have been planned with the old
        # contract, so include the dependency dynamically for backward
        # compatibility while new plans persist it in requires_json.
        if node.node_id == "compose_cv" and "normalize_job" not in dependencies:
            dependencies.append("normalize_job")
        for dependency in dependencies:
            row = self.database.fetch_one(
                """SELECT latest_attempt FROM cell_nodes
                   WHERE run_id = ? AND node_id = ? AND status = 'validated'""",
                (run_id, dependency),
            )
            if row is None:
                if allow_unvalidated:
                    continue
                raise RuntimeError(f"dependency is not validated: {dependency}")
            manifest_path = (
                paths.cells_dir
                / dependency
                / str(row["latest_attempt"])
                / "manifest.json"
            )
            if not manifest_path.is_file():
                raise ValueError(f"dependency attempt manifest is missing: {dependency}")
            manifest = read_json(manifest_path)
            if manifest.get("run_id") != run_id or manifest.get("status") != "validated":
                raise ValueError(f"dependency attempt manifest is not validated: {dependency}")
            if manifest.get("context", {}).get("synthetic") is True:
                continue
            read_paths.append(manifest_path)
            outputs = manifest.get("outputs", ())
            if not isinstance(outputs, list):
                raise ValueError(f"dependency outputs are invalid: {dependency}")
            expected = {Path(path).name for path in self._contract(dependency).produces}
            actual = {
                str(output.get("artifact_name", ""))
                for output in outputs
                if isinstance(output, Mapping)
            }
            if actual != expected or len(outputs) != len(expected):
                raise ValueError(f"dependency outputs do not match contract: {dependency}")
            manifest_store = ManifestStore(paths)
            for index, output in enumerate(outputs):
                if not isinstance(output, Mapping):
                    raise ValueError(f"dependency output is invalid: {dependency}/{index}")
                artifact_manifest_path = Path(str(output.get("manifest_path", "")))
                if not artifact_manifest_path.is_file():
                    raise ValueError(
                        f"dependency artifact manifest is missing: {dependency}/{index}"
                    )
                persisted_artifact = manifest_store._persisted_validated_artifact(
                    read_json(artifact_manifest_path), run_id
                )
                if (
                    persisted_artifact.get("node_id") != dependency
                    or persisted_artifact.get("attempt") != int(row["latest_attempt"])
                ):
                    raise ValueError(
                        f"dependency artifact belongs to a stale attempt: {dependency}/{index}"
                    )
                for field in (
                    "artifact_name",
                    "path",
                    "sha256",
                    "revision",
                    "manifest_path",
                ):
                    if output.get(field) != persisted_artifact.get(field):
                        raise ValueError(
                            f"dependency output provenance mismatch: {dependency}/{field}"
                        )
                if persisted_artifact["artifact_name"] not in expected:
                    raise ValueError(
                        f"dependency artifact is not declared by contract: {dependency}"
                    )
                key = f"{dependency}:{output.get('artifact_name', index)}"
                inputs[key] = {
                    "path": persisted_artifact["path"],
                    "sha256": persisted_artifact["sha256"],
                    "revision": persisted_artifact.get("revision"),
                    "source_kind": "validated_artifact",
                    "application_id": persisted_artifact["application_id"],
                    "run_id": persisted_artifact["run_id"],
                    "node_id": persisted_artifact["node_id"],
                    "artifact_manifest_path": persisted_artifact["manifest_path"],
                }
                read_paths.append(Path(str(persisted_artifact["path"])))
                read_paths.append(Path(str(persisted_artifact["manifest_path"])))
        if node.node_id == "normalize_job" and paths.job_description.is_file():
            inputs["job_description"] = paths.job_description
            read_paths.append(paths.job_description)
            if paths.identity.is_file():
                read_paths.append(paths.identity)
        if node.node_id == "analyze_fit":
            read_paths.append(paths.fit_map_draft)
            read_paths.extend(
                path
                for path in (paths.job_description, paths.identity, paths.derived_dir)
                if path.exists()
            )
            if validate_draft_binding:
                self._validate_fit_map_draft_binding(
                    paths,
                    run_id=run_id,
                    attempt=int(attempt or 0),
                )
            if paths.fit_map_draft.is_file():
                inputs["fit_map_draft"] = paths.fit_map_draft
        if node.node_id == "compose_cv":
            read_paths.extend(
                path
                for path in (
                    paths.job_description,
                    paths.identity,
                    paths.derived_dir,
                    paths.fit_map_draft,
                )
                if path.exists()
            )
            if int(attempt or 0) > 1:
                # A repaired compose attempt must be able to inspect the
                # failed review that requested the repair. The candidate is
                # written by the external repair agent and consumed by the
                # compose handler in this same application/run scope.
                review_row = self.database.fetch_one(
                    "SELECT latest_attempt FROM cell_nodes "
                    "WHERE run_id = ? AND node_id = ?",
                    (run_id, "review_cv"),
                )
                if review_row is not None and int(review_row["latest_attempt"] or 0) > 0:
                    review_staging = (
                        paths.cells_dir
                        / "review_cv"
                        / str(review_row["latest_attempt"])
                        / "staging"
                    )
                    read_paths.extend(
                        path
                        for path in (
                            review_staging / "cv_review.json",
                            review_staging / "polish_review.json",
                        )
                        if path.exists()
                    )
                read_paths.append(
                    paths.requests_dir
                    / "cellular"
                    / run_id
                    / "repair"
                    / str(attempt)
                    / "cv_content.json"
                )
        if node.node_id == "capture_source":
            source_input = paths.app_dir / "source_input.md"
            if source_input.is_file():
                inputs["source_description"] = source_input
                read_paths.append(source_input)
            if paths.identity.is_file():
                inputs["application_identity"] = paths.identity
                read_paths.append(paths.identity)
        if node.node_id in {"deliver_cv", "sync_notion_initial", "sync_notion_final"}:
            read_paths.append(paths.cells_dir / node.node_id / "receipts" / run_id)
            if paths.identity.is_file():
                inputs["application_identity"] = paths.identity
                read_paths.append(paths.identity)
            if paths.job_description.is_file():
                inputs["job_description"] = paths.job_description
                read_paths.append(paths.job_description)
        if node.node_id == "deliver_cv" and paths.fit_map.is_file():
            inputs["fit_map.json"] = {
                "path": str(paths.fit_map.resolve()),
                "sha256": sha256_file(paths.fit_map),
                "application_id": paths.application_id,
                "source_kind": "application_fit_map",
            }
            read_paths.append(paths.fit_map.resolve())
        if node.node_id in {"review_cv", "deliver_cv"}:
            job_extract = paths.derived_dir / "job_extract.json"
            if job_extract.is_file():
                read_paths.append(job_extract.resolve())
        if node.node_id == "review_cv":
            compose_row = self.database.fetch_one(
                """SELECT latest_attempt FROM cell_nodes
                   WHERE run_id = ? AND node_id = ? AND status = 'validated'""",
                (run_id, "compose_cv"),
            )
            if compose_row is not None:
                compose_manifest_path = (
                    paths.cells_dir
                    / "compose_cv"
                    / str(compose_row["latest_attempt"])
                    / "manifest.json"
                )
                if compose_manifest_path.is_file():
                    compose_manifest = read_json(compose_manifest_path)
                    for output in compose_manifest.get("outputs") or ():
                        if not isinstance(output, Mapping):
                            continue
                        if output.get("artifact_name") != "cv_content.json":
                            continue
                        persisted = ManifestStore(paths)._persisted_validated_artifact(
                            read_json(Path(str(output.get("manifest_path") or ""))),
                            run_id,
                        )
                        inputs["cv_content.json"] = {
                            "path": persisted["path"],
                            "sha256": persisted["sha256"],
                            "revision": persisted.get("revision"),
                            "source_kind": "validated_artifact",
                            "application_id": persisted["application_id"],
                            "run_id": persisted["run_id"],
                            "node_id": persisted["node_id"],
                            "artifact_manifest_path": persisted["manifest_path"],
                        }
                        read_paths.append(Path(str(persisted["path"])))
                        read_paths.append(Path(str(persisted["manifest_path"])))
                        break
        return inputs, tuple(read_paths)

    @staticmethod
    def _validate_fit_map_draft_binding(
        paths: ApplicationPaths, *, run_id: str, attempt: int
    ) -> None:
        binding_path = paths.app_dir / "fit_map.draft.binding.json"
        reasons: list[str] = []
        if not binding_path.is_file():
            binding = {}
            reasons.append("binding_missing")
        else:
            try:
                binding = read_json(binding_path)
            except Exception as exc:
                binding = {}
                reasons.append(f"invalid_json:{type(exc).__name__}")
        if paths.fit_map_draft.is_file():
            draft_hash = hashlib.sha256(paths.fit_map_draft.read_bytes()).hexdigest()
        else:
            draft_hash = ""
            reasons.append("draft_missing")
        job_hash = (
            hashlib.sha256(paths.job_description.read_bytes()).hexdigest()
            if paths.job_description.is_file()
            else ""
        )
        expected_manifest = (
            paths.cells_dir / "analyze_fit" / str(attempt) / "manifest.json"
        ).resolve()
        expected = {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": "analyze_fit",
            "attempt": attempt,
            "job_fingerprint": job_hash,
            "draft_sha256": draft_hash,
        }
        for key, value in expected.items():
            if binding.get(key) != value:
                reasons.append(f"{key}_mismatch")
        manifest_value = str(binding.get("manifest_path") or "").strip()
        if not manifest_value:
            reasons.append("manifest_path_missing")
        elif Path(manifest_value).resolve() != expected_manifest:
            reasons.append("manifest_path_mismatch")
        if not reasons:
            return
        quarantine = (
            paths.requests_dir
            / "quarantine"
            / f"{utc_now_iso().replace(':', '').replace('+', '_')}_invalid_draft_binding"
        )
        quarantine.mkdir(parents=True, exist_ok=True)
        if paths.fit_map_draft.exists():
            paths.fit_map_draft.replace(quarantine / "invalid_fit_map.draft.json")
        if binding_path.exists():
            binding_path.replace(quarantine / "invalid_fit_map.draft.binding.json")
        raise ValueError("draft_binding_invalid:" + ",".join(reasons))

    @staticmethod
    def _write_paths_for_node(
        paths: ApplicationPaths, node: NodePlan, attempt: int, run_id: str = ""
    ) -> tuple[Path, ...]:
        write_paths = [
            paths.cells_dir / node.node_id / str(attempt) / "staging",
            paths.reviews_dir,
        ]
        if node.node_id == "capture_source":
            write_paths.extend((paths.job_description, paths.source_metadata))
        elif node.node_id == "normalize_job":
            write_paths.append(paths.derived_dir)
        elif node.node_id == "analyze_fit":
            write_paths.append(paths.fit_map_draft)
        elif node.node_id == "compose_cv" and attempt > 1:
            write_paths.append(
                paths.requests_dir
                / "cellular"
                / run_id
                / "repair"
                / str(attempt)
                / "cv_content.json"
            )
        elif node.node_id in {"deliver_cv", "sync_notion_initial", "sync_notion_final"}:
            write_paths.append(paths.cells_dir / node.node_id / "receipts" / run_id)
        return tuple(write_paths)

    def _cancel_expired_execution(
        self,
        paths: ApplicationPaths,
        node: NodePlan,
        reservation: Mapping[str, Any],
        manifest_path: Path,
    ) -> CellExecutionResult:
        attempt = int(reservation["attempt"])
        cancelled = self.store.cancel_expired_reservation(
            str(reservation["run_id"]), node.node_id, attempt, self.worker_id
        )
        if manifest_path.is_file():
            manifest = dict(read_json(manifest_path))
            manifest["status"] = "cancelled"
            manifest["blocker"] = {
                "reason": "node_lease_expired",
                "repair_scope": node.repair_scope,
            }
            manifest["finished_at"] = utc_now_iso()
            manifest["workspace_owner"] = self.workspace_owner
            write_json(manifest_path, manifest)
        return CellExecutionResult(
            run_id=str(reservation["run_id"]),
            node_id=node.node_id,
            attempt=attempt,
            status="cancelled",
            manifest_path=manifest_path,
            blocker="node_lease_expired",
            workspace_owner=self.workspace_owner,
        )

    def _cancel_stale_workspace_execution(
        self,
        reservation: Mapping[str, Any],
        node: NodePlan,
        manifest_path: Path,
    ) -> CellExecutionResult:
        """Return a fenced result without mutating DB/manifests after authority loss."""
        return CellExecutionResult(
            run_id=str(reservation["run_id"]),
            node_id=node.node_id,
            attempt=int(reservation["attempt"]),
            status="cancelled",
            manifest_path=manifest_path,
            blocker="workspace_lease_expired",
            workspace_owner=self.workspace_owner,
        )

    def _cancel_capability_violation(
        self,
        reservation: Mapping[str, Any],
        node: NodePlan,
        manifest_path: Path,
        detail: str,
    ) -> CellExecutionResult:
        """Cancel an owned attempt that tried to escape its immutable manifest."""
        run_id = str(reservation["run_id"])
        attempt = int(reservation["attempt"])
        reason = f"capability_violation:{detail}"
        # Do not perform a terminal commit after an escape attempt: the
        # handler may also have changed authority while it was running.  The
        # reservation remains fenced and can only be reclaimed after expiry.
        return CellExecutionResult(
            run_id=run_id,
            node_id=node.node_id,
            attempt=attempt,
            status="cancelled",
            manifest_path=manifest_path,
            blocker=reason,
            workspace_owner=self.workspace_owner,
        )

    def _set_manual_terminal(
        self,
        run_id: str,
        paths: ApplicationPaths,
        node_id: str,
        status: str,
        reason: str,
    ) -> None:
        plan, _ = self._load_run(run_id)
        node = self._node(plan, node_id)
        with self.database.authority_ledger_lock():
            if self.database.authority_ledger_path is not None:
                self.database.assert_authoritative_storage()
            self._commit_manual_terminal(
                run_id, paths, node, status=status, reason=reason
            )

    def _commit_manual_terminal(
        self,
        run_id: str,
        paths: ApplicationPaths,
        node: NodePlan,
        *,
        status: str,
        reason: str,
    ) -> None:
        node_id = node.node_id
        if self.workspace_fence_token is None:
            raise ValueError("workspace fence token is required for terminal commit")
        now = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
            workspace_owned = conn.execute(
                """SELECT 1 FROM workspace_leases
                   WHERE lease_name = 'authoritative-workspace'
                     AND worker_id = ? AND lease_epoch = ?
                     AND expires_at > ?""",
                (
                    self.workspace_owner,
                    int(self.workspace_fence_token),
                    now,
                ),
            ).fetchone()
            if workspace_owned is None:
                raise RuntimeError("stale authoritative workspace lease")
            row = conn.execute(
                "SELECT latest_attempt FROM cell_nodes "
                "WHERE run_id = ? AND node_id = ?",
                (run_id, node_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown cell node: {run_id}/{node_id}")
            attempt = max(1, int(row["latest_attempt"]))
            if int(row["latest_attempt"]) == 0:
                conn.execute(
                    """INSERT INTO cell_attempts
                       (run_id, node_id, attempt, worker_id, status, created_at, finished_at,
                        detail_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        node_id,
                        attempt,
                        self.worker_id,
                        status,
                        now,
                        now,
                        json.dumps(
                            {
                                "status": status,
                                "paths": [],
                                "hashes": {},
                                "metadata": {"reason": reason},
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
            else:
                conn.execute(
                    """UPDATE cell_attempts SET status = ?, finished_at = ?, detail_json = ?
                       WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                    (
                        status,
                        now,
                        json.dumps(
                            {
                                "status": status,
                                "paths": [],
                                "hashes": {},
                                "metadata": {"reason": reason},
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        run_id,
                        node_id,
                        attempt,
                    ),
                )
            conn.execute(
                """UPDATE cell_nodes SET status = ?, latest_attempt = ?, reserved_by = NULL,
                   reservation_expires_at = NULL, updated_at = ?
                   WHERE run_id = ? AND node_id = ?""",
                (status, attempt, now, run_id, node_id),
            )
            manifest_path = paths.cells_dir / node_id / str(attempt) / "manifest.json"
            if manifest_path.is_file():
                manifest = dict(read_json(manifest_path))
            else:
                record = ManifestStore(paths).begin_attempt(
                    node_id,
                    attempt,
                    run_id=run_id,
                    contract_version=node.contract_version,
                    read_paths=(),
                    write_paths=(
                        paths.cells_dir / node_id / str(attempt) / "staging",
                        paths.reviews_dir,
                    ),
                    context={"repair_scope": node.repair_scope, "synthetic": True},
                    status=status,
                )
                manifest = dict(record.manifest)
            manifest["status"] = status
            manifest["finished_at"] = now
            if status == "blocked":
                manifest["blocker"] = {
                    "reason": reason,
                    "repair_scope": node.repair_scope,
                }
            write_json(manifest_path, manifest)

    def _failed_validator_report(
        self, context: CellExecutionContext, reason: str
    ) -> ValidatorResult:
        safe_command = context.validator_command.replace(":", "-").replace("/", "-")
        report = context.paths.reviews_dir / (
            f"{context.node_id}-{context.attempt}-{safe_command}.json"
        )
        context.capabilities.assert_writable(report)
        write_json(
            report,
            {
                "command": context.validator_command,
                "result": "failed",
                "reason": reason,
            },
        )
        return ValidatorResult.failed(context.validator_command, report, reason)

    @staticmethod
    def _coerce_validator_result(
        command: str, result: ValidatorResult | Mapping[str, Any]
    ) -> ValidatorResult:
        if isinstance(result, ValidatorResult):
            if result.command != command:
                raise ValueError("validator result command mismatch")
            if result.result not in {"passed", "failed"}:
                raise ValueError("validator result must be passed or failed")
            return result
        if isinstance(result, Mapping):
            return ValidatorResult(
                command=str(result.get("command", command)),
                result=str(result.get("result", "failed")),
                report_path=Path(str(result.get("report_path", ""))),
                reason=str(result.get("reason", "")),
            )
        raise TypeError("validator must return ValidatorResult or a result mapping")

    @staticmethod
    def _validator_mapping(result: ValidatorResult) -> dict[str, Any]:
        return {
            "command": result.command,
            "result": result.result,
            "report_path": str(result.report_path.resolve()),
            "executed_at": utc_now_iso(),
        }

    def _owned_ready_reservations(self, run_id: str) -> list[dict[str, Any]]:
        now = utc_now_iso()
        rows = self.database.fetch_all(
            """SELECT node_id, latest_attempt AS attempt
               FROM cell_nodes
               WHERE run_id = ? AND status = 'reserved' AND reserved_by = ?
                 AND reservation_expires_at > ?
               ORDER BY node_id""",
            (run_id, self.worker_id, now),
        )
        return [
            {
                "status": "reserved",
                "run_id": run_id,
                "node_id": row["node_id"],
                "attempt": row["attempt"],
                "worker_id": self.worker_id,
            }
            for row in rows
            if self._dependencies_validated(run_id, row["node_id"])
        ]

    def _reactivate_ready_superseded(self, run_id: str) -> None:
        rows = self.database.fetch_all(
            "SELECT node_id FROM cell_nodes WHERE run_id = ? AND status = 'superseded'",
            (run_id,),
        )
        now = utc_now_iso()
        for row in rows:
            node_id = str(row["node_id"])
            if self._dependencies_validated(run_id, node_id):
                self.database.execute(
                    """UPDATE cell_nodes SET status = 'repairing', updated_at = ?
                       WHERE run_id = ? AND node_id = ? AND status = 'superseded'""",
                    (now, run_id, node_id),
                )

    def _dependencies_validated(self, run_id: str, node_id: str) -> bool:
        row = self.database.fetch_one(
            "SELECT requires_json FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
        if row is None:
            raise KeyError(f"unknown cell node: {run_id}/{node_id}")
        requirements = json.loads(row["requires_json"])
        if not requirements:
            return True
        statuses = {
            item["node_id"]: item["status"]
            for item in self.database.fetch_all(
                "SELECT node_id, status FROM cell_nodes WHERE run_id = ?",
                (run_id,),
            )
        }
        return all(statuses.get(required) == "validated" for required in requirements)

    def _contract_descendants(
        self, node_id: str, planned_nodes: set[str]
    ) -> tuple[str, ...]:
        descendants: set[str] = set()
        pending = list(self._contract(node_id).invalidates)
        while pending:
            descendant = pending.pop()
            if descendant in descendants:
                continue
            descendants.add(descendant)
            contract = CELL_CONTRACTS.get(descendant)
            if contract is not None:
                pending.extend(contract.invalidates)
        return tuple(sorted(descendants & planned_nodes))

    def _latest_fit_map_revision_hash(
        self, run_id: str, node_id: str
    ) -> str | None:
        row = self.database.fetch_one(
            """SELECT path FROM artifacts
               WHERE run_id = ? AND node_id = ? AND artifact_name = 'fit_map.json'
               ORDER BY created_at DESC, artifact_id DESC LIMIT 1""",
            (run_id, node_id),
        )
        return self._fit_map_revision_hash(Path(row["path"])) if row is not None else None

    @staticmethod
    def _fit_map_revision_hash(path: Path) -> str:
        """Hash FIT_MAP meaning while excluding attempt-local provenance.

        ``produced_by_attempt`` is required audit metadata and necessarily changes
        for every repair. It must not invalidate descendants when the published
        FIT_MAP content is otherwise unchanged.
        """
        raw = Path(path).read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return hashlib.sha256(raw).hexdigest()
        provenance = payload.get("provenance")
        if isinstance(provenance, dict):
            payload = dict(payload)
            payload["provenance"] = {
                key: value
                for key, value in provenance.items()
                if key != "produced_by_attempt"
            }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _supersede_contract_descendants(
        self,
        paths: ApplicationPaths,
        run_id: str,
        node_id: str,
        planned_nodes: set[str],
    ) -> tuple[str, ...]:
        descendants = self._contract_descendants(node_id, planned_nodes)
        now = utc_now_iso()
        superseded: list[str] = []
        with self.database.transaction(immediate=True) as conn:
            for descendant in descendants:
                row = conn.execute(
                    """SELECT status, latest_attempt FROM cell_nodes
                       WHERE run_id = ? AND node_id = ?""",
                    (run_id, descendant),
                ).fetchone()
                if row is None or row["status"] == "planned":
                    continue
                conn.execute(
                    """UPDATE cell_nodes
                       SET status = 'superseded', reserved_by = NULL,
                           reservation_expires_at = NULL, updated_at = ?
                       WHERE run_id = ? AND node_id = ?""",
                    (now, run_id, descendant),
                )
                if int(row["latest_attempt"]) > 0:
                    conn.execute(
                        """UPDATE cell_attempts SET status = 'superseded'
                           WHERE run_id = ? AND node_id = ? AND attempt = ?""",
                        (run_id, descendant, int(row["latest_attempt"])),
                    )
                superseded.append(descendant)
        for descendant in superseded:
            self._mark_attempt_manifest_superseded(paths, run_id, descendant)
        return tuple(superseded)

    def _mark_attempt_manifest_superseded(
        self, paths: ApplicationPaths, run_id: str, node_id: str
    ) -> None:
        row = self.database.fetch_one(
            "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
        if row is None or int(row["latest_attempt"]) <= 0:
            return
        manifest_path = paths.cells_dir / node_id / str(row["latest_attempt"]) / "manifest.json"
        if manifest_path.is_file():
            manifest = dict(read_json(manifest_path))
            manifest["status"] = "superseded"
            manifest["superseded_at"] = utc_now_iso()
            write_json(manifest_path, manifest)

    def _load_run(self, run_id: str) -> tuple[RunPlan, ApplicationPaths]:
        row = self.database.fetch_one(
            "SELECT application_id, graph_json FROM application_runs WHERE run_id = ?",
            (run_id,),
        )
        if row is None:
            raise KeyError(f"unknown cell run: {run_id}")
        paths = self._paths(str(row["application_id"]))
        plan_path = paths.plans_dir / f"{run_id}.json"
        if not plan_path.is_file():
            raise ValueError(f"persisted run plan not found: {plan_path}")
        payload = read_json(plan_path)
        if payload != json.loads(row["graph_json"]):
            raise ValueError("database graph does not match persisted run plan")
        nodes = tuple(
            NodePlan(
                node_id=item["node_id"],
                requires=tuple(item["requires"]),
                produces=tuple(item["produces"]),
                validators=tuple(item["validators"]),
                resources=tuple(item["resources"]),
                invalidates=tuple(item["invalidates"]),
                repair_scope=item["repair_scope"],
                max_attempts=int(item["max_attempts"]),
                allows_external_effect=bool(item["allows_external_effect"]),
                contract_version=item["contract_version"],
            )
            for item in payload["nodes"]
        )
        plan = RunPlan(
            run_id=payload["run_id"],
            application_id=payload["application_id"],
            nodes=nodes,
            edges=tuple(tuple(edge) for edge in payload["edges"]),
            resource_locks=tuple(payload["resource_locks"]),
            created_at=payload["created_at"],
            contract_version=payload["contract_version"],
            execution_mode=payload.get("execution_mode", "wave"),
        )
        if plan.run_id != run_id or plan.application_id != row["application_id"]:
            raise ValueError("persisted run plan identity mismatch")
        return plan, self._run_scoped_paths(paths, run_id)

    @staticmethod
    def _run_scoped_paths(paths: ApplicationPaths, run_id: str) -> ApplicationPaths:
        if (
            not run_id
            or run_id in {".", ".."}
            or Path(run_id).name != run_id
            or "\\" in run_id
        ):
            raise ValueError("run_id must be a non-empty relative path segment")
        scoped = replace(
            paths,
            cells_dir=paths.cells_dir / run_id,
            artifacts_dir=paths.artifacts_dir / run_id,
            reviews_dir=paths.reviews_dir / run_id,
            run_completion_manifest=(
                paths.app_dir / "runs" / run_id / "run_completion_manifest.json"
            ),
        )
        for directory in (
            scoped.cells_dir,
            scoped.artifacts_dir,
            scoped.reviews_dir,
            scoped.run_completion_manifest.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return scoped

    def _paths(self, application_id: str) -> ApplicationPaths:
        paths = paths_for(application_id, root=self.applications_root)
        for directory in (
            paths.app_dir,
            paths.plans_dir,
            paths.cells_dir,
            paths.artifacts_dir,
            paths.reviews_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return paths

    @staticmethod
    def _node(plan: RunPlan, node_id: str) -> NodePlan:
        node = next((item for item in plan.nodes if item.node_id == node_id), None)
        if node is None:
            raise KeyError(f"unknown plan node: {node_id}")
        return node

    @staticmethod
    def _contract(node_id: str) -> CellContract:
        contract = CELL_CONTRACTS.get(node_id)
        if contract is None:
            raise KeyError(f"unknown cell contract: {node_id}")
        return contract

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
