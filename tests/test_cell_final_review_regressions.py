from __future__ import annotations

import json
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career.cells.handlers import (
    CellOutput,
    ValidatorResult,
    production_handler_registry,
)
from career.cells.manifests import ManifestStore
from career.services import applications_v2
from career.services.application_context import paths_for
from career.services.database import Database


def _passing_validator(context, _output):
    report = context.paths.reviews_dir / f"{context.validator_command}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{}", encoding="utf-8")
    return ValidatorResult.passed(context.validator_command, report)


def _failed_validator(context, _output):
    report = context.paths.reviews_dir / f"{context.validator_command}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{}", encoding="utf-8")
    return ValidatorResult.failed(context.validator_command, report, "rejected")


def _validator_proofs(paths, node_id: str):
    from career.cells.contracts import CELL_CONTRACTS

    proofs = []
    for index, command in enumerate(CELL_CONTRACTS[node_id].validators):
        report = paths.reviews_dir / f"proof-{index}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        proofs.append(
            {"command": command, "result": "passed", "report_path": report}
        )
    return proofs


def test_executor_rolls_back_handler_write_into_another_application(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    victim = app_b.app_dir / "foreign-write.json"

    def malicious_handler(_context):
        victim.write_text('{"breach": true}', encoding="utf-8")
        return CellOutput(
            artifacts={
                "job_normalized.json": "{}",
                "handover_summary.json": "{}",
                "evidence_index.json": "{}",
            }
        )

    executor = CellExecutor(
        database,
        applications_root=root,
        handlers={"normalize_job": malicious_handler},
        validators={"context:validate": _passing_validator},
    )
    plan = executor.plan("app-a", {"cv"})

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "normalize_job"
    )

    assert result.status == "cancelled"
    assert "capability" in result.blocker
    assert not victim.exists()
    assert executor.node_status(plan.run_id, "normalize_job") != "validated"
    database.close()


def test_parallel_verification_blocks_reported_application_tree_cross_write(
    tmp_path, monkeypatch
):
    fixture = tmp_path / "fixture"
    app_a = fixture / "applications" / "app-a"
    app_b = fixture / "applications" / "app-b"
    base = {
        "status": "validated",
        "job_fingerprint": "a" * 64,
        "manifest_path": str(app_a / "cells" / "a" / "manifest.json"),
        "artifact_paths": [],
        "external_lock_entered_at": 1,
        "external_lock_released_at": 2,
        "external_lock_contention_count": 1,
        "external_lock_node_id": "sync_notion_initial",
        "external_resource_declared_by_contract": True,
        "unexpected_writes": [],
    }
    monkeypatch.setattr(
        applications_v2,
        "run_parallel_fixture_workers",
        lambda _fixture: [
            {
                **base,
                "application_id": "app-a",
                "capability_violations": [str(app_b / "foreign.json")],
            },
            {
                **base,
                "application_id": "app-b",
                "job_fingerprint": "b" * 64,
                "manifest_path": str(app_b / "cells" / "b" / "manifest.json"),
                "external_lock_entered_at": 2,
                "external_lock_released_at": 3,
                "external_lock_contention_count": 0,
                "capability_violations": [],
            },
        ],
    )

    report = applications_v2.parallel_verification_report(fixture)

    assert report["status"] == "blocked"
    assert str(app_b / "foreign.json") in report["crossed_paths"]


def test_multi_output_publication_recovers_after_crash_without_visible_orphan(
    tmp_path, monkeypatch
):
    paths = paths_for("app-a", root=tmp_path / "applications")
    store = ManifestStore(paths)
    proofs = _validator_proofs(paths, "normalize_job")
    artifacts = {
        "job_normalized.json": b'{"job": 1}',
        "handover_summary.json": b'{"handover": 1}',
        "evidence_index.json": b'{"evidence": 1}',
    }
    real_replace = __import__("os").replace
    publication_moves = 0

    def crash_after_first_publication(source, target):
        nonlocal publication_moves
        real_replace(source, target)
        if Path(target).name in artifacts:
            publication_moves += 1
            if publication_moves == 1:
                raise SystemExit("simulated process death")

    monkeypatch.setattr(
        "career.cells.manifests.os.replace", crash_after_first_publication
    )
    with pytest.raises(SystemExit, match="simulated process death"):
        store.publish_files(
            "normalize_job", 1, artifacts, validators=proofs
        )

    visible = [
        path
        for path in paths.artifacts_dir.rglob("*")
        if path.is_file() and path.name in artifacts
    ]
    assert visible == []

    monkeypatch.setattr("career.cells.manifests.os.replace", real_replace)
    published = ManifestStore(paths).publish_files(
        "normalize_job", 1, artifacts, validators=proofs
    )
    assert {item.path.name for item in published} == set(artifacts)


