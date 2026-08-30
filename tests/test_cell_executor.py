from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import write_json


def _prepare_bound_analyze_fit(executor: CellExecutor, run_id: str) -> None:
    plan, application_paths = executor._load_run(run_id)
    application_id = plan.application_id
    node = executor.database.fetch_one(
        "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        (run_id, "analyze_fit"),
    )
    assert node is not None
    attempt = int(node["latest_attempt"]) + 1
    manifest_path = (
        application_paths.cells_dir / "analyze_fit" / str(attempt) / "manifest.json"
    )
    application_paths.fit_map_draft.parent.mkdir(parents=True, exist_ok=True)
    application_paths.fit_map_draft.write_text(
        '{"cargo": "Operations Lead"}', encoding="utf-8"
    )
    job_hash = (
        hashlib.sha256(application_paths.job_description.read_bytes()).hexdigest()
        if application_paths.job_description.is_file()
        else ""
    )
    write_json(
        application_paths.app_dir / "fit_map.draft.binding.json",
        {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": application_id,
            "run_id": run_id,
            "node_id": "analyze_fit",
            "attempt": attempt,
            "job_fingerprint": job_hash,
            "draft_sha256": hashlib.sha256(
                application_paths.fit_map_draft.read_bytes()
            ).hexdigest(),
            "manifest_path": str(manifest_path.resolve()),
        },
    )


