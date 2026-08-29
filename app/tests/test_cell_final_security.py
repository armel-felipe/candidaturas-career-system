from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from career.cells.capabilities import (
    CapabilitySet,
    CapabilityViolation,
    canonical_node_executable,
)
from career.cells.executor import CellExecutor
from career.cells.handlers import production_handler_registry
from career.services import review as review_service
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import write_json


ROOT = Path(__file__).resolve().parent.parent


def test_canonical_subprocess_rejects_path_and_python_environment_overrides(tmp_path):
    app = tmp_path / "applications" / "app-a"
    staging = app / "cells" / "render_cv" / "1" / "staging"
    staging.mkdir(parents=True)
    content = staging / "cv_content.json"
    content.write_text("{}", encoding="utf-8")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    marker = staging / "fake-node-ran"
    fake_node = fake_bin / "node"
    fake_node.write_text(
        "#!/bin/sh\nprintf compromised > \"$FAKE_NODE_MARKER\"\n",
        encoding="utf-8",
    )
    fake_node.chmod(0o755)
    capability = CapabilitySet(
        application_root=app,
        read_paths=[app],
        write_paths=[staging],
    )
    attacker_env = {
        **os.environ,
        "PATH": str(fake_bin),
        "PYTHON": str(fake_node),
        "FAKE_NODE_MARKER": str(marker),
    }

    for executable, expected in (
        (str(canonical_node_executable()), "environment"),
        ("node", "subprocess|executable"),
    ):
        with pytest.raises(CapabilityViolation, match=expected):
            with capability.enforce_writes():
                subprocess.run(
                    [
                        executable,
                        "scripts/docx/generate_custom_cv.js",
                        "--content",
                        str(content),
                    "--output-dir",
                    str(staging),
                    "--application-id",
                    "app-a",
                ],
                    cwd=ROOT,
                    env=attacker_env,
                    check=False,
                )

    assert not marker.exists()


