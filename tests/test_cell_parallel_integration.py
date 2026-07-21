from __future__ import annotations

import json
import os
from pathlib import Path

from career import cli
from career.services.applications_v2 import run_parallel_fixture_workers


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
    assert package["scripts"]["applications:verify-parallel"].endswith(
        "applications verify-parallel"
    )