@pytest.fixture
def orchestrator(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    executor = CellExecutor(database, applications_root=tmp_path / "applications")
    yield executor
    database.close()


def test_failed_render_repair_does_not_rerun_fit_map(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv"}).run_id
    orchestrator.mark_validated(run_id, "analyze_fit")
    orchestrator.mark_validated(run_id, "compose_cv")
    orchestrator.fail(run_id, "render_cv", "docx_layout")

    repaired = orchestrator.repair(run_id, "render_cv", "docx_layout")

    assert repaired.attempt == 2
    assert orchestrator.node_status(run_id, "analyze_fit") == "validated"
    assert orchestrator.store.reserve_node(run_id, "review_cv", "other-worker") == {
        "status": "busy"
    }


def test_executor_never_runs_child_before_parent(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv"}).run_id

    assert "render_cv" not in orchestrator.ready_nodes(run_id)


def test_legacy_plan_without_execution_mode_loads_as_wave(orchestrator):
    plan = orchestrator.plan("legacy-app", {"cv"})
    plan_path = (
        orchestrator._paths("legacy-app").plans_dir / f"{plan.run_id}.json"
    )
    persisted = json.loads(plan_path.read_text(encoding="utf-8"))
    persisted.pop("execution_mode")
    legacy_graph = json.dumps(persisted, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    plan_path.write_text(legacy_graph, encoding="utf-8")
    orchestrator.database.execute(
        "UPDATE application_runs SET graph_json = ? WHERE run_id = ?",
        (legacy_graph, plan.run_id),
    )

    loaded, _paths = orchestrator._load_run(plan.run_id)

    assert loaded.execution_mode == "wave"


def test_two_runs_for_same_application_use_distinct_attempt_data(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_paths = paths_for("app-1", root=applications_root)
    application_paths.app_dir.mkdir(parents=True)
    application_paths.job_description.write_text("Job description", encoding="utf-8")

    def handler(context):
        return CellOutput(
            artifacts={
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            }
        )

    def validator(context, output):
        report = context.paths.reviews_dir / f"{context.node_id}-{context.attempt}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": handler},
        validators={"context:validate": validator},
    )
    first = executor.plan("app-1", {"cv"})
    second = executor.plan("app-1", {"cv"})

    first_result = executor.run_ready(first.run_id)[0]
    second_result = executor.run_ready(second.run_id)[0]

    assert first_result.status == second_result.status == "validated"
    assert first_result.manifest_path != second_result.manifest_path
    assert first.run_id in first_result.manifest_path.parts
    assert second.run_id in second_result.manifest_path.parts
    assert json.loads(first_result.manifest_path.read_text(encoding="utf-8"))["run_id"] == first.run_id
    assert json.loads(second_result.manifest_path.read_text(encoding="utf-8"))["run_id"] == second.run_id
    first_artifact = database.fetch_one(
        "SELECT path, content_hash FROM artifacts WHERE run_id = ? AND artifact_name = ?",
        (first.run_id, "job_normalized.json"),
    )
    second_artifact = database.fetch_one(
        "SELECT path, content_hash FROM artifacts WHERE run_id = ? AND artifact_name = ?",
        (second.run_id, "job_normalized.json"),
    )
    assert first_artifact["content_hash"] == second_artifact["content_hash"]
    assert first_artifact["path"] != second_artifact["path"]
    database.close()


def test_run_ready_invokes_one_handler_and_all_contract_validators(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    calls: list[str] = []

    def handler(context):
        calls.append(f"handler:{context.node_id}")
        assert context.capabilities.assert_writable(context.staging_dir / "fit_map.json")
        return CellOutput(artifacts={"fit_map.json": b'{"score": 90}'})

    def validator(context, output):
        calls.append(f"validator:{context.validator_command}")
        report = context.paths.reviews_dir / f"{context.validator_command.replace(':', '-')}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={"analyze_fit": handler},
        validators={
            "validate:fit-map": validator,
            "validate:fit-map:quality": validator,
            "validate-provenance": validator,
        },
    )
    plan = executor.plan("app-1", {"cv"})
    executor.mark_validated(plan.run_id, "normalize_job")
    _prepare_bound_analyze_fit(executor, plan.run_id)

    results = executor.run_ready(plan.run_id)

    result = next(item for item in results if item.node_id == "analyze_fit")
    assert result.status == "validated"
    assert calls == [
        "handler:analyze_fit",
        "validator:validate:fit-map",
        "validator:validate:fit-map:quality",
        "validator:validate-provenance",
    ]
    assert executor.node_status(plan.run_id, "analyze_fit") == "validated"
    database.close()


def test_failed_validator_keeps_staging_and_blocks_descendant(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    child_calls: list[str] = []

    def handler(context):
        return CellOutput(artifacts={"fit_map.json": b"candidate"})

    def failed_validator(context, output):
        report = context.paths.reviews_dir / "failed.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.failed(context.validator_command, report, "invalid fit")

    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={
            "analyze_fit": handler,
            "compose_cv": lambda context: child_calls.append(context.node_id),
        },
        validators={"validate:fit-map": failed_validator},
    )
    plan = executor.plan("app-1", {"cv"})
    executor.mark_validated(plan.run_id, "normalize_job")
    _prepare_bound_analyze_fit(executor, plan.run_id)

    results = executor.run_ready(plan.run_id)

    blocked = next(item for item in results if item.node_id == "analyze_fit")
    manifest = json.loads(blocked.manifest_path.read_text(encoding="utf-8"))
    assert blocked.status == "blocked"
    assert manifest["blocker"]["reason"] == "invalid fit"
    assert (blocked.manifest_path.parent / "staging" / "fit_map.json").read_bytes() == b"candidate"
    assert child_calls == []
    assert "compose_cv" not in executor.ready_nodes(plan.run_id)
    database.close()


def test_repair_supersedes_only_declared_descendants(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv", "feras"}).run_id
    for node_id in ("analyze_fit", "compose_cv", "render_cv", "review_cv", "generate_feras"):
        orchestrator.mark_validated(run_id, node_id)
    orchestrator.fail(run_id, "render_cv", "docx_layout")

    repaired = orchestrator.repair(run_id, "render_cv", "docx_layout")

    assert repaired.attempt == 2
    assert repaired.repair_scope == "cv_render_only"
    assert orchestrator.node_status(run_id, "review_cv") == "superseded"
    assert orchestrator.node_status(run_id, "generate_feras") == "validated"
    assert orchestrator.node_status(run_id, "analyze_fit") == "validated"


def test_resume_reconstructs_run_from_database_and_persisted_plan(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    first = CellExecutor(database, applications_root=applications_root)
    plan = first.plan("app-1", {"cv"})
    first.mark_validated(plan.run_id, "normalize_job")

    resumed = CellExecutor(database, applications_root=applications_root).resume(plan.run_id)

    assert resumed.run_id == plan.run_id
    assert resumed.application_id == "app-1"
    assert "analyze_fit" in resumed.ready_nodes
    database.close()


def test_resume_ignores_auxiliary_gate_nodes_not_in_persisted_plan(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    executor = CellExecutor(database, applications_root=tmp_path / "applications")
    plan = executor.plan("app-1", {"cv"})
    database.execute(
        """
        INSERT INTO cell_nodes
            (run_id, node_id, status, requires_json, latest_attempt, created_at, updated_at)
        VALUES (?, ?, 'completed', '[]', 1, ?, ?)
        """,
        (plan.run_id, "cv_review_passed", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )

    resumed = executor.resume(plan.run_id)

    assert "cv_review_passed" not in resumed.statuses
    assert "capture_source" in resumed.ready_nodes
    assert set(resumed.statuses) == {node.node_id for node in plan.nodes}
    database.close()


def test_resource_lock_is_requested_only_by_contract(tmp_path, monkeypatch):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_paths = paths_for("app-1", root=applications_root)
    application_paths.app_dir.mkdir(parents=True)
    application_paths.job_description.write_text("job", encoding="utf-8")
    executor = CellExecutor(database, applications_root=applications_root)
    plan = executor.plan("app-1", {"cv"})
    acquired: list[str] = []
    real_acquire = executor.store.acquire_resource_lock

    def recording_acquire(resource_name, worker_id, **kwargs):
        acquired.append(resource_name)
        return real_acquire(resource_name, worker_id, **kwargs)

    monkeypatch.setattr(executor.store, "acquire_resource_lock", recording_acquire)
    executor.mark_validated(plan.run_id, "review_cv")
    executor.mark_validated(plan.run_id, "render_cv")
    executor.register_handler(
        "deliver_cv", lambda context: CellOutput(artifacts={"receipt.json": b"{}"})
    )
    executor.register_validator(
        "validate-delivery-receipt",
        lambda context, output: ValidatorResult.passed(
            context.validator_command,
            _write_report(context.paths.reviews_dir / "delivery.json"),
        ),
    )

    executor.run_ready(plan.run_id)

    assert acquired == ["delivery:onedrive-cv"]
    database.close()


def test_expired_owned_reservation_is_reclaimed_before_handler_runs(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("app-1", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("job", encoding="utf-8")
    calls: list[int] = []

    def handler(context):
        calls.append(context.attempt)
        return CellOutput(
            artifacts={
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            }
        )

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": handler},
        validators={"context:validate": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})
    first = executor.store.reserve_node(plan.run_id, "normalize_job", executor.worker_id)
    database.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
        (
            (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            plan.run_id,
            "normalize_job",
        ),
    )

    results = executor.run_ready(plan.run_id)

    result = next(item for item in results if item.node_id == "normalize_job")
    assert result.attempt == 2
    assert calls == [2]
    assert database.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
        (plan.run_id, "normalize_job", first["attempt"]),
    ) == {"status": "cancelled"}
    database.close()


def test_executor_does_not_invoke_handler_after_node_lease_expires(tmp_path, monkeypatch):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    calls: list[str] = []
    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={"capture_source": lambda context: calls.append(context.node_id)},
    )
    plan = executor.plan("app-1", {"cv"})
    real_renew = executor.store.renew_node_reservation

    def expire_then_renew(run_id, node_id, attempt, worker_id, **kwargs):
        database.execute(
            "UPDATE cell_nodes SET reservation_expires_at = ? WHERE run_id = ? AND node_id = ?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), run_id, node_id),
        )
        return real_renew(run_id, node_id, attempt, worker_id, **kwargs)

    monkeypatch.setattr(executor.store, "renew_node_reservation", expire_then_renew)

    results = executor.run_ready(plan.run_id)

    result = next(item for item in results if item.node_id == "capture_source")
    assert calls == []
    assert result.status == "cancelled"
    assert result.blocker == "node_lease_expired"
    database.close()


def test_executor_does_not_publish_when_node_lease_expires_during_handler(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"

    def handler(context):
        database.execute(
            "UPDATE cell_nodes SET reservation_expires_at = ? "
            "WHERE run_id = ? AND node_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                context.run_id,
                context.node_id,
            ),
        )
        return CellOutput(artifacts={"job_description.md": "job"})

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"capture_source": handler},
        validators={"validate-job-description": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert result.status == "cancelled"
    assert result.artifact_manifest_paths == ()
    assert list((paths_for("app-1", root=applications_root).artifacts_dir).rglob("manifest.json")) == []
    database.close()


def test_executor_does_not_publish_when_resource_lease_expires_during_handler(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"

    def handler(context):
        database.execute(
            "UPDATE resource_locks SET expires_at = ? WHERE resource_name = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "delivery:onedrive-cv",
            ),
        )
        return CellOutput(artifacts={"cv_delivery_receipt.json": "{}"})

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"deliver_cv": handler},
        validators={"validate-delivery-receipt": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})
    executor.mark_validated(plan.run_id, "review_cv")
    executor.mark_validated(plan.run_id, "render_cv")

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "deliver_cv"
    )

    assert result.status == "blocked"
    assert result.blocker == "resource_lease_expired:delivery:onedrive-cv"
    assert result.artifact_manifest_paths == ()
    database.close()


def test_executor_rolls_back_publication_when_node_lease_expires_during_publish(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "capture_source": lambda context: CellOutput(
                artifacts={"job_description.md": "job"}
            )
        },
        validators={"validate-job-description": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})
    from career.cells.manifests import ManifestStore

    real_publish = ManifestStore.publish_files

    def publish_then_expire(store, node_id, attempt, artifacts, **kwargs):
        published = real_publish(store, node_id, attempt, artifacts, **kwargs)
        database.execute(
            "UPDATE cell_nodes SET reservation_expires_at = ? "
            "WHERE run_id = ? AND node_id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                plan.run_id,
                node_id,
            ),
        )
        return published

    monkeypatch.setattr(ManifestStore, "publish_files", publish_then_expire)

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert result.status == "cancelled"
    assert list(paths_for("app-1", root=applications_root).artifacts_dir.rglob("manifest.json")) == []
    database.close()


def test_resume_reconciles_orphan_publication_after_process_interruption(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    handlers = {
        "capture_source": lambda context: CellOutput(
            artifacts={"job_description.md": "job"}
        )
    }
    validators = {"validate-job-description": _passing_validator}
    interrupted = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=handlers,
        validators=validators,
    )
    plan = interrupted.plan("app-1", {"cv"})

    def interrupt_finish(*args, **kwargs):
        raise KeyboardInterrupt("simulated process loss")

    monkeypatch.setattr(interrupted.store, "finish_attempt", interrupt_finish)
    with pytest.raises(KeyboardInterrupt, match="process loss"):
        interrupted.run_ready(plan.run_id)
    database.execute(
        "UPDATE cell_nodes SET reservation_expires_at = ? "
        "WHERE run_id = ? AND node_id = ?",
        (
            (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            plan.run_id,
            "capture_source",
        ),
    )

    resumed = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=handlers,
        validators=validators,
    )
    result = next(
        item for item in resumed.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert result.status == "validated"
    assert result.attempt == 2
    assert database.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = 1",
        (plan.run_id, "capture_source"),
    ) == {"status": "cancelled"}
    database.close()


def test_finish_atomically_rejects_resource_lease_lost_after_publication(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "deliver_cv": lambda context: CellOutput(
                artifacts={"cv_delivery_receipt.json": "{}"}
            )
        },
        validators={"validate-delivery-receipt": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})
    executor.mark_validated(plan.run_id, "review_cv")
    executor.mark_validated(plan.run_id, "render_cv")
    real_finish = executor.store.finish_attempt

    def expire_resource_then_finish(*args, **kwargs):
        database.execute(
            "UPDATE resource_locks SET expires_at = ? WHERE resource_name = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "delivery:onedrive-cv",
            ),
        )
        return real_finish(*args, **kwargs)

    monkeypatch.setattr(executor.store, "finish_attempt", expire_resource_then_finish)

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "deliver_cv"
    )

    assert result.status == "blocked"
    assert result.blocker == "resource_lease_expired:delivery:onedrive-cv"
    assert list(paths_for("app-1", root=applications_root).artifacts_dir.rglob("manifest.json")) == []
    database.close()


