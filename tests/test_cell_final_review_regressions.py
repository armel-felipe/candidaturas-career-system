from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from career.cells.executor import CellExecutor
from career.cells.capabilities import recorded_capability_violations
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


def test_executor_cancels_handler_that_reads_another_application_secret(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    secret = app_b.app_dir / "secret.txt"
    secret.write_text("foreign-secret", encoding="utf-8")

    def malicious_handler(_context):
        secret.read_text(encoding="utf-8")
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
    assert secret.read_text(encoding="utf-8") == "foreign-secret"
    assert any(item["target"] == str(secret.resolve()) for item in recorded_capability_violations())
    assert executor.node_status(plan.run_id, "normalize_job") != "validated"
    database.close()


def test_executor_cancels_subprocess_and_child_thread_foreign_writes(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    subprocess_victim = app_b.app_dir / "subprocess-breach.txt"
    thread_victim = app_b.app_dir / "thread-breach.txt"

    def malicious_handler(_context):
        thread = threading.Thread(
            target=lambda: thread_victim.write_text("breach", encoding="utf-8")
        )
        thread.start()
        thread.join()
        subprocess.run(["touch", str(subprocess_victim)], check=False)
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
    assert not subprocess_victim.exists()
    assert not thread_victim.exists()
    recorded_targets = {item["target"] for item in recorded_capability_violations()}
    assert str(subprocess_victim.resolve()) in recorded_targets
    assert str(thread_victim.resolve()) in recorded_targets
    assert executor.node_status(plan.run_id, "normalize_job") != "validated"
    database.close()


def test_executor_rejects_relative_foreign_path_through_approved_subprocess(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    secret = app_b.app_dir / "fit-map-secret.json"
    secret.write_text('{"secret": true}', encoding="utf-8")
    relative_secret = os.path.relpath(secret, Path.cwd())

    def malicious_handler(_context):
        subprocess.run(
            [
                sys.executable,
                "scripts/register_keywords.py",
                "--fit-map",
                relative_secret,
            ],
            check=False,
        )
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
    assert str(secret.resolve()) in result.blocker
    assert secret.is_file()
    database.close()


def test_executor_rejects_approved_script_name_hidden_behind_unapproved_executable(
    tmp_path,
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")

    def malicious_handler(_context):
        subprocess.run(
            ["/usr/bin/printf", "scripts/register_keywords.py"], check=False
        )
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
    assert "subprocess" in result.blocker
    database.close()


def test_executor_rejects_embedded_foreign_registry_option(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    foreign_registry = app_b.app_dir / "breach.json"
    embedded_registry = os.path.relpath(foreign_registry, Path.cwd())

    def malicious_handler(context):
        subprocess.run(
            [
                sys.executable,
                "scripts/register_keywords.py",
                "--fit-map",
                str(context.paths.job_description),
                f"--registry={embedded_registry}",
            ],
            check=False,
        )
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
    assert not foreign_registry.exists()
    assert any(
        item["event"] == "subprocess.Popen"
        for item in recorded_capability_violations()
    )
    database.close()


def test_executor_rejects_foreign_symlink_creation_and_records_target(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.app_dir.mkdir(parents=True)
    app_b.app_dir.mkdir(parents=True)
    app_a.job_description.write_text("Operations leadership " * 30, encoding="utf-8")
    foreign_link = app_b.app_dir / "foreign-link"

    def malicious_handler(context):
        os.symlink(context.paths.job_description, foreign_link)
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
    assert not foreign_link.exists()
    assert any(
        item["event"] == "os.symlink"
        and item["target"] == str(foreign_link.resolve())
        for item in recorded_capability_violations()
    )
    database.close()


def test_canonical_journal_rejects_foreign_restore_target(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    paths = paths_for("app-a", root=root)
    paths.app_dir.mkdir(parents=True)
    foreign = tmp_path / "foreign.txt"
    foreign.write_text("preserve", encoding="utf-8")
    journal = paths.app_dir / "cells" / "run-x" / "capture_source" / "1" / "canonical_commit_journal.json"
    applications_v2.write_json(
        journal,
        {
            "kind": "canonical_commit_journal",
            "application_id": "app-a",
            "run_id": "run-x",
            "node_id": "capture_source",
            "attempt": 1,
            "entries": [{"path": str(foreign), "kind": "missing"}],
        },
    )
    executor = CellExecutor(database, applications_root=root)

    with pytest.raises(ValueError, match="canonical journal"):
        executor._restore_canonical_journal(journal)

    assert foreign.read_text(encoding="utf-8") == "preserve"
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


def test_pending_reprocess_request_overrides_same_source_completion_receipt(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    app = {
        "record_id": 101,
        "page_id": "page-a",
        "status": "Reprocessar",
        "description": "Operations leadership and planning. " * 30,
    }
    paths = applications_v2._ensure_cellular_application(app, applications_root=v2_dir)
    fingerprint = applications_v2.sha256_file(paths.job_description)
    delivery_calls: list[str] = []

    def deliver():
        delivery_calls.append("delivery")
        return {"status": "delivered", "artifact_sha256": f"sha-{len(delivery_calls)}"}

    first = applications_v2._complete_cellular_application_once(
        app,
        paths=paths,
        run_id="run-old",
        job_fingerprint=fingerprint,
        delivery=deliver,
        update_tracker=lambda _status: None,
        success_status="Aplicação andamento",
    )
    applications_v2.write_json(
        applications_v2._reprocess_request_path(paths),
        {
            "kind": "cellular_reprocess_request",
            "application_id": paths.application_id,
            "request_fingerprint": "request-2",
            "status": "pending",
            "run_id": "",
        },
    )

    second = applications_v2._complete_cellular_application_once(
        app,
        paths=paths,
        run_id="run-new",
        job_fingerprint=fingerprint,
        delivery=deliver,
        update_tracker=lambda _status: None,
        success_status="Aplicação andamento",
    )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert second["run_id"] == "run-new"
    assert delivery_calls == ["delivery", "delivery"]


def test_explicit_new_run_is_not_short_circuited_by_prior_completion_receipt(
    tmp_path, monkeypatch
):
    v2_dir = tmp_path / ".career-state" / "applications_v2"
    monkeypatch.setattr(applications_v2, "V2_DIR", v2_dir)
    database_path = v2_dir.parent / "career.db"
    database = Database(database_path)
    database.init_schema()
    authority_id = database.control_db_identity()
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", authority_id)
    app = {
        "record_id": 101,
        "page_id": None,
        "status": "Fila Agente",
        "company": "Example Co.",
        "role": "Operations Manager",
        "description": "Operations leadership and planning. " * 30,
    }
    paths = applications_v2._ensure_cellular_application(
        app, applications_root=v2_dir
    )
    planner = CellExecutor(
        database,
        applications_root=v2_dir,
        workspace_control_db_id=authority_id,
        require_authoritative_workspace=True,
    )
    old_run = planner.plan(paths.application_id, {"cv"}).run_id
    fingerprint = applications_v2.sha256_file(paths.job_description)
    applications_v2._complete_cellular_application_once(
        app,
        paths=paths,
        run_id=old_run,
        job_fingerprint=fingerprint,
        delivery=lambda: {"status": "delivered", "artifact_sha256": "old-sha"},
        update_tracker=lambda _status: None,
        success_status="Aplicação andamento",
    )
    planner.release_workspace_lease()

    new_run = planner.plan(paths.application_id, {"cv"}).run_id
    planner.release_workspace_lease()
    result = applications_v2._process_cellular_application(
        {**app, "application_id": paths.application_id, "_cellular_run_id": new_run},
        options=applications_v2.HeartbeatV2Options(
            max_per_run=1,
            run_agent=True,
            dry_run=False,
            cellular=True,
            workspace_owner="test-explicit-new-run",
            control_db_id=authority_id,
            release_workspace_lease=True,
        ),
        config=applications_v2.DEFAULT_CONFIG,
        database_path=database_path,
    )

    assert result
    assert result[0]["run_id"] == new_run
    assert result[0]["status"] != "already_completed"
    assert database.fetch_one(
        "SELECT status FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        (new_run, "normalize_job"),
    ) == {"status": "validated"}
    database.close()


def test_failed_canonical_source_commit_has_no_validated_db_or_artifacts_and_retries(
    tmp_path, monkeypatch
):
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
        validators={"validate-job-description": _passing_validator},
    )
    plan = executor.plan("app-a", {"cv"})
    original_commit = executor._commit_captured_source
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated canonical persistence failure")
        return original_commit(*args, **kwargs)

    monkeypatch.setattr(executor, "_commit_captured_source", fail_once)
    first = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert first.status == "blocked", first.blocker
    assert "canonical" in first.blocker or "publication_commit_error" in first.blocker
    assert executor.node_status(plan.run_id, "capture_source") == "blocked"
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM artifacts WHERE run_id = ? AND node_id = ?",
        (plan.run_id, "capture_source"),
    ) == {"count": 0}
    assert list(paths.artifacts_dir.rglob("manifest.json")) == []
    assert not paths.job_description.exists()
    assert not paths.source_metadata.exists()

    executor.repair(plan.run_id, "capture_source", "retry canonical persistence")
    second = next(
        item for item in executor.run_ready(plan.run_id) if item.node_id == "capture_source"
    )

    assert second.status == "validated"
    assert paths.job_description.is_file()
    assert paths.source_metadata.is_file()
    database.close()


def test_canonical_commit_journal_recovers_process_death_before_db_commit(
    tmp_path, monkeypatch
):
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
        validators={"validate-job-description": _passing_validator},
    )
    plan = executor.plan("app-a", {"cv"})
    original_finish = executor.store.finish_attempt
    calls = 0

    def die_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SystemExit("simulated death after canonical persistence")
        return original_finish(*args, **kwargs)

    monkeypatch.setattr(executor.store, "finish_attempt", die_once)
    with pytest.raises(SystemExit, match="simulated death"):
        executor.run_ready(plan.run_id)

    assert paths.job_description.is_file()
    assert database.fetch_one(
        "SELECT status FROM cell_attempts WHERE run_id = ? AND node_id = ? AND attempt = 1",
        (plan.run_id, "capture_source"),
    )["status"] != "validated"

    results = executor.run_ready(plan.run_id)
    retried = next(item for item in results if item.node_id == "capture_source")

    assert retried.status == "validated", retried.blocker
    assert not list(paths.cells_dir.rglob("canonical_commit_journal.json"))
    assert database.fetch_one(
        "SELECT COUNT(*) AS count FROM artifacts WHERE run_id = ? AND node_id = ?",
        (plan.run_id, "capture_source"),
    ) == {"count": 1}
    database.close()


def test_canonical_journal_tampering_is_quarantined_without_deleting_source(
    tmp_path,
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    paths = paths_for("app-a", root=root)
    paths.app_dir.mkdir(parents=True)
    executor = CellExecutor(database, applications_root=root)
    plan = executor.plan("app-a", {"cv"})
    _loaded_plan, paths = executor._load_run(plan.run_id)
    paths.job_description.write_text("authoritative old source", encoding="utf-8")
    paths.source_metadata.write_text('{"source": "old"}', encoding="utf-8")
    journal = executor._begin_canonical_journal(
        paths, plan.run_id, "capture_source", 1
    )
    paths.job_description.write_text("new source must be preserved", encoding="utf-8")

    payload = json.loads(journal.read_text(encoding="utf-8"))
    source_entry = next(
        item
        for item in payload["entries"]
        if item["path"] == str(paths.job_description.resolve())
    )
    source_entry.clear()
    source_entry.update(
        {"path": str(paths.job_description.resolve()), "kind": "missing"}
    )
    journal.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="journal.*integrity|snapshot.*projection"):
        executor._restore_canonical_journal(journal)

    assert paths.job_description.read_text(encoding="utf-8") == "new source must be preserved"
    assert not journal.exists()
    assert list(journal.parent.glob("canonical_commit_journal.quarantined.*.json"))
    database.close()


def test_finalize_is_idempotent_and_preserves_completed_manifest(tmp_path, monkeypatch):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    from career.cells.manifests import RunCompletion
    from career.utils import write_json

    executor = CellExecutor(database, applications_root=root)
    plan = executor.plan("app-a", {"cv"})

    def finish_run(store, run_id, **_kwargs):
        path = paths_for("app-a", root=root).app_dir / "runs" / run_id / "run_completion_manifest.json"
        manifest = {
            "kind": "run_completion_manifest",
            "application_id": "app-a",
            "run_id": run_id,
            "status": "completed",
            "validated_artifacts": [],
            "blocked_nodes": [],
        }
        write_json(path, manifest)
        return RunCompletion(path=path, manifest=manifest)

    monkeypatch.setattr(ManifestStore, "finish_run", finish_run)

    first = executor.finalize(plan.run_id)
    original = first.path.read_bytes()
    second = executor.finalize(plan.run_id)

    assert second.manifest["status"] == "completed"
    assert second.path == first.path
    assert second.path.read_bytes() == original
    assert database.fetch_one(
        "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
    ) == {"status": "completed"}
    second.path.write_text("{truncated", encoding="utf-8")
    recovered = executor.finalize(plan.run_id)
    assert recovered.manifest["status"] == "completed"
    assert recovered.path.is_file()
    database.close()


def test_finalize_rebuilds_completed_manifest_with_foreign_artifact_path(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    paths = paths_for("app-a", root=root)
    foreign = paths_for("app-b", root=root)
    paths.app_dir.mkdir(parents=True)
    foreign.app_dir.mkdir(parents=True)
    foreign_artifact = foreign.app_dir / "foreign.docx"
    foreign_artifact.write_bytes(b"foreign")
    executor = CellExecutor(database, applications_root=root)
    plan = executor.plan("app-a", {"cv"})
    for node in plan.nodes:
        executor.fail(plan.run_id, node.node_id, "terminal fixture")
    database.execute(
        "UPDATE application_runs SET status = 'completed' WHERE run_id = ?",
        (plan.run_id,),
    )
    completion = paths.app_dir / "runs" / plan.run_id / "run_completion_manifest.json"
    completion.parent.mkdir(parents=True, exist_ok=True)
    completion.write_text(
        json.dumps(
            {
                "kind": "run_completion_manifest",
                "application_id": "app-a",
                "run_id": plan.run_id,
                "status": "completed",
                "validated_artifacts": [
                    {
                        "application_id": "app-b",
                        "run_id": plan.run_id,
                        "node_id": "render_cv_pt",
                        "artifact_name": "cv.docx",
                        "path": str(foreign_artifact),
                    }
                ],
                "blocked_nodes": [],
                "completed_at": "2026-07-21T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    recovered = executor.finalize(plan.run_id)

    assert recovered.manifest["status"] == "blocked"
    assert all(
        item.get("application_id") == "app-a"
        for item in recovered.manifest["validated_artifacts"]
    )
    assert str(foreign_artifact) not in recovered.path.read_text(encoding="utf-8")
    assert database.fetch_one(
        "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
    ) == {"status": "blocked"}
    database.close()


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
