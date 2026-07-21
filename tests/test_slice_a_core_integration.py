from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career import cli
from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import write_json


def _bind_analyze_fit(executor: CellExecutor, run_id: str) -> None:
    plan, paths = executor._load_run(run_id)
    node = executor.database.fetch_one(
        "SELECT latest_attempt, status FROM cell_nodes WHERE run_id = ? AND node_id = ?",
        (run_id, "analyze_fit"),
    )
    assert node is not None
    attempt = int(node["latest_attempt"])
    if node["status"] not in {"reserved", "repairing"} or attempt == 0:
        attempt += 1
    paths.fit_map_draft.write_text('{"cargo":"test"}', encoding="utf-8")
    job_hash = (
        hashlib.sha256(paths.job_description.read_bytes()).hexdigest()
        if paths.job_description.is_file()
        else ""
    )
    write_json(
        paths.app_dir / "fit_map.draft.binding.json",
        {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": plan.application_id,
            "run_id": run_id,
            "node_id": "analyze_fit",
            "attempt": attempt,
            "job_fingerprint": job_hash,
            "draft_sha256": hashlib.sha256(
                paths.fit_map_draft.read_bytes()
            ).hexdigest(),
            "manifest_path": str(
                (
                    paths.cells_dir
                    / "analyze_fit"
                    / str(attempt)
                    / "manifest.json"
                ).resolve()
            ),
        },
    )


def test_two_application_runs_share_sqlite_but_publish_and_inspect_only_scoped_validated_artifacts(
    tmp_path, monkeypatch, capsys
):
    """Slice A gate: two independent applications complete in one SQLite workspace."""
    database = Database(tmp_path / "career.db")
    database.init_schema()
    monkeypatch.setenv("CAREER_CONTROL_DB_ID", database.control_db_identity())
    applications_root = tmp_path / "applications"
    application_ids = ("slice-a-app-a", "slice-a-app-b")
    application_paths = {
        application_id: paths_for(application_id, root=applications_root)
        for application_id in application_ids
    }
    payload_markers = {
        application_id: f"payload-must-stay-out-of-sqlite:{application_id}"
        for application_id in application_ids
    }

    def handler(context):
        marker = payload_markers[context.application_id]
        artifacts = {
            "normalize_job": {
                "job_normalized.json": marker,
                "handover_summary.json": marker,
                "evidence_index.json": marker,
            },
            "analyze_fit": {"fit_map.json": marker},
            "sync_notion_initial": {"notion_initial_receipt.json": marker},
        }
        return CellOutput(
            artifacts={
                name: f"{content}:attempt-{context.attempt}"
                for name, content in artifacts[context.node_id].items()
            },
            metadata={"opaque_handler_payload": marker},
        )

    def validator(context, _output):
        report = context.paths.reviews_dir / (
            f"{context.node_id}-{context.attempt}-{context.validator_command}.json"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(
                {
                    "application_id": context.application_id,
                    "run_id": context.run_id,
                    "validator": context.validator_command,
                    "result": "passed",
                }
            ),
            encoding="utf-8",
        )
        return ValidatorResult.passed(context.validator_command, report)

    validators = {
        "context:validate": validator,
        "validate:fit-map": validator,
        "validate:fit-map:quality": validator,
        "validate-provenance": validator,
        "validate-notion-receipt": validator,
    }
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "normalize_job": handler,
            "analyze_fit": handler,
            "sync_notion_initial": handler,
        },
        validators=validators,
    )

    try:
        plans = {}
        completions = {}
        results = {application_id: [] for application_id in application_ids}
        for application_id, paths in application_paths.items():
            paths.app_dir.mkdir(parents=True)
            paths.job_description.write_text(
                f"Job description for {application_id}", encoding="utf-8"
            )
            plans[application_id] = executor.plan(application_id, {"notion"})
            _bind_analyze_fit(executor, plans[application_id].run_id)

        while any(executor.ready_nodes(plan.run_id) for plan in plans.values()):
            for application_id, plan in plans.items():
                results[application_id].extend(executor.run_ready(plan.run_id))

        monkeypatch.setattr(cli, "Database", lambda: database)
        monkeypatch.setattr(
            cli,
            "CellExecutor",
            lambda db, **kwargs: CellExecutor(
                db, applications_root=applications_root, **kwargs
            ),
        )
        for application_id, plan in plans.items():
            assert executor.is_terminal(plan.run_id)

            persisted_before_finalize = database.fetch_one(
                "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
            )["status"]
            assert cli.main(
                [
                    "applications",
                    "inspect-run",
                    "--application-id",
                    application_id,
                    "--run-id",
                    plan.run_id,
                ]
            ) == 0
            pre_finalize_inspection = json.loads(capsys.readouterr().out)
            assert pre_finalize_inspection["status"] == persisted_before_finalize
            assert pre_finalize_inspection["status"] != "completed"

            completion = executor.finalize(plan.run_id)
            completions[application_id] = completion
            paths = application_paths[application_id]

            assert completion.manifest["status"] == "completed"
            assert completion.manifest["validated_artifacts"]
            assert database.fetch_one(
                "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
            ) == {"status": "completed"}

            published_paths = []
            for artifact in completion.manifest["validated_artifacts"]:
                assert artifact["status"] == "validated"
                assert artifact["validators"]
                published_paths.extend((Path(artifact["path"]), Path(artifact["manifest_path"])))
            published_paths.extend(
                result.manifest_path for result in results[application_id]
            )
            published_paths.append(completion.path)

            assert published_paths
            assert all(path.is_file() for path in published_paths)
            assert all(path.resolve().is_relative_to(paths.app_dir.resolve()) for path in published_paths)
            other_paths = application_paths[
                next(candidate for candidate in application_ids if candidate != application_id)
            ]
            assert all(
                not path.resolve().is_relative_to(other_paths.app_dir.resolve())
                for path in published_paths
            )

        database_rows = []
        for table in (
            "application_runs",
            "cell_nodes",
            "cell_attempts",
            "artifacts",
            "artifact_dependencies",
            "resource_locks",
        ):
            database_rows.extend(database.fetch_all(f"SELECT * FROM {table}"))
        serialized_database_rows = json.dumps(database_rows, sort_keys=True)
        assert all(marker not in serialized_database_rows for marker in payload_markers.values())

        for application_id, plan in plans.items():
            assert cli.main(
                [
                    "applications",
                    "inspect-run",
                    "--application-id",
                    application_id,
                    "--run-id",
                    plan.run_id,
                ]
            ) == 0
            inspection = json.loads(capsys.readouterr().out)
            expected_artifact_paths = {
                str(artifact["path"])
                for artifact in completions[application_id].manifest["validated_artifacts"]
            }
            persisted_status = database.fetch_one(
                "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
            )["status"]
            assert inspection["status"] == persisted_status == "completed"
            assert set(inspection["artifact_paths"]) == expected_artifact_paths
            assert inspection["next_action"] == (
                "career applications inspect-run "
                f"--application-id {application_id} --run-id {plan.run_id}"
            )

        revised_application_id = application_ids[0]
        revised_plan = plans[revised_application_id]
        original_fit_map = next(
            artifact
            for artifact in completions[revised_application_id].manifest[
                "validated_artifacts"
            ]
            if artifact["artifact_name"] == "fit_map.json"
        )
        original_path = Path(original_fit_map["path"])
        original_manifest_path = Path(original_fit_map["manifest_path"])
        original_bytes = original_path.read_bytes()
        original_manifest_bytes = original_manifest_path.read_bytes()

        executor.repair(revised_plan.run_id, "analyze_fit", "revised evidence")
        _bind_analyze_fit(executor, revised_plan.run_id)
        executor.run_ready(revised_plan.run_id)
        while executor.ready_nodes(revised_plan.run_id):
            executor.run_ready(revised_plan.run_id)
        revised_completion = executor.finalize(revised_plan.run_id)
        revised_fit_map = next(
            artifact
            for artifact in revised_completion.manifest["validated_artifacts"]
            if artifact["artifact_name"] == "fit_map.json"
        )

        assert revised_fit_map["revision"] != original_fit_map["revision"]
        assert revised_fit_map["path"] != original_fit_map["path"]
        assert Path(revised_fit_map["path"]).read_bytes() != original_bytes
        assert original_path.read_bytes() == original_bytes
        assert original_manifest_path.read_bytes() == original_manifest_bytes
    finally:
        database.close()


