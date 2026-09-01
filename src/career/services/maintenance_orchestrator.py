from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
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
_REVIEW_FIELDS = frozenset(
    {
        "status",
        "score",
        "requirements",
        "blockers",
        "warnings",
        "reviewer_model",
        "diff_sha256",
        "spec_sha256",
    }
)
_REVIEW_REQUIREMENT_FIELDS = frozenset({"id", "status", "evidence"})
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_REQUIRED_CHECK_NAMES = frozenset(
    {"git_diff_check", "base_commit", "changed_paths", "candidate_diff", "required_pytest"}
)


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

    @staticmethod
    def _sha256_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _json_bytes(payload: Any) -> bytes:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

    @staticmethod
    def _command_result(
        command: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            return {
                "command": command,
                "returncode": 127,
                "stdout": "",
                "stderr": str(exc),
            }
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def _run_deterministic_checks(
        self, worktree: Path, request: dict[str, Any], diff_path: Path
    ) -> dict[str, Any]:
        """Run the non-negotiable checks before an independent review."""
        worktree = Path(worktree)
        commands: list[dict[str, Any]] = []

        diff_check = self._command_result(
            ["git", "diff", "--check", str(request["base_commit"]), "--"], cwd=worktree
        )
        diff_check["name"] = "git_diff_check"
        commands.append(diff_check)

        base_check = self._command_result(["git", "rev-parse", "HEAD"], cwd=worktree)
        base_check["name"] = "base_commit"
        base_check["expected"] = str(request["base_commit"])
        base_check["actual"] = base_check["stdout"].strip()
        if base_check["returncode"] == 0 and base_check["actual"] != base_check["expected"]:
            base_check["returncode"] = 1
            base_check["stderr"] = "worktree HEAD does not match request base_commit"
        commands.append(base_check)

        paths_check = self._command_result(
            ["git", "diff", "--name-only", "-z", str(request["base_commit"]), "--"], cwd=worktree
        )
        paths_check["name"] = "changed_paths"
        changed_files = sorted(
            {
                *{path for path in paths_check["stdout"].split("\0") if path},
                *{
                    path
                    for path in self._untracked_paths(worktree)
                    if path and not path.startswith(_WORKTREE_METADATA_PREFIX)
                },
            }
        )
        paths_check["changed_files"] = changed_files
        if paths_check["returncode"] == 0:
            path_policy = validate_maintenance_paths(worktree, changed_files)
            allowed_policy = validate_maintenance_paths(worktree, list(request["allowed_paths"]))
            paths_check["path_policy"] = path_policy
            paths_check["allowed_policy"] = allowed_policy
            allowed = set(allowed_policy.get("paths", []))
            outside = sorted(set(changed_files) - allowed)
            if path_policy["status"] != "ok" or allowed_policy["status"] != "ok" or outside:
                paths_check["returncode"] = 1
                paths_check["stderr"] = (
                    str(path_policy.get("blocker") or allowed_policy.get("blocker") or "paths_outside_allowlist")
                )
                paths_check["outside_allowlist"] = outside
        commands.append(paths_check)

        diff_file_check = {
            "name": "candidate_diff",
            "command": ["sha256", str(diff_path)],
            "returncode": 0 if diff_path.is_file() else 1,
            "stdout": "",
            "stderr": "" if diff_path.is_file() else "candidate diff is missing",
        }
        if diff_path.is_file():
            diff_file_check["sha256"] = self._sha256_bytes(diff_path.read_bytes())
        commands.append(diff_file_check)

        pythonpath = os.environ.get("PYTHONPATH", "")
        pytest_env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(part for part in ("src", pythonpath) if part),
        }
        tests_check = self._command_result(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_canonical_maintenance.py",
                "tests/test_harness_dispatch.py",
            ],
            cwd=worktree,
            env=pytest_env,
        )
        tests_check["name"] = "required_pytest"
        commands.append(tests_check)

        return {
            "status": "passed" if all(command["returncode"] == 0 for command in commands) else "failed",
            "commands": commands,
            "changed_files": changed_files,
        }

    def _run_reviewer(
        self,
        review_input_dir: Path,
        request: dict[str, Any],
        diff_path: Path,
        checks: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a separate, read-only reviewer over a sealed review input bundle."""
        if not self._checks_passed(checks):
            return {"status": "rejected", "blocker_reason": "deterministic_checks_failed"}

        runner_config = request.get("reviewer_config")
        if not isinstance(runner_config, dict):
            runner_config = {"kind": "codex", "command": "codex"}
        runner_kind = str(
            runner_config.get("kind")
            or Path(str(runner_config.get("command") or "opencode")).name
        ).casefold()
        configured_sandbox = str(runner_config.get("sandbox") or "").casefold()
        if runner_kind != "codex" or (configured_sandbox and configured_sandbox != "read-only"):
            return {"status": "rejected", "blocker_reason": "reviewer_runner_must_be_read_only"}

        review_input_dir = Path(review_input_dir)
        review_input_dir.mkdir(parents=True, exist_ok=True)
        spec = request.get("spec")
        if not isinstance(spec, dict) or not isinstance(spec.get("requirements"), list):
            return {"status": "rejected", "blocker_reason": "reviewer_spec_invalid"}
        if not diff_path.is_file():
            return {"status": "rejected", "blocker_reason": "candidate_diff_missing"}

        spec_bytes = self._json_bytes(spec)
        diff_bytes = diff_path.read_bytes()
        changed_files = checks.get("changed_files", [])
        if not isinstance(changed_files, list) or not all(isinstance(path, str) for path in changed_files):
            return {"status": "rejected", "blocker_reason": "changed_files_invalid"}
        hashes = {
            "diff_sha256": self._sha256_bytes(diff_bytes),
            "spec_sha256": self._sha256_bytes(spec_bytes),
        }
        bundle = {
            "spec.json": spec_bytes,
            "candidate.diff": diff_bytes,
            "changed_files.json": self._json_bytes(changed_files),
            "checks.json": self._json_bytes(checks),
            "hashes.json": self._json_bytes(hashes),
            "review_request.json": self._json_bytes(
                {
                    "request_id": request["request_id"],
                    "required_contract_fields": sorted(_REVIEW_FIELDS),
                    "input_files": [
                        "spec.json",
                        "candidate.diff",
                        "changed_files.json",
                        "checks.json",
                        "hashes.json",
                    ],
                }
            ),
        }
        for filename, payload in bundle.items():
            path = review_input_dir / filename
            path.write_bytes(payload)
            path.chmod(0o444)
        review_input_dir.chmod(0o555)

        runner = SubprocessAgentRunner(review_input_dir)
        runner_result = runner.run(
            AgentRunRequest(
                stage="maintenance_review",
                record_key=str(request["request_id"]),
                request_path=review_input_dir / "review_request.json",
                instruction=(
                    "Revise os artefatos de entrada em modo somente leitura e responda exclusivamente "
                    "com o JSON do contrato de revisão solicitado."
                ),
                runner_config=runner_config,
                read_only=True,
            )
        )
        if runner_result.returncode != 0:
            return {
                "status": "rejected",
                "blocker_reason": "reviewer_runner_failed",
                "returncode": runner_result.returncode,
                "stdout": runner_result.stdout,
                "stderr": runner_result.stderr,
            }
        try:
            review = json.loads(runner_result.stdout)
        except json.JSONDecodeError:
            return {"status": "rejected", "blocker_reason": "reviewer_json_invalid"}
        if not isinstance(review, dict):
            return {"status": "rejected", "blocker_reason": "reviewer_contract_invalid"}

        requirement_ids = {
            str(requirement.get("id", ""))
            for requirement in spec["requirements"]
            if isinstance(requirement, dict)
        }
        review_ids = {
            str(requirement.get("id", ""))
            for requirement in review.get("requirements", [])
            if isinstance(requirement, dict)
        }
        if requirement_ids != review_ids or not self._accept_review(
            review, diff_sha256=hashes["diff_sha256"], spec_sha256=hashes["spec_sha256"]
        ):
            return {"status": "rejected", "blocker_reason": "reviewer_contract_invalid", "review": review}
        return review

    def _accept_review(self, review: dict[str, Any], *, diff_sha256: str, spec_sha256: str) -> bool:
        """Accept only a complete, exact review contract at the 99/100 boundary."""
        if set(review) != _REVIEW_FIELDS:
            return False
        if review.get("status") != "approved":
            return False
        score = review.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score < 99.0
        ):
            return False
        if review.get("blockers") != [] or not isinstance(review.get("warnings"), list):
            return False
        if not isinstance(review.get("reviewer_model"), str) or not review["reviewer_model"].strip():
            return False
        if review.get("diff_sha256") != diff_sha256 or review.get("spec_sha256") != spec_sha256:
            return False
        if not isinstance(diff_sha256, str) or not isinstance(spec_sha256, str):
            return False
        if not _SHA256_RE.fullmatch(diff_sha256) or not _SHA256_RE.fullmatch(spec_sha256):
            return False
        requirements = review.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            return False
        for requirement in requirements:
            if not isinstance(requirement, dict) or set(requirement) != _REVIEW_REQUIREMENT_FIELDS:
                return False
            if not isinstance(requirement["id"], str) or not requirement["id"].strip():
                return False
            if requirement["status"] != "met":
                return False
            if not isinstance(requirement["evidence"], str) or not requirement["evidence"].strip():
                return False
        return True

    def _approval_decision(
        self,
        *,
        review: dict[str, Any],
        checks: dict[str, Any],
        diff_sha256: str | None = None,
        spec_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Combine deterministic gates and the independent review without overrides."""
        if not self._checks_passed(checks):
            return {"status": "rejected", "blocker_reason": "deterministic_checks_failed"}
        expected_diff = diff_sha256 if diff_sha256 is not None else str(review.get("diff_sha256", ""))
        expected_spec = spec_sha256 if spec_sha256 is not None else str(review.get("spec_sha256", ""))
        if not self._accept_review(review, diff_sha256=expected_diff, spec_sha256=expected_spec):
            return {"status": "rejected", "blocker_reason": "reviewer_rejected"}
        return {"status": "approved", "review": review, "checks": checks}

    @staticmethod
    def _checks_passed(checks: dict[str, Any]) -> bool:
        commands = checks.get("commands")
        if checks.get("status") != "passed" or not isinstance(commands, list):
            return False
        command_names: set[str] = set()
        for command in commands:
            if not isinstance(command, dict) or command.get("returncode") != 0:
                return False
            name = command.get("name")
            if not isinstance(name, str) or not name:
                return False
            command_names.add(name)
        return _REQUIRED_CHECK_NAMES.issubset(command_names)

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
