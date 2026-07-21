from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_cellular_runs import migrate_application  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_legacy_application(path: Path, *, reviewed: bool = False) -> dict[str, str]:
    path.mkdir(parents=True)
    (path / "job_description.md").write_text(
        "# Operations Lead\n\nLead planning and logistics.\n", encoding="utf-8"
    )
    (path / "fit_map.json").write_text(
        json.dumps({"cargo": "Operations Lead", "nota_aderencia": {"final": 7.1}}),
        encoding="utf-8",
    )
    (path / "cv_content.json").write_text(
        json.dumps({"professional_summary": "Operations leader"}), encoding="utf-8"
    )
    (path / "legacy_cv.docx").write_bytes(b"PK\x03\x04legacy-docx")
    if reviewed:
        (path / "cv_review_report.json").write_text(
            json.dumps(
                {
                    "approved": True,
                    "approved_for_delivery": True,
                    "artifact": str(path / "legacy_cv.docx"),
                }
            ),
            encoding="utf-8",
        )
        (path / "polish_review.json").write_text(
            json.dumps({"approval_blockers": []}), encoding="utf-8"
        )
    return {
        str(item.relative_to(path)): _sha256(item)
        for item in path.iterdir()
        if item.is_file()
    }


def test_migration_never_marks_unreviewed_cv_as_validated(tmp_path):
    legacy = tmp_path / "legacy-app"
    before = _seed_legacy_application(legacy)

    result = migrate_application(legacy, application_id="app-1", dry_run=False)

    assert result["status"] == "migrated"
    assert result["imported_nodes"]["review_cv"] == "blocked"
    assert result["imported_nodes"]["render_cv"] == "blocked"
    assert result["blockers"] == ["legacy_cv_review_unknown_or_unapproved"]
    assert {
        str(item.relative_to(legacy)): _sha256(item)
        for item in legacy.iterdir()
        if item.is_file() and item.name != "cellular_migration_manifest.json"
    } == before


def test_migration_dry_run_writes_nothing_and_reports_the_planned_manifest(tmp_path):
    legacy = tmp_path / "legacy-app"
    before = _seed_legacy_application(legacy)

    result = migrate_application(legacy, application_id="app-1", dry_run=True)

    assert result["status"] == "dry_run"
    assert result["manifest_path"].endswith("cellular_migration_manifest.json")
    assert not (legacy / "cellular_migration_manifest.json").exists()
    assert {
        str(item.relative_to(legacy)): _sha256(item)
        for item in legacy.iterdir()
        if item.is_file()
    } == before


def test_migration_manifest_is_idempotent_immutable_and_hashes_legacy_sources(tmp_path):
    legacy = tmp_path / "legacy-app"
    source_hashes = _seed_legacy_application(legacy, reviewed=True)

    first = migrate_application(legacy, application_id="app-1", dry_run=False)
    manifest_path = Path(first["manifest_path"])
    first_bytes = manifest_path.read_bytes()
    second = migrate_application(legacy, application_id="app-1", dry_run=False)

    assert first["imported_nodes"]["review_cv"] == "validated"
    assert second["status"] == "already_migrated"
    assert manifest_path.read_bytes() == first_bytes
    manifest = json.loads(first_bytes)
    assert manifest["kind"] == "cellular_legacy_import_manifest"
    assert manifest["application_id"] == "app-1"
    assert {
        item["source_path"]: item["sha256"] for item in manifest["source_artifacts"]
    } == source_hashes
    assert all(item["validation_origin"] != "fabricated" for item in manifest["nodes"])

