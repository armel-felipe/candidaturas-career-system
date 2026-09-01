from __future__ import annotations

import json
import hashlib
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from career import cli
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


def test_cli_process_returns_blocked_receipt_for_invalid_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request_path = tmp_path / "bad.json"
    request_path.write_text("{}\n", encoding="utf-8")

    exit_code = cli.main(["maintenance", "process", "--request", str(request_path)])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_cli_process_uses_public_maintenance_supervisor_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({"kind": "canonical_maintenance"}), encoding="utf-8")
    calls: list[dict[str, object]] = []

    class FakeSupervisor:
        def __init__(self, root: Path) -> None:
            assert root == Path.cwd()

        def process_maintenance_request(self, payload: dict[str, object]) -> dict[str, object]:
            calls.append(payload)
            return {"status": "blocked", "blocker_reason": "test"}

    monkeypatch.setattr(cli, "HarnessSupervisor", FakeSupervisor)

    exit_code = cli.main(["maintenance", "process", "--request", str(request_path)])

    assert exit_code == 1
    assert calls == [{"kind": "canonical_maintenance"}]
    assert json.loads(capsys.readouterr().out)["blocker_reason"] == "test"


def test_successful_skill_change_reloads_both_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "running\n", "")

    monkeypatch.setattr("career.services.maintenance_orchestrator.subprocess.run", fake_run)

    result = MaintenanceOrchestrator(tmp_path).reload_profiles_if_needed(
        changed_paths=[".agents/skills/escrita-humana/SKILL.md"]
    )

    assert result["status"] == "reloaded"
    assert result["command"][-2:] == ["vagas_bot_01", "vagas_bot_02"]
    assert calls[0] == [
        "docker",
        "compose",
        "-f",
        "compose.yaml",
        "up",
        "-d",
        "--force-recreate",
        "vagas_bot_01",
        "vagas_bot_02",
    ]
    assert calls[1][-2:] == ["vagas_bot_01", "vagas_bot_02"]
    assert result["policy"]["runtime_affecting"] is True
    assert result["docker_compose_ps"] == "running\n"