def test_executor_publishes_exact_multi_output_contract(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("app-1", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("job", encoding="utf-8")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "normalize_job": lambda context: CellOutput(
                artifacts={
                    "job_normalized.json": "normalized",
                    "handover_summary.json": "handover",
                    "evidence_index.json": "evidence",
                }
            )
        },
        validators={"context:validate": _passing_validator},
    )
    plan = executor.plan("app-1", {"cv"})

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "normalize_job"
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.status == "validated"
    assert {item["artifact_name"] for item in manifest["outputs"]} == {
        "job_normalized.json",
        "handover_summary.json",
        "evidence_index.json",
    }
    assert len(result.artifact_manifest_paths) == 3
    database.close()


@pytest.mark.parametrize(
    "artifacts",
    [
        {"job_normalized.json": "normalized"},
        {
            "job_normalized.json": "normalized",
            "handover_summary.json": "handover",
            "evidence_index.json": "evidence",
            "surprise.json": "arbitrary",
        },
    ],
)
def test_executor_rejects_missing_or_arbitrary_outputs(tmp_path, artifacts):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("app-1", root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("job", encoding="utf-8")
    validator_calls: list[str] = []

    def validator(context, output):
        validator_calls.append(context.validator_command)
        return _passing_validator(context, output)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={"normalize_job": lambda context: CellOutput(artifacts=artifacts)},
        validators={"context:validate": validator},
    )
    plan = executor.plan("app-1", {"cv"})

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "normalize_job"
    )

    assert result.status == "blocked"
    assert result.blocker.startswith("output_contract_mismatch:")
    assert validator_calls == []
    database.close()


