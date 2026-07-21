from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career import cli
from career.cells.executor import CellExecutor
from career.cells.handlers import CellOutput, ValidatorResult
from career.services.application_context import paths_for
from career.services.database import Database


def test_two_application_runs_share_sqlite_but_publish_and_inspect_only_scoped_validated_artifacts(
    tmp_path, monkeypatch, capsys
):
    """Slice A gate: two independent applications complete in one SQLite workspace."""
    database = Database(tmp_path / "career.db")
    database.init_schema()
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
            artifacts=artifacts[context.node_id],
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

        while any(executor.ready_nodes(plan.run_id) for plan in plans.values()):
            for application_id, plan in plans.items():
                results[application_id].extend(executor.run_ready(plan.run_id))

        for application_id, plan in plans.items():
            assert executor.is_terminal(plan.run_id)
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

        monkeypatch.setattr(cli, "Database", lambda: database)
        monkeypatch.setattr(
            cli,
            "CellExecutor",
            lambda db, **kwargs: CellExecutor(
                db, applications_root=applications_root, **kwargs
            ),
        )
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
            assert inspection["status"] == "completed"
            assert set(inspection["artifact_paths"]) == expected_artifact_paths
            assert inspection["next_action"] == (
                "career applications inspect-run "
                f"--application-id {application_id} --run-id {plan.run_id}"
            )
    finally:
        database.close()