def test_reload_blocks_when_docker_compose_up_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("docker")

    monkeypatch.setattr("career.services.maintenance_orchestrator.subprocess.run", unavailable)

    result = MaintenanceOrchestrator(tmp_path).reload_profiles_if_needed(
        changed_paths=["src/career/services/maintenance_orchestrator.py"]
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "docker_compose_unavailable"
    assert result["docker_compose_ps"] == ""


def test_reload_blocks_when_docker_compose_ps_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def up_then_unavailable(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(command, 0, "up\n", "")
        raise OSError("docker compose ps unavailable")

    monkeypatch.setattr(
        "career.services.maintenance_orchestrator.subprocess.run", up_then_unavailable
    )

    result = MaintenanceOrchestrator(tmp_path).reload_profiles_if_needed(
        changed_paths=["src/career/services/maintenance_orchestrator.py"]
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "docker_compose_unavailable"
    assert result["docker_compose_ps"] == ""


def test_documentation_and_tests_do_not_reload_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("Docker must not run for documentation/test changes")

    monkeypatch.setattr("career.services.maintenance_orchestrator.subprocess.run", unexpected_run)

    result = MaintenanceOrchestrator(tmp_path).reload_profiles_if_needed(
        changed_paths=["docs/maintenance.md", "tests/test_maintenance_orchestrator.py"]
    )

    assert result["status"] == "not_required"
    assert result["policy"]["runtime_affecting"] is False
    assert result["command"] is None
    assert result["docker_compose_ps"] == ""


@pytest.mark.parametrize(
    "changed_path",
    [
        "src/career/services/maintenance_orchestrator.py",
        "hermes-src/agent.py",
        "compose.yaml",
        "hermes/vagas_bot_01/config.yaml",
    ],
)
def test_runtime_and_config_changes_reload_both_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_path: str
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "running\n", "")

    monkeypatch.setattr("career.services.maintenance_orchestrator.subprocess.run", fake_run)

    result = MaintenanceOrchestrator(tmp_path).reload_profiles_if_needed(
        changed_paths=[changed_path]
    )

    assert result["status"] == "reloaded"
    assert result["policy"]["runtime_affecting"] is True
    assert calls[0][-2:] == ["vagas_bot_01", "vagas_bot_02"]


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


def _transaction_request(
    root: Path, *, application_id: str | None = None, run_id: str | None = None
) -> dict[str, object]:
    base_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return create_maintenance_request(
        root,
        objective="Aplicar ajuste canônico testado",
        allowed_paths=["src/career/services/cv_content.py"],
        spec={"requirements": [{"id": "REQ-1", "text": "Aplicar ajuste testado"}]},
        evidence={"error": "falha reproduzível"},
        requester_profile="vagas_bot_01",
        application_id=application_id,
        run_id=run_id,
        base_commit=base_commit,
    )


def _passing_checks() -> dict[str, object]:
    return {
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
        "changed_files": ["src/career/services/cv_content.py"],
    }


class SequencedRunner:
    """Test seam that returns an independently reviewed maintenance outcome per attempt."""

    def __init__(self, root: Path, decisions: list[str], *, bad_review_hash: bool = False) -> None:
        self.root = root
        self.decisions = decisions
        self.bad_review_hash = bad_review_hash
        self.requests: list[dict[str, object]] = []

    def run_attempt(self, request: dict[str, object], attempt_number: int) -> dict[str, object]:
        self.requests.append(dict(request))
        decision = self.decisions[attempt_number - 1]
        if decision == "reject":
            return {
                "status": "rejected",
                "checks": _passing_checks(),
                "review": {
                    "status": "rejected",
                    "blockers": [f"blocker-{attempt_number}"],
                },
                "blocker_reason": "reviewer_rejected",
            }

        patch_path = self.root / ".career-state" / "maintenance" / f"candidate-{attempt_number}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_text = (
            "--- a/src/career/services/cv_content.py\n"
            "+++ b/src/career/services/cv_content.py\n"
            "@@ -1 +1 @@\n"
            "-BASE\n"
            "+CHANGED\n"
        )
        patch_path.write_text(patch_text, encoding="utf-8")
        review = reviewer_payload()
        review["diff_sha256"] = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
        review["spec_sha256"] = hashlib.sha256(
            json.dumps(request["spec"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if self.bad_review_hash:
            review["diff_sha256"] = "0" * 64
        return {
            "status": "approved",
            "candidate": {
                "patch_path": str(patch_path),
                "changed_files": ["src/career/services/cv_content.py"],
            },
            "checks": _passing_checks(),
            "review": review,
        }

    def post_apply_checks(self, request: dict[str, object], patch_path: Path) -> dict[str, object]:
        assert patch_path.is_file()
        return _passing_checks()


class FailingPostApplyRunner(SequencedRunner):
    def post_apply_checks(self, request: dict[str, object], patch_path: Path) -> dict[str, object]:
        assert patch_path.is_file()
        return {
            "status": "failed",
            "commands": [{"name": "post_apply", "returncode": 1}],
        }


def _git_log(root: Path) -> list[str]:
    return subprocess.run(
        ["git", "-C", str(root), "log", "--format=%s", "--reverse"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()


def _stub_successful_profile_reload(
    monkeypatch: pytest.MonkeyPatch, orchestrator: MaintenanceOrchestrator
) -> None:
    monkeypatch.setattr(
        orchestrator,
        "reload_profiles_if_needed",
        lambda changed_paths: {
            "status": "reloaded",
            "policy": {"runtime_affecting": True, "changed_paths": changed_paths},
            "command": ["docker", "compose", "stubbed"],
            "docker_compose_ps": "running\n",
        },
    )


def test_reviewer_feedback_retry_retries_twice_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    runner = SequencedRunner(root, ["reject", "reject", "approve"])
    orchestrator = MaintenanceOrchestrator(root, runner=runner)
    _stub_successful_profile_reload(monkeypatch, orchestrator)

    result = orchestrator.process(Path(str(request["request_path"])))

    assert result["status"] == "committed"
    assert result["attempts"] == 3
    assert runner.requests[1]["reviewer_feedback"] == ["blocker-1"]
    assert runner.requests[2]["reviewer_feedback"] == ["blocker-2"]
    for attempt in (1, 2, 3):
        manifest = root / ".career-state" / "maintenance" / "attempts" / str(request["request_id"]) / str(attempt) / "manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["status"] in {"rejected", "approved"}
        assert len(payload["spec_sha256"]) == 64
        assert len(payload["diff_sha256"]) == 64
        assert "checks" in payload
        assert "review" in payload


def test_retry_limit_blocks_fourth_failure_without_apply(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    runner = SequencedRunner(root, ["reject", "reject", "reject"])

    result = MaintenanceOrchestrator(root, runner=runner).process(Path(str(request["request_path"])))

    assert result["status"] == "blocked"
    assert result["attempts"] == 3
    assert _git_log(root) == ["base"]


def test_retry_limit_is_persisted_across_process_calls(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    runner = SequencedRunner(root, ["reject", "reject", "reject"])
    orchestrator = MaintenanceOrchestrator(root, runner=runner)

    first = orchestrator.process(Path(str(request["request_path"])), max_attempts=1)
    second = orchestrator.process(Path(str(request["request_path"])), max_attempts=1)
    third = orchestrator.process(Path(str(request["request_path"])), max_attempts=1)
    fourth = MaintenanceOrchestrator(root, runner=SequencedRunner(root, ["approve"])).process(
        Path(str(request["request_path"]))
    )

    assert [first["attempts"], second["attempts"], third["attempts"]] == [1, 2, 3]
    assert fourth["status"] == "blocked"
    assert fourth["attempts"] == 3
    assert _git_log(root) == ["base"]


def test_completed_fingerprint_is_idempotently_refused_without_a_second_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    runner = SequencedRunner(root, ["approve"])
    orchestrator = MaintenanceOrchestrator(root, runner=runner)
    _stub_successful_profile_reload(monkeypatch, orchestrator)

    first = orchestrator.process(Path(str(request["request_path"])))
    second = orchestrator.process(Path(str(request["request_path"])))

    assert first["status"] == "committed"
    assert second["status"] == "blocked"
    assert second["blocker_reason"] == "request_fingerprint_already_completed"
    assert len(_git_log(root)) == 2
    assert _git_log(root)[0] == "base"


def test_successful_commit_contains_request_roadmap_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    runner = SequencedRunner(root, ["approve"])
    orchestrator = MaintenanceOrchestrator(root, runner=runner)
    _stub_successful_profile_reload(monkeypatch, orchestrator)

    result = orchestrator.process(Path(str(request["request_path"])))

    assert result["status"] == "committed"
    assert "maintenance_" in _git_log(root)[-1]
    assert "MAINT-002" in _git_log(root)[-1]
    receipt_path = Path(str(result["receipt_path"]))
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["request_id"] == request["request_id"]
    assert receipt["status"] == "committed"
    assert len(receipt["spec_sha256"]) == 64
    assert len(receipt["diff_sha256"]) == 64
    assert receipt["changed_files"] == ["src/career/services/cv_content.py"]


def test_blocked_reload_prevents_resume_and_blocks_operational_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(
        root, application_id="app_exact", run_id="run_exact"
    )
    orchestrator = MaintenanceOrchestrator(root, runner=SequencedRunner(root, ["approve"]))
    resume_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        orchestrator,
        "reload_profiles_if_needed",
        lambda changed_paths: {
            "status": "blocked",
            "policy": {"runtime_affecting": True, "changed_paths": changed_paths},
            "command": ["docker", "compose"],
            "docker_compose_ps": "",
        },
    )

    def unexpected_resume(request_payload: dict[str, object]) -> dict[str, object]:
        resume_calls.append(request_payload)
        return {"status": "resumed"}

    monkeypatch.setattr(orchestrator, "resume_original_run", unexpected_resume)

    result = orchestrator.process(Path(str(request["request_path"])))

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "profile_reload_blocked"
    assert result["reload"]["status"] == "blocked"
    assert result["resume"]["status"] == "not_requested"
    assert resume_calls == []
    receipt = json.loads(Path(str(result["receipt_path"])).read_text(encoding="utf-8"))
    assert receipt["status"] == "blocked"
    assert receipt["reload"]["status"] == "blocked"
    assert receipt["resume"]["status"] == "not_requested"


def test_blocked_resume_blocks_operational_result_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(
        root, application_id="app_exact", run_id="run_exact"
    )
    orchestrator = MaintenanceOrchestrator(root, runner=SequencedRunner(root, ["approve"]))
    _stub_successful_profile_reload(monkeypatch, orchestrator)
    monkeypatch.setattr(
        orchestrator,
        "resume_original_run",
        lambda request_payload: {
            "status": "blocked",
            "command": ["npm", "run", "applications:run"],
            "returncode": 1,
            "stdout": "",
            "stderr": "resume failed",
        },
    )

    result = orchestrator.process(Path(str(request["request_path"])))

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "original_run_resume_blocked"
    assert result["reload"]["status"] == "reloaded"
    assert result["resume"]["status"] == "blocked"
    receipt = json.loads(Path(str(result["receipt_path"])).read_text(encoding="utf-8"))
    assert receipt["status"] == "blocked"
    assert receipt["resume"]["status"] == "blocked"


def test_injected_approval_with_mismatched_reviewer_hash_is_blocked(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)

    result = MaintenanceOrchestrator(
        root,
        runner=SequencedRunner(root, ["approve", "approve", "approve"], bad_review_hash=True),
    ).process(Path(str(request["request_path"])))

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "reviewer_rejected"
    assert _git_log(root) == ["base"]


def test_failed_commit_restores_worktree_and_index(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)
    subprocess.run(["git", "-C", str(root), "config", "user.name", ""], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", ""], check=True)

    result = MaintenanceOrchestrator(root, runner=SequencedRunner(root, ["approve"])).process(
        Path(str(request["request_path"]))
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "canonical_commit_failed"
    assert (root / "src/career/services/cv_content.py").read_text(encoding="utf-8") == "BASE\n"
    assert subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--quiet", "--"],
        check=False,
    ).returncode == 0


def test_failed_post_apply_checks_remove_applied_at_after_rollback(tmp_path: Path) -> None:
    root = make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )
    request = _transaction_request(root)

    result = MaintenanceOrchestrator(
        root, runner=FailingPostApplyRunner(root, ["approve"])
    ).process(Path(str(request["request_path"])))

    assert result["status"] == "blocked"
    payload = json.loads(Path(str(request["request_path"])).read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert "applied_at" not in payload
