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