def test_repair_refuses_to_supersede_live_descendant(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    executor = CellExecutor(database, applications_root=tmp_path / "applications")
    plan = executor.plan("app-1", {"cv"})
    for node_id in ("normalize_job", "analyze_fit", "compose_cv", "render_cv"):
        executor.mark_validated(plan.run_id, node_id)
    reservation = executor.store.reserve_node(
        plan.run_id, "review_cv", "review-worker", lease_seconds=300
    )
    executor.fail(plan.run_id, "render_cv", "docx_layout")

    with pytest.raises(RuntimeError, match="active descendant.*review_cv"):
        executor.repair(plan.run_id, "render_cv", "docx_layout")

    assert executor.node_status(plan.run_id, "review_cv") == "reserved"
    assert database.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
        (plan.run_id, "review_cv", reservation["attempt"]),
    ) == {"status": "reserved"}
    assert executor.node_status(plan.run_id, "render_cv") == "blocked"
    database.close()


def test_executor_revalidates_dependency_artifact_before_child_handler(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    child_calls: list[str] = []
    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={
            "analyze_fit": lambda context: CellOutput(
                artifacts={"fit_map.json": '{"score": 90}'}
            ),
            "compose_cv": lambda context: child_calls.append(context.node_id),
        },
        validators={
            "validate:fit-map": _passing_validator,
            "validate:fit-map:quality": _passing_validator,
            "validate-provenance": _passing_validator,
        },
    )
    plan = executor.plan("app-1", {"cv"})
    executor.mark_validated(plan.run_id, "normalize_job")
    _prepare_bound_analyze_fit(executor, plan.run_id)
    fit_result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "analyze_fit"
    )
    artifact_manifest = json.loads(
        fit_result.artifact_manifest_paths[0].read_text(encoding="utf-8")
    )
    Path(artifact_manifest["path"]).write_text("tampered", encoding="utf-8")

    child_result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "compose_cv"
    )

    assert child_calls == []
    assert child_result.status == "blocked"
    assert child_result.blocker.startswith("input_materialization_error:")
    database.close()


def _write_report(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def _passing_validator(context, output):
    report = context.paths.reviews_dir / (
        f"{context.node_id}-{context.attempt}-{context.validator_command.replace(':', '-')}.json"
    )
    return ValidatorResult.passed(context.validator_command, _write_report(report))
