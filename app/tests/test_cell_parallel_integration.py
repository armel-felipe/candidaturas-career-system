from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from career import cli
from career.services.applications_v2 import run_parallel_fixture_workers
from career.services import application_context
from career.services.database import Database


def test_two_hermes_profiles_keep_delegated_flows_isolated(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    try:
        first = application_context.claim_profile_application(
            database,
            profile_id="hermes-a",
            application_id="notion_515",
            source="notion_record",
        )
        second = application_context.claim_profile_application(
            database,
            profile_id="hermes-b",
            application_id="pasted_beta_ops",
            source="pasted_text",
        )

        runs = run_parallel_fixture_workers(
            tmp_path / "cellular",
            applications=(first["application_id"], second["application_id"]),
        )

        assert first["application_id"] != second["application_id"]
        assert first["profile_id"] != second["profile_id"]
        assert {run["application_id"] for run in runs} == {
            first["application_id"],
            second["application_id"],
        }
        assert len({run["run_id"] for run in runs}) == 2
        assert len({run["manifest_path"] for run in runs}) == 2
        assert all(
            application_id in manifest
            for application_id, manifest in {
                run["application_id"]: run["manifest_path"] for run in runs
            }.items()
        )

        with pytest.raises(ValueError, match="profile_does_not_own_application"):
            application_context.release_profile_application(
                database,
                profile_id="hermes-a",
                application_id=second["application_id"],
            )
    finally:
        database.close()


def test_two_processes_complete_separate_normalization_cells(tmp_path):
    results = run_parallel_fixture_workers(
        tmp_path, applications=("app-a", "app-b")
    )

    assert {item["status"] for item in results} == {"validated"}
    assert len({item["pid"] for item in results}) == 2
    assert os.getpid() not in {item["pid"] for item in results}
    assert results[0]["job_fingerprint"] != results[1]["job_fingerprint"]
    assert len({item["run_id"] for item in results}) == 2
    assert len({item["manifest_path"] for item in results}) == 2

    for item in results:
        application_root = (
            tmp_path / "applications" / item["application_id"]
        ).resolve()
        manifest = Path(item["manifest_path"]).resolve()
        assert manifest.is_relative_to(application_root)
        assert all(
            Path(path).resolve().is_relative_to(application_root)
            for path in item["artifact_paths"]
        )
        assert not any(
            other in str(manifest)
            for other in {"app-a", "app-b"} - {item["application_id"]}
        )

    ordered = sorted(results, key=lambda item: item["external_lock_entered_at"])
    assert ordered[0]["external_lock_released_at"] <= ordered[1][
        "external_lock_entered_at"
    ]
    assert {item["external_resource"] for item in results} == {"notion-write"}
    assert sum(item["external_lock_contention_count"] for item in results) >= 1
    assert {item["external_lock_node_id"] for item in results} == {
        "sync_notion_initial"
    }
    assert all(item["external_resource_declared_by_contract"] for item in results)
    assert all(item["unexpected_writes"] == [] for item in results)


def test_verify_parallel_cli_uses_fixture_directory_and_returns_proof(
    tmp_path, capsys
):
    fixture_dir = tmp_path / "fixture"

    assert (
        cli.main(
            [
                "applications",
                "verify-parallel",
                "--fixture-dir",
                str(fixture_dir),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "validated"
    assert payload["subprocess_count"] == 2
    assert payload["distinct_fingerprints"] is True
    assert payload["distinct_manifests"] is True
    assert payload["crossed_paths"] == []
    assert payload["external_locks_serialized"] is True
    assert payload["external_lock_contention_observed"] is True


def test_package_exposes_cellular_migration_and_parallel_verification_aliases():
    package = json.loads(
        (Path(__file__).resolve().parent.parent / "package.json").read_text(
            encoding="utf-8"
        )
    )

    assert package["scripts"]["applications:migrate-cellular"].endswith(
        "applications migrate-cellular"
    )
    assert package["scripts"]["applications:authorize-handoff"].endswith(
        "applications authorize-handoff"
    )
    assert package["scripts"]["applications:verify-parallel"].endswith(
        "applications verify-parallel"
    )
