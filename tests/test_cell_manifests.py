import json
from pathlib import Path

import pytest

from career.cells.capabilities import CapabilitySet, CapabilityViolation
from career.cells.manifests import ManifestStore
from career.services.application_context import paths_for


def test_publish_records_input_hash_and_keeps_previous_revision(tmp_path):
    store = ManifestStore(paths_for("app-1", root=tmp_path))

    first = store.publish_file(
        "compose_cv", 1, "cv_content", b'{"version": 1}', inputs={"fit_map": "a"}
    )
    second = store.publish_file(
        "compose_cv", 2, "cv_content", b'{"version": 2}', inputs={"fit_map": "b"}
    )

    assert first.path != second.path
    assert first.path.read_bytes() == b'{"version": 1}'
    assert second.path.read_bytes() == b'{"version": 2}'
    assert second.manifest["inputs"]["fit_map"] == {
        "path": "fit_map",
        "sha256": "b",
        "revision": None,
        "source_kind": "artifact",
    }


def test_capability_rejects_other_application_path(tmp_path):
    caps = CapabilitySet(
        read_paths=[tmp_path / "app-a"],
        write_paths=[tmp_path / "app-a" / "staging"],
    )

    with pytest.raises(CapabilityViolation):
        caps.assert_writable(tmp_path / "app-b" / "state.json")


def test_capability_resolves_paths_and_rejects_symlink_escape(tmp_path):
    application = tmp_path / "app-a"
    staging = application / "staging"
    outside = tmp_path / "outside"
    staging.mkdir(parents=True)
    outside.mkdir()
    (staging / "escape").symlink_to(outside, target_is_directory=True)
    caps = CapabilitySet(read_paths=[application], write_paths=[staging])

    assert caps.assert_readable(application / "input.json") == (
        application / "input.json"
    ).resolve()
    assert caps.assert_writable(staging / "output.json") == (
        staging / "output.json"
    ).resolve()
    with pytest.raises(CapabilityViolation):
        caps.assert_writable(staging / "escape" / "state.json")


def test_begin_attempt_persists_manifest_and_application_scoped_staging(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)

    attempt = store.begin_attempt(
        "compose_cv",
        2,
        run_id="run-1",
        contract_version="1",
        inputs={
            "fit_map": {
                "path": "fit_map.json",
                "sha256": "abc",
                "revision": "fit-2",
                "source_kind": "validated_artifact",
            }
        },
        read_paths=[paths.fit_map],
        write_paths=[paths.cells_dir / "compose_cv" / "2" / "staging"],
    )

    expected_dir = paths.cells_dir / "compose_cv" / "2"
    assert attempt.staging_dir == (expected_dir / "staging").resolve()
    assert attempt.path == (expected_dir / "manifest.json").resolve()
    assert attempt.staging_dir.is_dir()
    assert json.loads(attempt.path.read_text(encoding="utf-8"))["inputs"]["fit_map"] == {
        "path": "fit_map.json",
        "sha256": "abc",
        "revision": "fit-2",
        "source_kind": "validated_artifact",
    }


def test_write_handover_is_attempt_scoped_and_rejects_path_escape(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)

    handover_path = store.write_handover("analyze_fit", 1, {"decision": "proceed"})

    assert handover_path == (
        paths.cells_dir / "analyze_fit" / "1" / "handover_summary.json"
    ).resolve()
    assert json.loads(handover_path.read_text(encoding="utf-8")) == {
        "decision": "proceed"
    }
    with pytest.raises(ValueError, match="application directory"):
        store.write_handover("../other-app", 1, {"decision": "escape"})


def test_publish_uses_staging_and_atomic_replace(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    replacements: list[tuple[Path, Path]] = []
    real_replace = __import__("os").replace

    def recording_replace(source, target):
        replacements.append((Path(source), Path(target)))
        real_replace(source, target)

    monkeypatch.setattr("career.cells.manifests.os.replace", recording_replace)

    published = store.publish_file("compose_cv", 1, "cv_content", b"validated")

    assert replacements
    source, target = next(
        (source, target)
        for source, target in replacements
        if target == published.path
    )
    assert source.parent == (
        paths.cells_dir / "compose_cv" / "1" / "staging"
    ).resolve()
    assert target == published.path
    assert published.path.parent.parent == paths.artifacts_dir.resolve() / "cv_content"
    assert published.path.parent.name == published.manifest["sha256"][:12]


def test_publish_records_normalized_validators(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    report = paths.reviews_dir / "cv_review.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}", encoding="utf-8")
    store = ManifestStore(paths)

    published = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=[
            {
                "command": "cv:validate-content",
                "result": "passed",
                "report_path": report,
            }
        ],
    )

    validator = published.manifest["validators"][0]
    assert set(validator) == {"command", "result", "report_path", "executed_at"}
    assert validator["command"] == "cv:validate-content"
    assert validator["result"] == "passed"
    assert validator["report_path"] == str(report.resolve())
    assert validator["executed_at"]


def test_finish_run_uses_only_explicit_validated_artifacts_and_blockers(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    ignored = paths.artifacts_dir / "ignored" / "existing.txt"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("file existence is not completion", encoding="utf-8")
    published = store.publish_file("compose_cv", 1, "cv_content", b"validated")

    completion = store.finish_run(
        "run-1",
        validated_artifacts=[published],
        blocked_nodes=[{"node_id": "deliver_cv", "reason": "review required"}],
    )

    assert completion.path == paths.run_completion_manifest.resolve()
    assert completion.manifest["validated_artifacts"] == [published.manifest]
    assert completion.manifest["blocked_nodes"] == [
        {"node_id": "deliver_cv", "reason": "review required"}
    ]
    assert "ignored" not in completion.path.read_text(encoding="utf-8")


def test_application_paths_expose_cell_data_directories(tmp_path):
    paths = paths_for("app-1", root=tmp_path)

    assert paths.plans_dir == paths.app_dir / "plans"
    assert paths.cells_dir == paths.app_dir / "cells"
    assert paths.artifacts_dir == paths.app_dir / "artifacts"
    assert paths.reviews_dir == paths.app_dir / "reviews"
    assert paths.run_completion_manifest == paths.app_dir / "run_completion_manifest.json"