def test_finalization_rejects_file_only_state_and_blocks_failed_terminal_run(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_id = "slice-a-finalization-negative"
    paths = paths_for(application_id, root=applications_root)
    paths.app_dir.mkdir(parents=True)
    paths.job_description.write_text("Job description", encoding="utf-8")
    fail_notion_validation = True

    def handler(context):
        artifacts = {
            "normalize_job": {
                "job_normalized.json": "normalized",
                "handover_summary.json": "handover",
                "evidence_index.json": "evidence",
            },
            "analyze_fit": {"fit_map.json": "fit"},
            "sync_notion_initial": {"notion_initial_receipt.json": "receipt"},
        }
        return CellOutput(artifacts=artifacts[context.node_id])

    def validator(context, _output):
        report = context.paths.reviews_dir / (
            f"{context.node_id}-{context.attempt}-{context.validator_command}.json"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        if context.node_id == "sync_notion_initial" and fail_notion_validation:
            return ValidatorResult.failed(
                context.validator_command, report, "notion receipt failed validation"
            )
        return ValidatorResult.passed(context.validator_command, report)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers={
            "normalize_job": handler,
            "analyze_fit": handler,
            "sync_notion_initial": handler,
        },
        validators={
            "context:validate": validator,
            "validate:fit-map": validator,
            "validate:fit-map:quality": validator,
            "validate-provenance": validator,
            "validate-notion-receipt": validator,
        },
    )

    try:
        plan = executor.plan(application_id, {"notion"})
        _bind_analyze_fit(executor, plan.run_id)
        fake_artifact = paths.artifacts_dir / "fit_map.json" / "fake" / "fit_map.json"
        fake_artifact.parent.mkdir(parents=True)
        fake_artifact.write_text("exists but is not validated", encoding="utf-8")

        with pytest.raises(ValueError, match="persisted attempt"):
            executor.finalize(plan.run_id)
        assert database.fetch_one(
            "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
        ) == {"status": "planned"}

        while executor.ready_nodes(plan.run_id):
            executor.run_ready(plan.run_id)
        assert executor.is_terminal(plan.run_id)
        completion = executor.finalize(plan.run_id)

        assert completion.manifest["status"] == "blocked"
        assert completion.manifest["blocked_nodes"] == [
            {
                "node_id": "sync_notion_initial",
                "attempt": 1,
                "status": "blocked",
                "manifest_path": str(
                    paths.cells_dir
                    / plan.run_id
                    / "sync_notion_initial"
                    / "1"
                    / "manifest.json"
                ),
            }
        ]
        assert database.fetch_one(
            "SELECT status FROM application_runs WHERE run_id = ?", (plan.run_id,)
        ) == {"status": "blocked"}
        assert str(fake_artifact) not in json.dumps(completion.manifest, sort_keys=True)
    finally:
        database.close()


def test_independent_reservations_proceed_while_only_notion_write_serializes(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    application_ids = ("slice-a-lock-app-a", "slice-a-lock-app-b")
    executed: list[tuple[str, str]] = []

    def handler(context):
        executed.append((context.application_id, context.node_id))
        artifacts = {
            "normalize_job": {
                "job_normalized.json": context.application_id,
                "handover_summary.json": context.application_id,
                "evidence_index.json": context.application_id,
            },
            "analyze_fit": {"fit_map.json": context.application_id},
            "sync_notion_initial": {
                "notion_initial_receipt.json": context.application_id
            },
        }
        return CellOutput(artifacts=artifacts[context.node_id])

    def validator(context, _output):
        report = context.paths.reviews_dir / (
            f"{context.node_id}-{context.attempt}-{context.validator_command}.json"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        return ValidatorResult.passed(context.validator_command, report)

    handlers = {
        "normalize_job": handler,
        "analyze_fit": handler,
        "sync_notion_initial": handler,
    }
    validators = {
        "context:validate": validator,
        "validate:fit-map": validator,
        "validate:fit-map:quality": validator,
        "validate-provenance": validator,
        "validate-notion-receipt": validator,
    }
    executors = {
        application_id: CellExecutor(
            database,
            applications_root=applications_root,
            handlers=handlers,
            validators=validators,
            worker_id=f"worker-{application_id}",
        )
        for application_id in application_ids
    }

    try:
        plans = {}
        for application_id in application_ids:
            paths = paths_for(application_id, root=applications_root)
            paths.app_dir.mkdir(parents=True)
            paths.job_description.write_text(application_id, encoding="utf-8")
            plans[application_id] = executors[application_id].plan(
                application_id, {"notion"}
            )
            _bind_analyze_fit(
                executors[application_id], plans[application_id].run_id
            )

        reservations = {
            application_id: executors[application_id].store.reserve_node(
                plans[application_id].run_id,
                "normalize_job",
                executors[application_id].worker_id,
            )
            for application_id in application_ids
        }
        assert all(
            reservation["status"] == "reserved"
            for reservation in reservations.values()
        )

        notion_lock = executors[application_ids[0]].store.acquire_resource_lock(
            "notion-write", "external-notion-writer"
        )
        assert notion_lock["acquired"] is True

        for application_id in application_ids:
            non_resource = executors[application_id].run_ready(
                plans[application_id].run_id
            )
            assert [result.node_id for result in non_resource] == [
                "normalize_job",
                "analyze_fit",
            ]
            assert all(result.status == "validated" for result in non_resource)

        assert set(executed) == {
            (application_id, node_id)
            for application_id in application_ids
            for node_id in ("normalize_job", "analyze_fit")
        }

        for application_id in application_ids:
            deferred = executors[application_id].run_ready(
                plans[application_id].run_id
            )
            assert len(deferred) == 1
            assert deferred[0].node_id == "sync_notion_initial"
            assert deferred[0].status == "deferred"
            assert deferred[0].blocker == "resource_busy:notion-write"
            assert executors[application_id].node_status(
                plans[application_id].run_id, "sync_notion_initial"
            ) == "planned"

        assert executors[application_ids[0]].store.release_resource_lock(
            "notion-write",
            "external-notion-writer",
            lease_id=notion_lock["lease_id"],
        )["released"] is True

        for application_id in application_ids:
            completed = executors[application_id].run_ready(
                plans[application_id].run_id
            )
            assert len(completed) == 1
            assert completed[0].node_id == "sync_notion_initial"
            assert completed[0].status == "validated"
            assert executor_terminal_statuses(
                database, plans[application_id].run_id
            ) == {
                "analyze_fit": "validated",
                "normalize_job": "validated",
                "sync_notion_initial": "validated",
            }
    finally:
        database.close()


def executor_terminal_statuses(database, run_id):
    return {
        row["node_id"]: row["status"]
        for row in database.fetch_all(
            "SELECT node_id, status FROM cell_nodes WHERE run_id = ? ORDER BY node_id",
            (run_id,),
        )
    }