def test_canonical_journal_rejects_symlinked_projection_before_capture_and_restore(
    tmp_path,
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    app_a = paths_for("app-a", root=root)
    app_b = paths_for("app-b", root=root)
    app_a.derived_dir.mkdir(parents=True)
    app_b.derived_dir.mkdir(parents=True)
    local = app_a.derived_dir / "local.json"
    local.write_text('{"local": true}', encoding="utf-8")
    foreign = app_b.derived_dir / "foreign.json"
    foreign.write_text('{"foreign": true}', encoding="utf-8")
    executor = CellExecutor(database, applications_root=root)
    plan = executor.plan("app-a", {"cv"})
    _plan, app_a = executor._load_run(plan.run_id)

    journal = executor._begin_canonical_journal(
        app_a, plan.run_id, "normalize_job", 1
    )
    parked = app_a.app_dir / "derived.parked"
    app_a.derived_dir.rename(parked)
    app_a.derived_dir.symlink_to(app_b.derived_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink|application directory"):
        executor._restore_canonical_journal(journal)
    assert foreign.read_text(encoding="utf-8") == '{"foreign": true}'

    journal.unlink(missing_ok=True)
    database.execute("DELETE FROM canonical_journal_snapshots")
    with pytest.raises(ValueError, match="symlink|application directory"):
        executor._begin_canonical_journal(
            app_a, plan.run_id, "normalize_job", 2
        )
    assert foreign.read_text(encoding="utf-8") == '{"foreign": true}'
    database.close()


def test_canonical_target_safety_rejects_symlinked_applications_root_ancestor(
    tmp_path,
):
    real_parent = tmp_path / "real-parent"
    real_root = real_parent / "applications"
    real_app = paths_for("app-a", root=real_root)
    real_app.app_dir.mkdir(parents=True)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    linked_app = paths_for("app-a", root=linked_parent / "applications")

    with pytest.raises(ValueError, match="symlink|application directory"):
        CellExecutor._assert_canonical_target_safe(
            linked_app,
            linked_app.job_description,
        )

    assert not real_app.job_description.exists()


def test_cv_review_command_requires_scoped_translation_registry(
    tmp_path, monkeypatch
):
    artifact = tmp_path / "cv.docx"
    fit_map = tmp_path / "fit_map.json"
    registry = tmp_path / "keyword_registry.json"
    translation_registry = tmp_path / "keyword_translation_registry.json"
    report = tmp_path / "cv_review.json"
    polish = tmp_path / "polish_review.json"
    artifact.write_bytes(b"PK\x03\x04docx")
    fit_map.write_text("{}", encoding="utf-8")
    (tmp_path / "enquadramento.json").write_text(
        '{"job_fingerprint":"fixture","experiencias":[{"experience_id":"fixture"}]}',
        encoding="utf-8",
    )
    translation_registry.write_text(
        '{"version": 1, "policy": {}, "entries": {}}', encoding="utf-8"
    )
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(list(command))
        registry.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_review(*_args, **_kwargs):
        payload = {"approved_for_delivery": True}
        write_json(report, payload)
        return payload

    def fake_polish(*_args, **_kwargs):
        payload = {"approval_blockers": []}
        write_json(polish, payload)
        return payload

    monkeypatch.setattr(review_service.subprocess, "run", fake_run)
    monkeypatch.setattr(review_service, "review_cv", fake_review)
    monkeypatch.setattr(review_service, "polish_cv", fake_polish)

    review_service.approve_cv(
        artifact,
        fit_map,
        registry,
        report,
        polish,
        translation_registry_path=translation_registry,
    )

    command = commands[0]
    assert "--translation-registry" in command
    assert command[command.index("--translation-registry") + 1] == str(
        translation_registry
    )


def test_keyword_registration_cli_requires_translation_registry(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/register_keywords.py"),
            "--fit-map",
            str(tmp_path / "fit_map.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--translation-registry" in result.stderr


def test_mandatory_keyword_registration_documentation_names_translation_registry():
    documented_callers = (
        ".agents/skills/career-fit-analysis/SKILL.md",
        ".agents/skills/cv-generator/SKILL.md",
        ".agents/skills/output-reviewer/SKILL.md",
        ".agents/skills/unified-job-analysis/SKILL.md",
        ".agents/skills/career-system/references/keyword_ats_registry.md",
        "src/career/services/fit_map.py",
        "src/career/services/agent_guard.py",
        "src/career/services/harness_supervisor.py",
    )

    missing: list[str] = []
    for relative in documented_callers:
        for line_number, line in enumerate(
            (ROOT / relative).read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if (
                "scripts/register_keywords.py" in line
                and "--fit-map" in line
                and "--translation-registry" not in line
            ):
                missing.append(f"{relative}:{line_number}")

    assert missing == []


def test_mandatory_delivery_documentation_and_npm_alias_name_report_path():
    rclone_doc = (ROOT / "RCLONE_ONEDRIVE_DELIVERY.md").read_text(
        encoding="utf-8"
    )
    undocumented = [
        line
        for line in rclone_doc.splitlines()
        if "npm run deliver:artifact" in line and "--report" not in line
    ]
    package_scripts = json.loads(
        (ROOT / "package.json").read_text(encoding="utf-8")
    )["scripts"]

    assert undocumented == []
    assert "--report" in package_scripts["deliver:artifact"]


def test_delivery_request_and_canonical_command_use_scoped_report(tmp_path, monkeypatch):
    from career.services.delivery import CanonicalDeliveryCellAdapter

    paths = paths_for("app-a", root=tmp_path / "applications")
    staging = paths.cells_dir / "deliver_cv" / "1" / "staging"
    receipts = paths.cells_dir / "deliver_cv" / "receipts" / "run-a"
    staging.mkdir(parents=True)
    inputs_dir = paths.app_dir / "inputs"
    inputs_dir.mkdir(parents=True)
    artifact = inputs_dir / "cv.docx"
    artifact.write_bytes(b"PK\x03\x04docx")
    approval = inputs_dir / "approved.json"
    approval_payload = {
        "application_id": "app-a",
        "approved_for_delivery": True,
        "artifact_path": str(artifact),
        "artifact_sha256": __import__("hashlib").sha256(artifact.read_bytes()).hexdigest(),
    }
    approval.write_text(json.dumps(approval_payload), encoding="utf-8")
    from career.cells.handlers import CellExecutionContext

    context = CellExecutionContext(
        application_id="app-a",
        run_id="run-a",
        node_id="deliver_cv",
        attempt=1,
        paths=paths,
        manifest_path=staging.parent / "manifest.json",
        staging_dir=staging,
        inputs={
            "cv.docx": {
                "path": str(artifact),
                "sha256": approval_payload["artifact_sha256"],
            },
            "approved_cv_manifest.json": {
                "path": str(approval),
                "sha256": __import__("hashlib").sha256(approval.read_bytes()).hexdigest(),
            },
        },
        output_paths=(),
        capabilities=CapabilitySet(
            application_root=paths.app_dir,
            read_paths=[paths.app_dir],
            write_paths=[staging, receipts],
        ),
        repair_scope="test",
    )
    adapter = CanonicalDeliveryCellAdapter(env={})
    monkeypatch.setattr(adapter, "preflight", lambda: ("onedrive", "01_armel/Curriculos/personalizados"))
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(list(command))
        report_path = Path(command[command.index("--report") + 1])
        write_json(report_path, {"status": "delivered", "destination": "remote:cv.docx"})
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "delivered", "destination": "remote:cv.docx"}),
            stderr="",
        )

    monkeypatch.setattr("career.services.delivery.subprocess.run", fake_run)
    output = production_handler_registry(delivery_client=adapter)["deliver_cv"](context)

    receipt = json.loads(output.artifacts["cv_delivery_receipt.json"])
    scoped_report = Path(receipt["delivery_report_path"])
    assert scoped_report.is_relative_to(staging)
    command = commands[0]
    assert command[command.index("--report") + 1] == str(scoped_report)
    assert "outputs/_tmp/delivery_report.json" not in " ".join(command)


def test_delivery_cli_requires_explicit_report(tmp_path):
    global_report = ROOT / "outputs/_tmp/delivery_report.json"
    before = global_report.read_bytes() if global_report.is_file() else None
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/deliver_artifact.py"),
            "--file",
            str(tmp_path / "cv.docx"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--report" in result.stderr
    after = global_report.read_bytes() if global_report.is_file() else None
    assert after == before
