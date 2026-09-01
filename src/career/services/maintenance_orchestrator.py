from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.maintenance import (
    maintenance_request_fingerprint,
    validate_maintenance_paths,
    validate_maintenance_request,
)


_WORKTREE_METADATA_PREFIX = ".career-state/maintenance/"


class MaintenanceOrchestrator:
    """Runs one maintenance candidate in a disposable Git worktree."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _create_worktree(self, base_commit: str) -> Path:
        worktree = Path(tempfile.mkdtemp(prefix="career-maintenance-worktree-"))
        worktree.rmdir()
        result = subprocess.run(
            ["git", "-C", str(self.root), "worktree", "add", "--detach", str(worktree), base_commit],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"unable to create maintenance worktree: {detail}")
        return worktree

    def _remove_worktree(self, worktree: Path) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), "worktree", "remove", "--force", str(worktree)],
            capture_output=True,
            text=True,
        )
        if worktree.exists():
            shutil.rmtree(worktree)

    def _copy_request(self, worktree: Path, request: dict[str, Any]) -> Path:
        request_id = str(request["request_id"])
        destination = worktree / _WORKTREE_METADATA_PREFIX / "requests" / f"{request_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination

    def _run_maintenance_agent(self, worktree: Path, request: dict[str, Any]) -> dict[str, Any]:
        request_path = Path(str(request["workspace_request_path"]))
        runner_config = request.get("runner_config")
        if not isinstance(runner_config, dict):
            runner_config = {"kind": "opencode"}
        result = SubprocessAgentRunner(worktree).run(
            AgentRunRequest(
                stage="maintenance",
                record_key=str(request["request_id"]),
                request_path=request_path,
                instruction=(
                    "Implemente somente a manutenção solicitada. "
                    "Altere exclusivamente os caminhos permitidos no pedido."
                ),
                runner_config=runner_config,
            )
        )
        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _changed_paths(self, worktree: Path) -> list[str]:
        tracked = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--name-only", "-z", "HEAD", "--"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        untracked_paths = self._untracked_paths(worktree)
        if tracked.returncode:
            detail = (tracked.stderr or tracked.stdout).strip()
            raise RuntimeError(f"unable to collect maintenance changes: {detail}")
        paths = tracked.stdout.split("\0") + untracked_paths
        return sorted(
            {
                path
                for path in paths
                if path and not path.startswith(_WORKTREE_METADATA_PREFIX)
            }
        )

    def _untracked_paths(self, worktree: Path) -> list[str]:
        untracked = subprocess.run(
            [
                "git",
                "-C",
                str(worktree),
                "ls-files",
                "--others",
                "--exclude-standard",
                "--no-directory",
                "-z",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if untracked.returncode:
            detail = (untracked.stderr or untracked.stdout).strip()
            raise RuntimeError(f"unable to collect maintenance changes: {detail}")
        return untracked.stdout.split("\0")

    def _collect_candidate(
        self, worktree: Path, base_commit: str, allowed_paths: list[str]
    ) -> dict[str, Any]:
        request_policy = validate_maintenance_paths(worktree, allowed_paths)
        if request_policy["status"] != "ok":
            return {
                "status": "rejected",
                "changed_files": [],
                "blocker_reason": f"request paths blocked: {request_policy['blocker']}",
            }

        changed_files = self._changed_paths(worktree)
        candidate_policy = validate_maintenance_paths(worktree, changed_files)
        if candidate_policy["status"] != "ok":
            path = candidate_policy.get("path", "")
            return {
                "status": "rejected",
                "changed_files": changed_files,
                "blocker_reason": f"{path}: {candidate_policy['blocker']}",
            }

        allowed = set(request_policy["paths"])
        outside = sorted(set(changed_files) - allowed)
        if outside:
            return {
                "status": "rejected",
                "changed_files": changed_files,
                "blocker_reason": "paths outside maintenance allowlist: " + ", ".join(outside),
            }

        new_paths = [
            path
            for path in self._untracked_paths(worktree)
            if path and not path.startswith(_WORKTREE_METADATA_PREFIX)
        ]
        if new_paths:
            intent_to_add = subprocess.run(
                ["git", "-C", str(worktree), "add", "--intent-to-add", "--", *new_paths],
                capture_output=True,
                text=True,
            )
            if intent_to_add.returncode:
                detail = (intent_to_add.stderr or intent_to_add.stdout).strip()
                return {
                    "status": "rejected",
                    "changed_files": changed_files,
                    "blocker_reason": f"unable to stage candidate files: {detail}",
                }

        diff = subprocess.run(
            [
                "git",
                "-C",
                str(worktree),
                "diff",
                "--binary",
                base_commit,
                "--",
                ".",
                f":(exclude){_WORKTREE_METADATA_PREFIX}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if diff.returncode:
            detail = (diff.stderr or diff.stdout).strip()
            return {
                "status": "rejected",
                "changed_files": changed_files,
                "blocker_reason": f"unable to generate candidate diff: {detail}",
            }
        return {
            "status": "candidate_ready",
            "changed_files": changed_files,
            "diff": diff.stdout,
        }

    def run_in_worktree(self, request_path: Path) -> dict[str, Any]:
        request_path = Path(request_path)
        request_validation = validate_maintenance_request(self.root, request_path)
        path_policy = validate_maintenance_paths(self.root, request_validation["paths"])
        if path_policy["status"] != "ok":
            path = path_policy.get("path", "")
            return {
                "status": "rejected",
                "changed_files": [],
                "blocker_reason": f"{path}: {path_policy['blocker']}",
            }
        normalized_allowed_paths = list(path_policy["paths"])
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["allowed_paths"] = normalized_allowed_paths
        request["request_fingerprint"] = maintenance_request_fingerprint(request)
        base = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        if base.returncode:
            detail = (base.stderr or base.stdout).strip()
            raise RuntimeError(f"unable to resolve maintenance base commit: {detail}")
        base_commit = base.stdout.strip()

        worktree = self._create_worktree(base_commit)
        try:
            workspace_request = self._copy_request(worktree, request)
            run_request = {**request, "workspace_request_path": str(workspace_request)}
            agent_result = self._run_maintenance_agent(worktree, run_request)
            if agent_result.get("status") != "completed":
                return {
                    "status": "rejected",
                    "worktree": str(worktree),
                    "changed_files": [],
                    "blocker_reason": "maintenance agent failed",
                    "agent": agent_result,
                }
            candidate = self._collect_candidate(
                worktree,
                base_commit,
                normalized_allowed_paths,
            )
            return {**candidate, "worktree": str(worktree), "agent": agent_result}
        finally:
            self._remove_worktree(worktree)
