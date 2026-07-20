from __future__ import annotations

import json
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services.database import Database


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
    orchestrator.fail(run_id, "render_cv", "docx_layout")

    repaired = orchestrator.repair(run_id, "render_cv", "docx_layout")

    assert repaired.attempt == 2
    assert orchestrator.node_status(run_id, "analyze_fit") == "validated"


def test_executor_never_runs_child_before_parent(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv"}).run_id

    assert "render_cv" not in orchestrator.ready_nodes(run_id)


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


def _write_report(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path