def test_failed_production_source_capture_leaves_no_canonical_source_state(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    paths = paths_for("app-a", root=root)
    paths.app_dir.mkdir(parents=True)
    (paths.app_dir / "source_input.md").write_text(
        "Lead operations, planning, indicators, governance, and data analysis. " * 30,
        encoding="utf-8",
    )
    paths.identity.write_text(
        json.dumps(
            {
                "kind": "application_identity",
                "application_id": "app-a",
                "source_type": "test",
                "source_id": "source-a",
            }
        ),
        encoding="utf-8",
    )
    executor = CellExecutor(
        database,
        applications_root=root,
        handlers={"capture_source": production_handler_registry()["capture_source"]},
        validators={"validate-job-description": _failed_validator},
    )
    plan = executor.plan("app-a", {"cv"})

    result = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert result.status == "blocked"
    assert not paths.job_description.exists()
    assert not paths.source_metadata.exists()
    database.close()


def test_changed_source_cancels_active_run_before_replanning(tmp_path, monkeypatch):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    database_path = v2_dir.parent / "career.db"
    database = Database(database_path)
    database.init_schema()
    executor = CellExecutor(database, applications_root=v2_dir)
    first_application = {
        "record_id": 101,
        "page_id": "page-a",
        "status": "Fila Agente",
        "description": "Original operations description. " * 30,
    }
    paths = applications_v2._ensure_cellular_application(
        first_application, applications_root=v2_dir
    )
    old_run = executor.plan("101", {"cv"}).run_id
    executor.mark_validated(old_run, "normalize_job")
    old_fingerprint = applications_v2.sha256_file(paths.job_description)

    changed = {
        **first_application,
        "description": "Changed supply-chain and capacity description. " * 30,
    }
    applications_v2._ensure_cellular_application(changed, applications_root=v2_dir)
    new_run = applications_v2._select_or_plan_cellular_run(
        changed, paths=paths, executor=executor, config=applications_v2.DEFAULT_CONFIG
    )

    assert new_run != old_run
    assert database.fetch_one(
        "SELECT status FROM application_runs WHERE run_id = ?", (old_run,)
    ) == {"status": "cancelled"}
    assert executor.node_status(new_run, "normalize_job") != "validated"
    assert applications_v2.sha256_file(paths.job_description) != old_fingerprint
    database.close()


def test_completed_source_has_durable_cross_run_receipt_and_is_not_redelivered(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    app = {
        "record_id": 101,
        "page_id": "page-a",
        "status": "Fila Agente",
        "description": "Operations leadership and planning. " * 30,
    }
    paths = applications_v2._ensure_cellular_application(app, applications_root=v2_dir)
    fingerprint = applications_v2.sha256_file(paths.job_description)
    delivery_calls: list[str] = []
    tracker_calls: list[str] = []

    def deliver_once():
        delivery_calls.append("delivery")
        return {"status": "delivered", "artifact_sha256": "cv-sha"}

    first = applications_v2._complete_cellular_application_once(
        app,
        paths=paths,
        run_id="run-1",
        job_fingerprint=fingerprint,
        delivery=deliver_once,
        update_tracker=lambda status: tracker_calls.append(status),
        success_status="Aplicação andamento",
    )
    second = applications_v2._complete_cellular_application_once(
        app,
        paths=paths,
        run_id="run-2",
        job_fingerprint=fingerprint,
        delivery=deliver_once,
        update_tracker=lambda status: tracker_calls.append(status),
        success_status="Aplicação andamento",
    )

    assert first["status"] == "completed"
    assert second["status"] == "already_completed"
    assert delivery_calls == ["delivery"]
    assert tracker_calls == ["Aplicação andamento"]
    receipt = json.loads(
        (paths.app_dir / "cellular_completion_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["job_fingerprint"] == fingerprint
    assert receipt["delivery"]["artifact_sha256"] == "cv-sha"


def test_completed_manifest_recovers_cross_run_receipt_before_new_plan(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    app = {
        "record_id": 101,
        "page_id": "page-a",
        "status": "Fila Agente",
        "description": "Operations leadership and planning. " * 30,
    }
    paths = applications_v2._ensure_cellular_application(app, applications_root=v2_dir)
    fingerprint = applications_v2.sha256_file(paths.job_description)
    run_id = "run-completed"
    handover = paths.app_dir / "artifacts" / run_id / "handover.json"
    delivery = paths.app_dir / "artifacts" / run_id / "delivery.json"
    handover.parent.mkdir(parents=True)
    handover.write_text(json.dumps({"job_fingerprint": fingerprint}), encoding="utf-8")
    delivery.write_text(
        json.dumps(
            {
                "operation": "cv_delivery",
                "delivery_id": "delivery-1",
                "response_hash": "response-sha",
            }
        ),
        encoding="utf-8",
    )
    completion = paths.app_dir / "runs" / run_id / "run_completion_manifest.json"
    completion.parent.mkdir(parents=True)
    completion.write_text(
        json.dumps(
            {
                "kind": "run_completion_manifest",
                "application_id": "101",
                "run_id": run_id,
                "status": "completed",
                "validated_artifacts": [
                    {
                        "node_id": "normalize_job",
                        "artifact_name": "handover_summary.json",
                        "path": str(handover),
                    },
                    {
                        "node_id": "deliver_cv",
                        "artifact_name": "cv_delivery_receipt.json",
                        "path": str(delivery),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    tracker_calls: list[str] = []

    recovered = applications_v2._recover_completed_cellular_receipt(
        app,
        paths=paths,
        job_fingerprint=fingerprint,
        success_status="Aplicação andamento",
        update_tracker=lambda status: tracker_calls.append(status),
    )

    assert recovered["status"] == "completed"
    assert recovered["run_id"] == run_id
    assert recovered["delivery"]["delivery_id"] == "delivery-1"
    assert tracker_calls == ["Aplicação andamento"]
