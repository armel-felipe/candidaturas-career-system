from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_cellular_runs import migrate_application  # noqa: E402

from career.cells.executor import CellExecutor  # noqa: E402
from career.services.database import Database  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>",
        )
        archive.writestr(
            "word/document.xml",
            "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body/></w:document>",
        )
        archive.writestr(
            "word/styles.xml",
            "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"/>",
        )
        archive.writestr(
            "word/theme/theme1.xml",
            "<a:theme xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><a:latin typeface=\"Arial\"/></a:theme>",
        )


def _seed_legacy_application(
    path: Path, *, reviewed: str | None = None
) -> dict[str, str]:
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
    docx_path = path / "legacy_cv.docx"
    if reviewed == "verified":
        _write_docx(docx_path)
    else:
        docx_path.write_bytes(b"PK\x03\x04legacy-docx")
    if reviewed == "minimal":
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
    elif reviewed == "verified":
        artifact_sha256 = _sha256(docx_path)
        polish_path = path / "polish_review.json"
        polish_path.write_text(
            json.dumps(
                {
                    "polish_executed": True,
                    "approval_blockers": [],
                    "artifact": str(docx_path),
                    "artifact_sha256": artifact_sha256,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        review_path = path / "cv_review_report.json"
        review_path.write_text(
            json.dumps(
                {
                    "approved": True,
                    "approved_for_delivery": True,
                    "artifact": str(docx_path),
                    "artifact_sha256": artifact_sha256,
                    "polish_report": str(polish_path),
                    "polish_report_sha256": _sha256(polish_path),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        registry_path = path / "keyword_ats_registry.json"
        registry_path.write_text(
            json.dumps({"keywords": ["operations", "planning"]}, sort_keys=True),
            encoding="utf-8",
        )
        (path / "approved_cv_manifest.json").write_text(
            json.dumps(
                {
                    "approved_for_delivery": True,
                    "artifact": str(docx_path),
                    "artifact_sha256": artifact_sha256,
                    "review_report": str(review_path),
                    "review_report_sha256": _sha256(review_path),
                    "polish_report": str(polish_path),
                    "polish_report_sha256": _sha256(polish_path),
                    "keyword_registry": str(registry_path),
                    "keyword_registry_sha256": _sha256(registry_path),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
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


def test_migration_rejects_minimal_fake_approval_and_invalid_docx(tmp_path):
    legacy = tmp_path / "legacy-app"
    _seed_legacy_application(legacy, reviewed="minimal")

    result = migrate_application(legacy, application_id="app-1", dry_run=False)

    assert result["imported_nodes"]["review_cv"] == "blocked"
    assert result["imported_nodes"]["render_cv"] == "blocked"
    assert "legacy_cv_review_unknown_or_unapproved" in result["blockers"]


def test_migration_manifest_is_idempotent_immutable_and_hashes_legacy_sources(tmp_path):
    legacy = tmp_path / "applications" / "app-1"
    source_hashes = _seed_legacy_application(legacy, reviewed="verified")
    database_path = tmp_path / "career.db"

    first = migrate_application(
        legacy,
        application_id="app-1",
        dry_run=False,
        database_path=database_path,
    )
    manifest_path = Path(first["manifest_path"])
    first_bytes = manifest_path.read_bytes()
    second = migrate_application(
        legacy,
        application_id="app-1",
        dry_run=False,
        database_path=database_path,
    )

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
    assert first["run_id"] == second["run_id"] == manifest["run_id"]

    database = Database(database_path)
    database.init_schema()
    try:
        assert database.fetch_one(
            "SELECT application_id FROM application_runs WHERE run_id = ?",
            (first["run_id"],),
        ) == {"application_id": "app-1"}
        assert len(
            database.fetch_all(
                "SELECT node_id FROM cell_nodes WHERE run_id = ?", (first["run_id"],)
            )
        ) >= 6
        assert len(
            database.fetch_all(
                "SELECT node_id FROM cell_attempts WHERE run_id = ?",
                (first["run_id"],),
            )
        ) >= 6
        assert database.fetch_all(
            "SELECT artifact_name, content_hash FROM artifacts WHERE run_id = ?",
            (first["run_id"],),
        )
        executor = CellExecutor(database, applications_root=legacy.parent)
        resumed = executor.resume(first["run_id"])
        assert resumed.application_id == "app-1"
        assert resumed.statuses["review_cv"] == "validated"
    finally:
        database.close()

    assert all(
        (legacy / node["manifest_path"]).is_file() for node in manifest["nodes"]
    )
