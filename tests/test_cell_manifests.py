import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from career.cells.capabilities import CapabilitySet, CapabilityViolation
from career.cells.contracts import CELL_CONTRACTS
from career.cells.manifests import ManifestStore
from career.services.application_context import paths_for


def passed_validators(paths, node_id="compose_cv"):
    validators = []
    for index, command in enumerate(CELL_CONTRACTS[node_id].validators):
        report = paths.reviews_dir / f"validation-{index}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("{}", encoding="utf-8")
        validators.append(
            {
                "command": command,
                "result": "passed",
                "report_path": report,
            }
        )
    return validators


def persist_run_plan(paths, run_id, node_ids):
    plan_path = paths.plans_dir / f"{run_id}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "application_id": paths.application_id,
                "nodes": [{"node_id": node_id} for node_id in node_ids],
            }
        ),
        encoding="utf-8",
    )
    return plan_path


def test_publish_records_input_hash_and_keeps_previous_revision(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)

    first = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b'{"version": 1}',
        inputs={"fit_map": "a"},
        validators=passed_validators(paths),
    )
    second = store.publish_file(
        "compose_cv",
        2,
        "cv_content",
        b'{"version": 2}',
        inputs={"fit_map": "b"},
        validators=passed_validators(paths),
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
    application = tmp_path / "app-a"
    caps = CapabilitySet(
        application_root=application,
        read_paths=[application],
        write_paths=[application / "staging"],
    )

    with pytest.raises(CapabilityViolation):
        caps.assert_writable(tmp_path / "app-b" / "state.json")


def test_capability_requires_application_root(tmp_path):
    with pytest.raises(TypeError, match="application_root"):
        CapabilitySet(read_paths=[tmp_path], write_paths=[tmp_path])


def test_capability_resolves_paths_and_rejects_symlink_escape(tmp_path):
    application = tmp_path / "app-a"
    staging = application / "staging"
    outside = tmp_path / "outside"
    staging.mkdir(parents=True)
    outside.mkdir()
    (staging / "escape").symlink_to(outside, target_is_directory=True)
    caps = CapabilitySet(
        application_root=application,
        read_paths=[application],
        write_paths=[staging],
    )

    assert caps.assert_readable(application / "input.json") == (
        application / "input.json"
    ).resolve()
    assert caps.assert_writable(staging / "output.json") == (
        staging / "output.json"
    ).resolve()
    with pytest.raises(CapabilityViolation):
        caps.assert_writable(staging / "escape" / "state.json")


def test_capability_rejects_allowlist_root_outside_application(tmp_path):
    application = tmp_path / "app-a"
    outside = tmp_path / "outside"

    with pytest.raises(CapabilityViolation, match="application root"):
        CapabilitySet(
            application_root=application,
            read_paths=[outside],
            write_paths=[application / "staging"],
        )


def test_capability_validates_symlink_allowlist_roots_and_application_root(tmp_path):
    real_application = tmp_path / "real-app"
    real_application.mkdir()
    application_link = tmp_path / "app-link"
    application_link.symlink_to(real_application, target_is_directory=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (real_application / "escape").symlink_to(outside, target_is_directory=True)

    caps = CapabilitySet(
        application_root=application_link,
        read_paths=[application_link],
        write_paths=[application_link / "staging"],
    )
    assert caps.assert_writable(application_link / "staging" / "result.json") == (
        real_application / "staging" / "result.json"
    ).resolve()

    with pytest.raises(CapabilityViolation, match="application root"):
        CapabilitySet(
            application_root=application_link,
            read_paths=[application_link / "escape"],
            write_paths=[],
        )


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
    store.begin_attempt("analyze_fit", 1)

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

    published = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=passed_validators(paths),
    )

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
            },
            {
                "command": "validate-provenance",
                "result": "passed",
                "report_path": report,
            },
        ],
    )

    validator = published.manifest["validators"][0]
    assert set(validator) == {"command", "result", "report_path", "executed_at"}
    assert validator["command"] == "cv:validate-content"
    assert validator["result"] == "passed"
    assert validator["report_path"] == str(report.resolve())
    assert validator["executed_at"]


@pytest.mark.parametrize(
    "validators",
    [
        [],
        [{"command": "validate-artifact", "result": "failed"}],
        [{"command": "validate-artifact"}],
        ["validate-artifact"],
    ],
    ids=["missing", "failed", "missing-result", "unverified-string"],
)
def test_publish_refuses_missing_or_unpassed_validators(tmp_path, validators):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)

    with pytest.raises(ValueError, match="validator"):
        store.publish_file(
            "compose_cv",
            1,
            "cv_content",
            b"not validated",
            validators=validators,
        )

    assert not paths.artifacts_dir.exists()


