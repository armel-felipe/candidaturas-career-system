from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.cells.capabilities import CapabilitySet
from career.cells.contracts import CELL_CONTRACTS, CellContract
from career.cells.handlers import (
    CellExecutionContext,
    CellHandler,
    CellOutput,
    CellValidator,
    ValidatorResult,
)
from career.cells.manifests import ManifestStore, RunCompletion
from career.cells.planner import NodePlan, RunPlan, compile_run_plan
from career.services.application_context import APPLICATIONS_DIR, ApplicationPaths, paths_for
from career.services.cell_store import CellStore
from career.services.database import Database
from career.utils import read_json, utc_now_iso, write_json


@dataclass(frozen=True)
class CellExecutionResult:
    run_id: str
    node_id: str
    attempt: int
    status: str
    manifest_path: Path
    artifact_manifest_paths: tuple[Path, ...] = ()
    blocker: str = ""


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

    def register_handler(self, node_id: str, handler: CellHandler) -> None:
        self._contract(node_id)
        self.handlers[node_id] = handler

    def register_validator(self, command: str, validator: CellValidator) -> None:
        if not command:
            raise ValueError("validator command is required")
        self.validators[command] = validator

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

    def plan(self, application_id: str, deliverables: Iterable[str]) -> RunPlan:
        paths = self._paths(application_id)
        plan = compile_run_plan(application_id, deliverables, paths)
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

    def run_ready(self, run_id: str) -> tuple[CellExecutionResult, ...]:
        plan, paths = self._load_run(run_id)
        results: list[CellExecutionResult] = []

        for reservation in self._owned_ready_reservations(run_id):
            node = self._node(plan, reservation["node_id"])
            results.append(self._execute_reserved(plan, paths, node, reservation))

        self._reactivate_ready_superseded(run_id)
        for ready in self.store.list_ready_nodes(run_id):
            node_id = str(ready["node_id"])
            if not self._dependencies_validated(run_id, node_id):
                continue
            reservation = self.store.reserve_node(
                run_id,
                node_id,
                self.worker_id,
                lease_seconds=self.lease_seconds,
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
        return tuple(results)

    def repair(self, run_id: str, node_id: str, reason: str) -> RepairResult:
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

    def resume(self, run_id: str) -> ResumeResult:
        plan, paths = self._load_run(run_id)
        ManifestStore(paths)._load_run_plan_nodes(run_id)
        statuses = {
            row["node_id"]: row["status"]
            for row in self.database.fetch_all(
                "SELECT node_id, status FROM cell_nodes WHERE run_id = ? ORDER BY node_id",
                (run_id,),
            )
        }
        persisted_nodes = {node.node_id for node in plan.nodes}
        if set(statuses) != persisted_nodes:
            raise ValueError("database nodes do not match persisted run plan")
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
        _plan, paths = self._load_run(run_id)
        completion = ManifestStore(paths).finish_run(
            run_id,
            validated_artifacts=(),
            blocked_nodes=(),
        )
        self.database.execute(
            "UPDATE application_runs SET status = ?, updated_at = ? WHERE run_id = ?",
            (completion.manifest["status"], utc_now_iso(), run_id),
        )
        return completion

    def is_terminal(self, run_id: str) -> bool:
        statuses = self.resume(run_id).statuses.values()
        return bool(statuses) and all(status in {"validated", "blocked"} for status in statuses)

    def mark_validated(self, run_id: str, node_id: str) -> None:
        """Persist a synthetic validated attempt for orchestration tests and imports."""
        _plan, paths = self._load_run(run_id)
        self._set_manual_terminal(run_id, paths, node_id, "validated", "")

    def fail(self, run_id: str, node_id: str, reason: str) -> None:
        """Persist a synthetic blocked attempt for orchestration tests and imports."""
        _plan, paths = self._load_run(run_id)
        self._set_manual_terminal(run_id, paths, node_id, "blocked", reason)

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
            try:
                output = handler(context)
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
            lease_failure = self._renew_execution_leases(
                plan.run_id, node.node_id, attempt, acquired_resources
            )
            if lease_failure == "node_lease_expired":
                return self._cancel_expired_execution(
                    paths, node, reservation, attempt_record.path
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
                return self._block_reserved(
                    paths,
                    node,
                    reservation,
                    lease_failure,
                    (),
                    validator_results,
                    attempt_record=manifest_store._load_attempt(node.node_id, attempt),
                )
            try:
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
            except Exception as exc:
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
            )
        finally:
            for lock in reversed(acquired_resources):
                self.store.release_resource_lock(
                    str(lock["resource_name"]),
                    self.worker_id,
                    lease_id=str(lock["lease_id"]),
                )

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
                "metadata": {"reason": str(reason)[:256]},
            },
        )
        manifest = dict(read_json(record.path))
        manifest["validators"] = [self._validator_mapping(item) for item in validators]
        manifest["status"] = "blocked"
        manifest["blocker"] = {
            "reason": str(reason),
            "repair_scope": node.repair_scope,
        }
        manifest["finished_at"] = utc_now_iso()
        write_json(record.path, manifest)
        return CellExecutionResult(
            run_id=str(reservation["run_id"]),
            node_id=node.node_id,
            attempt=attempt,
            status="blocked",
            manifest_path=record.path,
            blocker=str(reason),
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
        write_json(attempt_record.path, manifest)
        return CellExecutionResult(
            run_id=run_id,
            node_id=node.node_id,
            attempt=attempt,
            status="deferred",
            manifest_path=attempt_record.path,
            blocker=str(reason),
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
    ):
        inputs, read_paths = self._inputs_for_node(
            run_id,
            paths,
            node,
            allow_unvalidated=allow_unvalidated_inputs,
        )
        write_paths = self._write_paths_for_node(paths, node, attempt)
        return ManifestStore(paths).begin_attempt(
            node.node_id,
            attempt,
            run_id=run_id,
            contract_version=node.contract_version,
            inputs=inputs,
            read_paths=read_paths,
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
    ):
        inputs, read_paths = self._inputs_for_node(run_id, paths, node)
        manifest_path = paths.cells_dir / node.node_id / str(attempt) / "manifest.json"
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
                    for path in self._write_paths_for_node(paths, node, attempt)
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
            write_paths=self._write_paths_for_node(paths, node, attempt),
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
            write_paths=self._write_paths_for_node(paths, node, attempt),
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
        )

    def _inputs_for_node(
        self,
        run_id: str,
        paths: ApplicationPaths,
        node: NodePlan,
        *,
        allow_unvalidated: bool = False,
    ) -> tuple[dict[str, Mapping[str, Any] | Path], tuple[Path, ...]]:
        inputs: dict[str, Mapping[str, Any] | Path] = {}
        read_paths: list[Path] = []
        for dependency in node.requires:
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
                }
                read_paths.append(Path(str(persisted_artifact["path"])))
        if node.node_id == "normalize_job" and paths.job_description.is_file():
            inputs["job_description"] = paths.job_description
            read_paths.append(paths.job_description)
        if node.node_id == "analyze_fit" and paths.fit_map_draft.is_file():
            inputs["fit_map_draft"] = paths.fit_map_draft
            read_paths.append(paths.fit_map_draft)
        if node.node_id == "capture_source":
            source_input = paths.app_dir / "source_input.md"
            if source_input.is_file():
                inputs["source_description"] = source_input
                read_paths.append(source_input)
            if paths.identity.is_file():
                inputs["application_identity"] = paths.identity
                read_paths.append(paths.identity)
        return inputs, tuple(read_paths)

    @staticmethod
    def _write_paths_for_node(
        paths: ApplicationPaths, node: NodePlan, attempt: int
    ) -> tuple[Path, ...]:
        write_paths = [
            paths.cells_dir / node.node_id / str(attempt) / "staging",
            paths.reviews_dir,
        ]
        if node.node_id == "capture_source":
            write_paths.extend((paths.job_description, paths.source_metadata))
        elif node.node_id == "normalize_job":
            write_paths.append(paths.derived_dir)
        elif node.node_id == "compose_cv":
            write_paths.append(paths.cv_content)
        elif node.node_id == "review_cv":
            write_paths.append(paths.derived_dir)
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
            write_json(manifest_path, manifest)
        return CellExecutionResult(
            run_id=str(reservation["run_id"]),
            node_id=node.node_id,
            attempt=attempt,
            status="cancelled",
            manifest_path=manifest_path,
            blocker="node_lease_expired",
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
        row = self.database.fetch_one(
            "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (run_id, node_id),
        )
        if row is None:
            raise KeyError(f"unknown cell node: {run_id}/{node_id}")
        attempt = max(1, int(row["latest_attempt"]))
        now = utc_now_iso()
        with self.database.transaction(immediate=True) as conn:
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
