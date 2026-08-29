from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

import cv_approve_and_deliver


def test_cv_deliver_rejects_missing_application_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "cv.docx"
    artifact.write_bytes(b"docx")
    monkeypatch.setattr(
        sys,
        "argv",
        ["cv_approve_and_deliver.py", "--artifact", str(artifact)],
    )

    with pytest.raises(SystemExit) as error:
        cv_approve_and_deliver.main()

    assert error.value.code == 2


def test_cv_deliver_passes_application_scope_and_uses_scoped_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "cv.docx"
    delivery_report = tmp_path / "delivery.json"
    combined_report = tmp_path / "combined.json"
    artifact.write_bytes(b"docx")
    commands: list[list[str]] = []
    app_dir = tmp_path / "applications_v2" / "notion_589"
    app_dir.mkdir(parents=True)
    scoped_paths = SimpleNamespace(
        fit_map=app_dir / "fit_map.json",
        derived_dir=app_dir / "derived",
        cv_review_report=app_dir / "cv_review_report.json",
        polish_review=app_dir / "polish_review.json",
    )
    monkeypatch.setattr(
        cv_approve_and_deliver.application_context,
        "paths_for",
        lambda application_id: scoped_paths,
    )

    def fake_run(command: list[str], timeout: int | None = None):
        commands.append(command)
        if "approve" in command:
            scoped_paths.cv_review_report.write_text(
                '{"approved_for_delivery": true}\n', encoding="utf-8"
            )
        else:
            delivery_report.write_text(
                '{"status": "dry_run_ok"}\n', encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(cv_approve_and_deliver, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cv_approve_and_deliver.py",
            "--artifact",
            str(artifact),
            "--application-id",
            "notion_589",
            "--delivery-report",
            str(delivery_report),
            "--combined-report",
            str(combined_report),
            "--dry-run",
        ],
    )

    assert cv_approve_and_deliver.main() == 0
    approval = commands[0]
    assert "--application-id" in approval
    assert approval[approval.index("--application-id") + 1] == "notion_589"
    assert approval[approval.index("--fit-map") + 1].endswith(
        "applications_v2/notion_589/fit_map.json"
    )
    assert approval[approval.index("--registry") + 1].endswith(
        "applications_v2/notion_589/derived/keyword_ats_registry.json"
    )
