from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from career.services.maintenance import create_maintenance_request
from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.maintenance_orchestrator import MaintenanceOrchestrator

from test_canonical_maintenance import make_git_fixture


def make_valid_request(root: Path, *, allowed_paths: list[str]) -> dict[str, object]:
    return create_maintenance_request(
        root,
        objective="Corrigir cláusula canônica",
        allowed_paths=allowed_paths,
        spec={"requirements": [{"id": "REQ-1", "text": "Alterar apenas o arquivo permitido"}]},
        evidence={"error": "reprodução local"},
        requester_profile="vagas_bot_01",
        base_commit="fixture-base",
    )


class FakeMaintenanceRunner(MaintenanceOrchestrator):
    def __init__(self, *, extra_file: str | None = None) -> None:
        self.extra_file = extra_file

    def run_in_worktree(self, root: Path, request: dict[str, object]) -> dict[str, object]:
        self.root = root
        return super().run_in_worktree(Path(str(request["request_path"])))

    def _run_maintenance_agent(
        self, worktree: Path, request: dict[str, object]
    ) -> dict[str, object]:
        target = worktree / "src/career/services/cv_content.py"
        target.write_text("CHANGED\n", encoding="utf-8")
        if self.extra_file:
            extra = worktree / self.extra_file
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("forbidden\n", encoding="utf-8")
        return {"status": "completed"}


class PreflightProbe(MaintenanceOrchestrator):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.worktree_calls = 0
        self.agent_calls = 0

    def _create_worktree(self, base_commit: str) -> Path:
        self.worktree_calls += 1
        return super()._create_worktree(base_commit)

    def _run_maintenance_agent(
        self, worktree: Path, request: dict[str, object]
    ) -> dict[str, object]:
        self.agent_calls += 1
        return {"status": "completed"}


