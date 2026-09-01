from __future__ import annotations

from pathlib import Path

from career.services.maintenance import create_maintenance_request
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
