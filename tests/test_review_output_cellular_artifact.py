from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from review_output import is_validated_cellular_artifact  # noqa: E402


def test_rejects_fabricated_adjacent_cellular_manifest(tmp_path):
    artifact = tmp_path / "applications" / "other-app" / "artifacts" / "foreign-run" / "cv.docx" / "badrevision" / "cv.docx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fabricated docx")
    manifest = {
        "status": "validated",
        "artifact_name": "cv.docx",
        "path": str(artifact.resolve()),
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    (artifact.parent / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert not is_validated_cellular_artifact(artifact)


def test_rejects_structurally_complete_forged_manifest_and_validator_report(tmp_path):
    app = tmp_path / "applications" / "app-1"
    digest = hashlib.sha256(b"fabricated docx").hexdigest()
    revision = digest[:12]
    revision_dir = app / "artifacts" / "run-1" / "cv.docx" / revision
    revision_dir.mkdir(parents=True)
    artifact = revision_dir / "cv.docx"
    artifact.write_bytes(b"fabricated docx")
    report = app / "reviews" / "render.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"command": "validate:docx", "result": "passed"}), encoding="utf-8")
    manifest = {
        "kind": "artifact_manifest", "status": "validated", "application_id": "app-1", "run_id": "run-1",
        "node_id": "render_cv", "attempt": 1, "artifact_name": "cv.docx", "revision": revision,
        "path": str(artifact.resolve()), "manifest_path": str((revision_dir / "manifest.json").resolve()),
        "sha256": digest,
        "validators": [{"command": "validate:docx", "result": "passed", "report_path": str(report.resolve())}],
    }
    (revision_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert not is_validated_cellular_artifact(artifact)