def test_maintenance_agent_writes_only_inside_temporary_worktree(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = make_valid_request(root, allowed_paths=["src/career/services/cv_content.py"])

    result = FakeMaintenanceRunner().run_in_worktree(root, request)

    assert result["status"] == "candidate_ready"
    assert result["worktree"] != str(root)
    assert (root / "src/career/services/cv_content.py").read_text(encoding="utf-8") == "BASE\n"
    assert result["changed_files"] == ["src/career/services/cv_content.py"]


def test_candidate_rejects_new_file_outside_allowlist(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = make_valid_request(root, allowed_paths=["src/career/services/cv_content.py"])

    result = FakeMaintenanceRunner(extra_file="outputs/forbidden.txt").run_in_worktree(root, request)

    assert result["status"] == "rejected"
    assert "outputs/forbidden.txt" in str(result["blocker_reason"])


def test_candidate_diff_includes_allowlisted_new_file(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = make_valid_request(
        root,
        allowed_paths=[
            "src/career/services/cv_content.py",
            "src/career/services/new_clause.py",
        ],
    )

    result = FakeMaintenanceRunner(extra_file="src/career/services/new_clause.py").run_in_worktree(
        root, request
    )

    assert result["status"] == "candidate_ready"
    assert "diff --git a/src/career/services/new_clause.py b/src/career/services/new_clause.py" in str(
        result["diff"]
    )


def test_blocked_allowlist_is_rejected_before_worktree_or_agent(tmp_path: Path) -> None:
    root = make_git_fixture(tmp_path)
    request = make_valid_request(root, allowed_paths=[".agents/skills/new-skill/SKILL.md"])
    orchestrator = PreflightProbe(root)

    result = orchestrator.run_in_worktree(Path(str(request["request_path"])))

    assert result["status"] == "rejected"
    assert "new_skill_forbidden" in str(result["blocker_reason"])
    assert orchestrator.worktree_calls == 0
    assert orchestrator.agent_calls == 0


FIXTURES = Path(__file__).parent / "fixtures"


def reviewer_payload(
    *,
    score: float = 99.0,
    requirements_met: bool = True,
    blockers: list[str] | None = None,
) -> dict[str, object]:
    fixture_name = (
        "maintenance_reviewer_approved.json" if score >= 99.0 else "maintenance_reviewer_rejected.json"
    )
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    payload["score"] = score
    payload["blockers"] = [] if blockers is None else blockers
    if not requirements_met:
        payload["requirements"][0]["status"] = "missing"
    return payload


def test_reviewer_accepts_exactly_99_and_matching_hashes(tmp_path: Path) -> None:
    review = reviewer_payload(score=99.0, requirements_met=True, blockers=[])
    orchestrator = MaintenanceOrchestrator(tmp_path)

    assert orchestrator._accept_review(
        review,
        diff_sha256=str(review["diff_sha256"]),
        spec_sha256=str(review["spec_sha256"]),
    )


def test_reviewer_rejects_98_99_even_without_blockers(tmp_path: Path) -> None:
    review = reviewer_payload(score=98.99, requirements_met=True, blockers=[])
    orchestrator = MaintenanceOrchestrator(tmp_path)

    assert not orchestrator._accept_review(
        review,
        diff_sha256=str(review["diff_sha256"]),
        spec_sha256=str(review["spec_sha256"]),
    )


def test_reviewer_rejects_non_finite_nan_score(tmp_path: Path) -> None:
    review = reviewer_payload()
    review["score"] = json.loads("NaN")
    orchestrator = MaintenanceOrchestrator(tmp_path)

    assert isinstance(review["score"], float)
    assert math.isnan(review["score"])
    assert not orchestrator._accept_review(
        review,
        diff_sha256=str(review["diff_sha256"]),
        spec_sha256=str(review["spec_sha256"]),
    )


def test_reviewer_rejects_missing_schema_field_and_mismatched_hashes(tmp_path: Path) -> None:
    review = reviewer_payload()
    review.pop("reviewer_model")
    orchestrator = MaintenanceOrchestrator(tmp_path)

    assert not orchestrator._accept_review(
        review,
        diff_sha256="0" * 64,
        spec_sha256=str(review["spec_sha256"]),
    )


def test_hard_gate_rejects_high_score_when_test_failed(tmp_path: Path) -> None:
    checks = {"status": "failed", "commands": [{"returncode": 1}]}
    result = MaintenanceOrchestrator(tmp_path)._approval_decision(
        review=reviewer_payload(score=100.0),
        checks=checks,
    )

    assert result["status"] == "rejected"
    assert result["blocker_reason"] == "deterministic_checks_failed"


def test_hard_gate_rejects_high_score_when_required_check_is_missing(tmp_path: Path) -> None:
    result = MaintenanceOrchestrator(tmp_path)._approval_decision(
        review=reviewer_payload(score=100.0),
        checks={"status": "passed", "commands": [{"name": "required_pytest", "returncode": 0}]},
    )

    assert result["status"] == "rejected"
    assert result["blocker_reason"] == "deterministic_checks_failed"


def test_reviewer_input_is_read_only_and_contains_required_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(tmp_path)
    diff_path = tmp_path.parent / "candidate.patch"
    diff_path.write_bytes(b"diff --git a/src/x.py b/src/x.py\n")
    review_input_dir = tmp_path / "review-input"
    request = make_valid_request(root, allowed_paths=["src/x.py"])
    request["reviewer_config"] = {"kind": "codex", "command": "codex"}
    captured: dict[str, object] = {}

    class FakeReviewerRunner:
        def __init__(self, runner_root: Path) -> None:
            captured["root"] = runner_root

        def run(self, run_request: object) -> object:
            captured["request"] = run_request
            payload = json.loads(
                (FIXTURES / "maintenance_reviewer_approved.json").read_text(encoding="utf-8")
            )
            payload.update(
                json.loads((review_input_dir / "hashes.json").read_text(encoding="utf-8"))
            )
            return type(
                "ReviewResult",
                (),
                {
                    "returncode": 0,
                    "stdout": json.dumps(payload),
                    "stderr": "",
                },
            )()

    monkeypatch.setattr(
        "career.services.maintenance_orchestrator.SubprocessAgentRunner", FakeReviewerRunner
    )
    monkeypatch.setattr(
        "career.services.maintenance_orchestrator.shutil.which",
        lambda command: "/usr/bin/codex",
    )
    checks = {
        "status": "passed",
        "commands": [
            {"name": name, "returncode": 0}
            for name in [
                "git_diff_check",
                "base_commit",
                "changed_paths",
                "candidate_diff",
                "required_pytest",
            ]
        ],
        "changed_files": ["src/x.py"],
    }

    result = MaintenanceOrchestrator(root)._run_reviewer(review_input_dir, request, diff_path, checks)

    assert result["status"] == "approved"
    assert captured["root"] == review_input_dir
    assert captured["request"].read_only is True
    assert (review_input_dir / "spec.json").is_file()
    assert (review_input_dir / "candidate.diff").read_bytes() == diff_path.read_bytes()
    assert json.loads((review_input_dir / "changed_files.json").read_text(encoding="utf-8")) == [
        "src/x.py"
    ]
    assert json.loads((review_input_dir / "checks.json").read_text(encoding="utf-8")) == checks
    hashes = json.loads((review_input_dir / "hashes.json").read_text(encoding="utf-8"))
    assert len(hashes["diff_sha256"]) == 64
    assert len(hashes["spec_sha256"]) == 64
    assert (review_input_dir.stat().st_mode & 0o222) == 0


def test_reviewer_rejects_write_capable_runner_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(tmp_path)
    diff_path = tmp_path.parent / "candidate.patch"
    diff_path.write_bytes(b"diff --git a/src/x.py b/src/x.py\n")
    request = make_valid_request(root, allowed_paths=["src/x.py"])
    request["reviewer_config"] = {
        "kind": "codex",
        "command": "codex",
        "sandbox": "workspace-write",
    }
    checks = {
        "status": "passed",
        "commands": [
            {"name": name, "returncode": 0}
            for name in [
                "git_diff_check",
                "base_commit",
                "changed_paths",
                "candidate_diff",
                "required_pytest",
            ]
        ],
        "changed_files": ["src/x.py"],
    }

    class UnexpectedReviewerRunner:
        def __init__(self, runner_root: Path) -> None:
            raise AssertionError("write-capable reviewer must be rejected before spawning")

    monkeypatch.setattr(
        "career.services.maintenance_orchestrator.SubprocessAgentRunner",
        UnexpectedReviewerRunner,
    )

    result = MaintenanceOrchestrator(root)._run_reviewer(
        tmp_path / "review-input", request, diff_path, checks
    )

    assert result["status"] == "rejected"
    assert result["blocker_reason"] == "reviewer_runner_must_be_read_only"


def test_reviewer_rejects_non_codex_command_before_spawning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(tmp_path)
    diff_path = tmp_path.parent / "candidate.patch"
    diff_path.write_bytes(b"diff --git a/src/x.py b/src/x.py\n")
    request = make_valid_request(root, allowed_paths=["src/x.py"])
    request["reviewer_config"] = {
        "kind": "codex",
        "command": "fake-reviewer",
        "sandbox": "read-only",
    }
    checks = {
        "status": "passed",
        "commands": [
            {"name": name, "returncode": 0}
            for name in [
                "git_diff_check",
                "base_commit",
                "changed_paths",
                "candidate_diff",
                "required_pytest",
            ]
        ],
        "changed_files": ["src/x.py"],
    }

    class UnexpectedReviewerRunner:
        def __init__(self, runner_root: Path) -> None:
            raise AssertionError("untrusted reviewer command must be rejected before spawning")

    monkeypatch.setattr(
        "career.services.maintenance_orchestrator.SubprocessAgentRunner",
        UnexpectedReviewerRunner,
    )

    result = MaintenanceOrchestrator(root)._run_reviewer(
        tmp_path / "review-input", request, diff_path, checks
    )

    assert result["status"] == "rejected"
    assert result["blocker_reason"] == "reviewer_executable_not_trusted"


def test_codex_reviewer_command_uses_read_only_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request = AgentRunRequest(
        stage="maintenance_review",
        record_key="request-1",
        request_path=tmp_path / "review_request.json",
        instruction="review",
        runner_config={"kind": "codex", "command": "codex"},
        read_only=True,
    )
    request.request_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("career.services.agent_runner.shutil.which", lambda _: "/usr/bin/codex")

    command = SubprocessAgentRunner(tmp_path).build_command(request)

    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "workspace-write" not in command


def test_deterministic_checks_pass_in_current_worktree_and_record_portable_pytest_command(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    clean_root = tmp_path / "clean-worktree"
    subprocess.run(["git", "clone", "--no-local", "--quiet", str(root), str(clean_root)], check=True)
    shutil.copy2(
        root / "src/career/services/maintenance_orchestrator.py",
        clean_root / "src/career/services/maintenance_orchestrator.py",
    )
    base_commit = subprocess.run(
        ["git", "-C", str(clean_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    diff_path = tmp_path / "candidate.patch"
    diff_path.write_bytes(b"candidate diff\n")
    request = {
        "base_commit": base_commit,
        "allowed_paths": [
            "src/career/services/maintenance_orchestrator.py",
        ],
        "spec": {"requirements": [{"id": "REQ-1", "text": "checks"}]},
    }

    checks = MaintenanceOrchestrator(clean_root)._run_deterministic_checks(clean_root, request, diff_path)

    assert checks["status"] == "passed"
    pytest_check = next(command for command in checks["commands"] if command["name"] == "required_pytest")
    assert pytest_check["returncode"] == 0
    assert pytest_check["command"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_canonical_maintenance.py",
        "tests/test_harness_dispatch.py",
    ]


def test_deterministic_checks_validate_untracked_changed_paths(tmp_path: Path) -> None:
    root = make_git_fixture(tmp_path, files={"src/existing.py": "BASE\n"})
    base_commit = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        .stdout.strip()
    )
    (root / "src/new_file.py").write_text("NEW\n", encoding="utf-8")
    diff_path = tmp_path.parent / "candidate.patch"
    diff_path.write_bytes(b"diff --git a/src/new_file.py b/src/new_file.py\n")
    request = make_valid_request(root, allowed_paths=["src/new_file.py"])
    request["base_commit"] = base_commit

    checks = MaintenanceOrchestrator(root)._run_deterministic_checks(root, request, diff_path)

    assert checks["changed_files"] == ["src/new_file.py"]