def test_publish_requires_every_validator_declared_by_node_contract(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    report = paths.reviews_dir / "fit-map.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}", encoding="utf-8")
    store = ManifestStore(paths)

    with pytest.raises(ValueError, match="missing required validator"):
        store.publish_file(
            "analyze_fit",
            1,
            "fit_map",
            b"validated by only one command",
            validators=[
                {
                    "command": "validate:fit-map",
                    "result": "passed",
                    "report_path": report,
                }
            ],
        )

    assert not paths.artifacts_dir.exists()


def test_publish_rejects_inputs_that_differ_from_attempt_manifest(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    attempt = store.begin_attempt(
        "compose_cv", 1, run_id="run-1", inputs={"fit_map": "original"}
    )
    original = attempt.path.read_bytes()

    with pytest.raises(ValueError, match="inputs do not match"):
        store.publish_file(
            "compose_cv",
            1,
            "cv_content",
            b"forged",
            inputs={"fit_map": "forged"},
            validators=passed_validators(paths),
        )

    assert attempt.path.read_bytes() == original
    assert not paths.artifacts_dir.exists()


def test_begin_attempt_rejects_duplicate_without_overwriting_manifest(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    first = store.begin_attempt("compose_cv", 1, run_id="run-1")
    original = first.path.read_bytes()

    with pytest.raises(RuntimeError, match="attempt already exists"):
        store.begin_attempt("compose_cv", 1, run_id="forged-run")

    assert first.path.read_bytes() == original
    assert json.loads(original)["run_id"] == "run-1"


def test_publish_rejects_identical_revision_without_overwriting_provenance(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    first = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"identical",
        inputs={"fit_map": "first"},
        validators=passed_validators(paths),
    )
    original = first.manifest_path.read_bytes()

    with pytest.raises(RuntimeError, match="artifact revision already exists"):
        store.publish_file(
            "compose_cv",
            2,
            "cv_content",
            b"identical",
            inputs={"fit_map": "forged"},
            validators=passed_validators(paths),
        )

    assert first.manifest_path.read_bytes() == original
    assert json.loads(original)["inputs"]["fit_map"]["sha256"] == "first"


def test_publish_rejects_reuse_of_a_finalized_attempt(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    first = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"first",
        validators=passed_validators(paths),
    )
    original_attempt = (
        paths.cells_dir / "compose_cv" / "1" / "manifest.json"
    ).read_bytes()

    with pytest.raises(RuntimeError, match="attempt cannot be reused"):
        store.publish_file(
            "compose_cv",
            1,
            "other_content",
            b"second",
            validators=passed_validators(paths),
        )

    assert first.path.read_bytes() == b"first"
    assert (
        paths.cells_dir / "compose_cv" / "1" / "manifest.json"
    ).read_bytes() == original_attempt
    assert not (paths.artifacts_dir / "other_content").exists()


def test_concurrent_publications_cannot_reuse_the_same_attempt(tmp_path, monkeypatch):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    store.begin_attempt("compose_cv", 1, run_id="run-1")
    validators = passed_validators(paths)
    barrier = Barrier(2)
    original_load = store._load_or_begin_attempt

    def synchronized_load(*args, **kwargs):
        record = original_load(*args, **kwargs)
        barrier.wait(timeout=2)
        return record

    monkeypatch.setattr(store, "_load_or_begin_attempt", synchronized_load)

    def publish(name):
        try:
            store.publish_file(
                "compose_cv",
                1,
                name,
                name.encode(),
                validators=validators,
            )
        except RuntimeError as exc:
            return str(exc)
        return "published"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(publish, ["first", "second"]))

    assert outcomes.count("published") == 1
    assert sum("attempt cannot be reused" in outcome for outcome in outcomes) == 1


def test_finish_run_uses_only_explicit_validated_artifacts_and_blockers(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    persist_run_plan(paths, "run-1", ["compose_cv", "deliver_cv"])
    ignored = paths.artifacts_dir / "ignored" / "existing.txt"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("file existence is not completion", encoding="utf-8")
    store.begin_attempt("compose_cv", 1, run_id="run-1")
    published = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=passed_validators(paths),
    )
    blocked = store.begin_attempt("deliver_cv", 1, run_id="run-1", status="blocked")

    completion = store.finish_run(
        "run-1",
        validated_artifacts=[published],
        blocked_nodes=[{"node_id": "deliver_cv", "attempt": 1}],
    )

    assert completion.path == paths.run_completion_manifest.resolve()
    assert completion.manifest["validated_artifacts"] == [published.manifest]
    assert completion.manifest["blocked_nodes"] == [
        {
            "node_id": "deliver_cv",
            "attempt": 1,
            "status": "blocked",
            "manifest_path": str(blocked.path),
        }
    ]
    assert completion.manifest["status"] == "blocked"
    assert "ignored" not in completion.path.read_text(encoding="utf-8")


def test_finish_run_rejects_forged_artifact_mapping(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    persist_run_plan(paths, "run-1", ["compose_cv"])
    forged = {
        "kind": "artifact_manifest",
        "application_id": "app-1",
        "run_id": "run-1",
        "node_id": "compose_cv",
        "attempt": 1,
        "artifact_name": "cv_content",
        "path": str(paths.artifacts_dir / "cv_content" / "fake" / "cv_content"),
        "sha256": "fake",
        "revision": "fake",
        "inputs": {},
        "validators": [{"command": "fake", "result": "passed"}],
        "status": "validated",
    }

    with pytest.raises(ValueError, match="persisted artifact manifest"):
        store.finish_run("run-1", validated_artifacts=[forged], blocked_nodes=[])


def test_finish_run_rejects_foreign_and_stale_persisted_artifacts(tmp_path):
    first_paths = paths_for("app-1", root=tmp_path)
    second_paths = paths_for("app-2", root=tmp_path)
    first_store = ManifestStore(first_paths)
    second_store = ManifestStore(second_paths)
    persist_run_plan(first_paths, "run-old", ["compose_cv"])
    first_store.begin_attempt("compose_cv", 1, run_id="run-old")
    published = first_store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=passed_validators(first_paths),
    )
    forged_mapping = dict(published.manifest)
    forged_mapping["node_id"] = "forged_node"

    with pytest.raises(ValueError, match="forged artifact mapping"):
        first_store.finish_run(
            "run-old", validated_artifacts=[forged_mapping], blocked_nodes=[]
        )
    with pytest.raises(ValueError, match="stale artifact manifest"):
        first_store.finish_run(
            "run-new", validated_artifacts=[dict(published.manifest)], blocked_nodes=[]
        )
    with pytest.raises(ValueError, match="application directory"):
        second_store.finish_run(
            "run-old", validated_artifacts=[dict(published.manifest)], blocked_nodes=[]
        )


def test_finish_run_rejects_forged_or_nonblocked_node_mapping(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    persist_run_plan(paths, "run-1", ["deliver_cv"])
    store.begin_attempt("deliver_cv", 1, run_id="run-1", status="planned")

    with pytest.raises(ValueError, match="persisted blocked attempt"):
        store.finish_run(
            "run-1",
            validated_artifacts=[],
            blocked_nodes=[{"node_id": "deliver_cv", "attempt": 1, "status": "blocked"}],
        )


def test_finish_run_discovers_persisted_artifacts_and_blockers_when_omitted(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    persist_run_plan(paths, "run-1", ["compose_cv", "deliver_cv"])
    store.begin_attempt("compose_cv", 1, run_id="run-1")
    published = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=passed_validators(paths),
    )
    blocked = store.begin_attempt("deliver_cv", 1, run_id="run-1", status="blocked")

    completion = store.finish_run(
        "run-1", validated_artifacts=[], blocked_nodes=[]
    )

    assert completion.manifest["validated_artifacts"] == [published.manifest]
    assert completion.manifest["blocked_nodes"] == [
        {
            "node_id": "deliver_cv",
            "attempt": 1,
            "status": "blocked",
            "manifest_path": str(blocked.path),
        }
    ]
    assert completion.manifest["status"] == "blocked"


def test_finish_run_rejects_missing_plan_and_nonterminal_attempts(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)

    with pytest.raises(ValueError, match="persisted run plan"):
        store.finish_run("missing-run", validated_artifacts=[], blocked_nodes=[])

    persist_run_plan(paths, "run-1", ["compose_cv"])
    store.begin_attempt("compose_cv", 1, run_id="run-1", status="planned")
    with pytest.raises(ValueError, match="nonterminal attempt"):
        store.finish_run("run-1", validated_artifacts=[], blocked_nodes=[])


def test_finish_run_rejects_missing_persisted_output_revision(tmp_path):
    paths = paths_for("app-1", root=tmp_path)
    store = ManifestStore(paths)
    persist_run_plan(paths, "run-1", ["compose_cv"])
    store.begin_attempt("compose_cv", 1, run_id="run-1")
    published = store.publish_file(
        "compose_cv",
        1,
        "cv_content",
        b"validated",
        validators=passed_validators(paths),
    )
    published.manifest_path.unlink()

    with pytest.raises(ValueError, match="persisted output manifest"):
        store.finish_run("run-1", validated_artifacts=[], blocked_nodes=[])


def test_application_paths_expose_cell_data_directories(tmp_path):
    paths = paths_for("app-1", root=tmp_path)

    assert paths.plans_dir == paths.app_dir / "plans"
    assert paths.cells_dir == paths.app_dir / "cells"
    assert paths.artifacts_dir == paths.app_dir / "artifacts"
    assert paths.reviews_dir == paths.app_dir / "reviews"
    assert paths.run_completion_manifest == paths.app_dir / "run_completion_manifest.json"
