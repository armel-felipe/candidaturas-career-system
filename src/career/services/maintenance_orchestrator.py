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
    apply_maintenance_patch,
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

    def __init__(self, root: Path, runner: Any | None = None) -> None:
        self.root = Path(root)
        self.runner = runner

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
                    + self._reviewer_feedback_instruction(request)
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

    @staticmethod
    def _reviewer_feedback_instruction(request: dict[str, Any]) -> str:
        feedback = request.get("reviewer_feedback")
        if not isinstance(feedback, list) or not feedback:
            return ""
        blockers = [str(blocker).strip() for blocker in feedback if str(blocker).strip()]
        if not blockers:
            return ""
        return " Corrija os blockers do revisor anterior: " + "; ".join(blockers)

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
            path_policy = (
                {"status": "ok", "paths": []}
                if not changed_files
                else validate_maintenance_paths(worktree, changed_files)
            )
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
        configured_command = runner_config.get("command")
        if configured_command is None:
            configured_command = "codex"
        if not isinstance(configured_command, str) or configured_command not in {"codex", "codex.exe"}:
            return {"status": "rejected", "blocker_reason": "reviewer_executable_not_trusted"}
        trusted_codex = shutil.which("codex")
        resolved_command = shutil.which(configured_command)
        if not trusted_codex or not resolved_command:
            return {"status": "rejected", "blocker_reason": "reviewer_executable_not_trusted"}
        if os.path.realpath(resolved_command) != os.path.realpath(trusted_codex):
            return {"status": "rejected", "blocker_reason": "reviewer_executable_not_trusted"}
        runner_config = {**runner_config, "command": configured_command}

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

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def _maintenance_state_dir(self) -> Path:
        return self.root / _WORKTREE_METADATA_PREFIX

    def _attempt_dir(self, request: dict[str, Any], attempt_number: int) -> Path:
        return self._maintenance_state_dir() / "attempts" / str(request["request_id"]) / str(attempt_number)

    def _persisted_attempts(self, request: dict[str, Any]) -> int:
        attempts_dir = self._maintenance_state_dir() / "attempts" / str(request["request_id"])
        if not attempts_dir.is_dir():
            return 0
        attempt_numbers = [
            int(path.name)
            for path in attempts_dir.iterdir()
            if path.is_dir() and path.name.isdecimal() and (path / "manifest.json").is_file()
        ]
        return max(attempt_numbers, default=0)

    def _persist_attempt(
        self,
        request: dict[str, Any],
        attempt_number: int,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        attempt_dir = self._attempt_dir(request, attempt_number)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        spec = request.get("spec") if isinstance(request.get("spec"), dict) else {}
        candidate = result.get("candidate") if isinstance(result.get("candidate"), dict) else {}
        patch_path = Path(str(candidate.get("patch_path", ""))) if candidate.get("patch_path") else None
        diff_bytes = patch_path.read_bytes() if patch_path and patch_path.is_file() else b""
        checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
        review = result.get("review") if isinstance(result.get("review"), dict) else {}
        manifest = {
            "request_id": request["request_id"],
            "request_fingerprint": request["request_fingerprint"],
            "attempt": attempt_number,
            "status": result.get("status", "rejected"),
            "spec_sha256": self._sha256_bytes(self._json_bytes(spec)),
            "diff_sha256": self._sha256_bytes(diff_bytes),
            "checks": checks,
            "review": review,
            "changed_files": candidate.get("changed_files", []),
            "blocker_reason": result.get("blocker_reason"),
            "completed_at": self._now(),
        }
        self._write_json(attempt_dir / "checks.json", checks)
        self._write_json(attempt_dir / "review.json", review)
        self._write_json(attempt_dir / "manifest.json", manifest)
        return {**result, "attempt": attempt_number, "attempt_path": str(attempt_dir), "manifest": manifest}

    def _run_injected_attempt(
        self, request: dict[str, Any], attempt_number: int
    ) -> dict[str, Any]:
        handler = getattr(self.runner, "run_attempt", None)
        if not callable(handler):
            return {
                "status": "rejected",
                "blocker_reason": "maintenance_runner_contract_invalid",
                "checks": {},
                "review": {},
            }
        result = handler(request, attempt_number)
        if not isinstance(result, dict):
            return {
                "status": "rejected",
                "blocker_reason": "maintenance_runner_result_invalid",
                "checks": {},
                "review": {},
            }
        return result

    def _process_real_attempt(self, request: dict[str, Any], attempt_number: int) -> dict[str, Any]:
        base_commit = str(request["base_commit"])
        worktree = self._create_worktree(base_commit)
        try:
            workspace_request = self._copy_request(worktree, request)
            agent_result = self._run_maintenance_agent(
                worktree,
                {**request, "workspace_request_path": str(workspace_request)},
            )
            if agent_result.get("status") != "completed":
                return {
                    "status": "rejected",
                    "blocker_reason": "maintenance_agent_failed",
                    "agent": agent_result,
                    "checks": {},
                    "review": {},
                }

            candidate = self._collect_candidate(worktree, base_commit, list(request["allowed_paths"]))
            if candidate.get("status") != "candidate_ready":
                return {
                    "status": "rejected",
                    "blocker_reason": candidate.get("blocker_reason", "candidate_rejected"),
                    "candidate": candidate,
                    "checks": {},
                    "review": {},
                }

            attempt_dir = self._attempt_dir(request, attempt_number)
            attempt_dir.mkdir(parents=True, exist_ok=True)
            patch_path = attempt_dir / "candidate.patch"
            patch_path.write_text(str(candidate["diff"]), encoding="utf-8")
            candidate = {
                **candidate,
                "patch_path": str(patch_path),
            }
            checks = self._run_deterministic_checks(worktree, request, patch_path)
            review = self._run_reviewer(attempt_dir / "review", request, patch_path, checks)
            decision = self._approval_decision(
                review=review,
                checks=checks,
                diff_sha256=self._sha256_bytes(patch_path.read_bytes()),
                spec_sha256=self._sha256_bytes(self._json_bytes(request["spec"])),
            )
            return {
                "status": decision["status"],
                "blocker_reason": decision.get("blocker_reason"),
                "candidate": candidate,
                "checks": checks,
                "review": review,
                "agent": agent_result,
            }
        finally:
            self._remove_worktree(worktree)

    def _process_attempt(self, request: dict[str, Any], attempt_number: int) -> dict[str, Any]:
        """Produce and review one isolated candidate, retaining its evidence before retrying."""
        result = (
            self._run_injected_attempt(request, attempt_number)
            if self.runner is not None
            else self._process_real_attempt(request, attempt_number)
        )
        if result.get("status") == "approved":
            candidate = result.get("candidate")
            review = result.get("review")
            checks = result.get("checks")
            patch_value = candidate.get("patch_path") if isinstance(candidate, dict) else None
            patch_path = Path(str(patch_value)) if patch_value else None
            if not patch_path or not patch_path.is_file():
                result = {**result, "status": "rejected", "blocker_reason": "candidate_patch_missing"}
            elif not isinstance(review, dict) or not isinstance(checks, dict):
                result = {**result, "status": "rejected", "blocker_reason": "reviewer_rejected"}
            else:
                decision = self._approval_decision(
                    review=review,
                    checks=checks,
                    diff_sha256=self._sha256_bytes(patch_path.read_bytes()),
                    spec_sha256=self._sha256_bytes(self._json_bytes(request["spec"])),
                )
                if decision["status"] != "approved":
                    result = {
                        **result,
                        "status": "rejected",
                        "blocker_reason": decision["blocker_reason"],
                    }
        return self._persist_attempt(request, attempt_number, result)

    def _tracked_checkout_is_clean(self) -> bool:
        for command in (
            ["git", "diff", "--quiet", "HEAD", "--"],
            ["git", "diff", "--cached", "--quiet", "--"],
        ):
            result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
            if result.returncode != 0:
                return False
        return True

    def _run_post_apply_checks(self, request: dict[str, Any], patch_path: Path) -> dict[str, Any]:
        if self.runner is not None:
            handler = getattr(self.runner, "post_apply_checks", None)
            if callable(handler):
                result = handler(request, patch_path)
                if isinstance(result, dict):
                    return result
        return self._run_deterministic_checks(self.root, request, patch_path)

    def _restore_inverse_patch(self, patch_path: Path, paths: list[str]) -> dict[str, Any]:
        result = subprocess.run(
            ["git", "-C", str(self.root), "apply", "--reverse", str(patch_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            return {
                "status": "restore_failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        unstage = subprocess.run(
            ["git", "-C", str(self.root), "reset", "--", *paths],
            capture_output=True,
            text=True,
        )
        return {
            "status": "restored" if unstage.returncode == 0 else "restore_failed",
            "stdout": result.stdout + unstage.stdout,
            "stderr": result.stderr + unstage.stderr,
        }

    def _apply_and_commit(
        self,
        candidate: dict[str, Any],
        request: dict[str, Any],
        review: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply exactly one approved patch and commit only after post-apply hard gates pass."""
        patch_value = candidate.get("patch_path")
        patch_path = Path(str(patch_value)) if patch_value else None
        if patch_path is None or not patch_path.is_file():
            return {"status": "blocked", "blocker_reason": "candidate_patch_missing"}
        head = self._command_result(["git", "rev-parse", "HEAD"], cwd=self.root)
        if head["returncode"] != 0 or head["stdout"].strip() != str(request["base_commit"]):
            return {"status": "blocked", "blocker_reason": "canonical_base_commit_mismatch"}
        if not self._tracked_checkout_is_clean():
            return {"status": "blocked", "blocker_reason": "canonical_checkout_not_clean"}

        request_path = Path(str(request["request_path"]))
        try:
            dry_run = apply_maintenance_patch(
                root=self.root,
                patch_path=patch_path,
                request_path=request_path,
                apply=False,
            )
            apply_maintenance_patch(
                root=self.root,
                patch_path=patch_path,
                request_path=request_path,
                apply=True,
            )
        except ValueError as exc:
            return {"status": "blocked", "blocker_reason": f"canonical_apply_rejected: {exc}"}

        post_apply_checks = self._run_post_apply_checks(request, patch_path)
        if not self._checks_passed(post_apply_checks):
            restore = self._restore_inverse_patch(patch_path, list(request["allowed_paths"]))
            blocker = "post_apply_checks_failed"
            if restore["status"] != "restored":
                blocker = "post_apply_checks_failed_restore_failed"
            return {
                "status": "blocked",
                "blocker_reason": blocker,
                "checks": post_apply_checks,
                "restore": restore,
                "dry_run": dry_run,
            }

        staged = self._command_result(
            ["git", "add", "-A", "--", *list(request["allowed_paths"])], cwd=self.root
        )
        if staged["returncode"] != 0:
            self._restore_inverse_patch(patch_path, list(request["allowed_paths"]))
            return {"status": "blocked", "blocker_reason": "canonical_stage_failed", "checks": post_apply_checks}
        staged_paths = self._command_result(
            ["git", "diff", "--cached", "--name-only", "--"], cwd=self.root
        )
        allowed_paths = set(request["allowed_paths"])
        committed_paths = {path for path in staged_paths["stdout"].splitlines() if path}
        if staged_paths["returncode"] != 0 or not committed_paths or not committed_paths.issubset(allowed_paths):
            self._restore_inverse_patch(patch_path, list(request["allowed_paths"]))
            return {"status": "blocked", "blocker_reason": "canonical_stage_scope_invalid", "checks": post_apply_checks}
        message = f"maintenance({request['request_id']}): {request['objective']} [{request['roadmap_id']}]"
        commit = self._command_result(["git", "commit", "-m", message], cwd=self.root)
        if commit["returncode"] != 0:
            self._restore_inverse_patch(patch_path, list(request["allowed_paths"]))
            return {"status": "blocked", "blocker_reason": "canonical_commit_failed", "checks": post_apply_checks}
        commit_id = self._command_result(["git", "rev-parse", "HEAD"], cwd=self.root)
        return {
            "status": "committed",
            "commit": commit_id["stdout"].strip(),
            "changed_files": sorted(committed_paths),
            "checks": post_apply_checks,
            "review": review,
            "dry_run": dry_run,
        }

    def _completed_receipt(self, request: dict[str, Any]) -> dict[str, Any] | None:
        if request.get("status") in {"committed", "resumed"}:
            return {"receipt_path": request.get("receipt_path")}
        receipts_dir = self._maintenance_state_dir() / "receipts"
        if not receipts_dir.is_dir():
            return None
        for receipt_path in receipts_dir.glob("*.json"):
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                receipt.get("request_fingerprint") == request.get("request_fingerprint")
                and receipt.get("status") in {"committed", "resumed"}
            ):
                return {"receipt_path": str(receipt_path)}
        return None

    def _update_request_state(
        self,
        request: dict[str, Any],
        *,
        status: str,
        attempts: int,
        blocker_reason: str | None = None,
        receipt_path: Path | None = None,
    ) -> None:
        request_path = Path(str(request["request_path"]))
        persisted = json.loads(request_path.read_text(encoding="utf-8"))
        persisted.update(
            {
                "status": status,
                "attempts": attempts,
                "blocker_reason": blocker_reason,
            }
        )
        if status == "committed":
            persisted["committed_at"] = self._now()
        if receipt_path is not None:
            persisted["receipt_path"] = str(receipt_path)
        self._write_json(request_path, persisted)

    def _write_receipt(self, request: dict[str, Any], result: dict[str, Any]) -> Path:
        """Persist the immutable execution summary outside the candidate diff and checkout index."""
        receipt_path = self._maintenance_state_dir() / "receipts" / f"{request['request_id']}.json"
        attempt_manifest: dict[str, Any] = {}
        attempts = result.get("attempts", 0)
        if isinstance(attempts, int) and attempts > 0:
            manifest_path = self._attempt_dir(request, attempts) / "manifest.json"
            try:
                attempt_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                attempt_manifest = {}
        receipt = {
            "request_id": request["request_id"],
            "request_fingerprint": request["request_fingerprint"],
            "requester_profile": request.get("requester_profile"),
            "application_id": request.get("application_id"),
            "run_id": request.get("run_id"),
            "roadmap_id": request.get("roadmap_id"),
            "base_commit": request.get("base_commit"),
            "allowed_paths": request.get("allowed_paths", []),
            "status": result.get("status"),
            "attempts": result.get("attempts", 0),
            "blocker_reason": result.get("blocker_reason"),
            "commit": result.get("commit"),
            "spec_sha256": attempt_manifest.get(
                "spec_sha256", self._sha256_bytes(self._json_bytes(request.get("spec", {})))
            ),
            "diff_sha256": attempt_manifest.get("diff_sha256", self._sha256_bytes(b"")),
            "changed_files": result.get("changed_files", attempt_manifest.get("changed_files", [])),
            "checks": result.get("checks", {}),
            "review": result.get("review", {}),
            "completed_at": self._now(),
        }
        self._write_json(receipt_path, receipt)
        return receipt_path

    @staticmethod
    def _reviewer_blockers(result: dict[str, Any]) -> list[str]:
        review = result.get("review")
        if isinstance(review, dict) and isinstance(review.get("blockers"), list):
            blockers = [str(value).strip() for value in review["blockers"] if str(value).strip()]
            if blockers:
                return blockers
        blocker_reason = result.get("blocker_reason")
        return [str(blocker_reason)] if isinstance(blocker_reason, str) and blocker_reason else []

    def process(
        self,
        request_path: Path,
        *,
        max_attempts: int = 3,
        maintenance_config: dict[str, Any] | None = None,
        reviewer_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process one validated request with at most three persisted executor/reviewer attempts."""
        del maintenance_config, reviewer_config
        request_path = Path(request_path)
        try:
            validate_maintenance_request(self.root, request_path)
            request = json.loads(request_path.read_text(encoding="utf-8"))
            path_policy = validate_maintenance_paths(self.root, list(request["allowed_paths"]))
            if path_policy["status"] != "ok":
                raise ValueError(str(path_policy.get("blocker", "maintenance_path_policy_blocked")))
            request["allowed_paths"] = list(path_policy["paths"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"status": "blocked", "attempts": 0, "blocker_reason": str(exc)}

        already_completed = self._completed_receipt(request)
        if already_completed is not None:
            return {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": 0,
                "blocker_reason": "request_fingerprint_already_completed",
                "receipt_path": already_completed.get("receipt_path"),
            }
        head = self._command_result(["git", "rev-parse", "HEAD"], cwd=self.root)
        if head["returncode"] != 0 or head["stdout"].strip() != str(request["base_commit"]):
            result = {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": 0,
                "blocker_reason": "canonical_base_commit_mismatch",
            }
            receipt_path = self._write_receipt(request, result)
            self._update_request_state(request, status="blocked", attempts=0, blocker_reason=result["blocker_reason"], receipt_path=receipt_path)
            return {**result, "receipt_path": str(receipt_path)}
        if not self._tracked_checkout_is_clean():
            result = {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": 0,
                "blocker_reason": "canonical_checkout_not_clean",
            }
            receipt_path = self._write_receipt(request, result)
            self._update_request_state(request, status="blocked", attempts=0, blocker_reason=result["blocker_reason"], receipt_path=receipt_path)
            return {**result, "receipt_path": str(receipt_path)}

        persisted_attempts = self._persisted_attempts(request)
        if persisted_attempts >= 3:
            result = {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": persisted_attempts,
                "blocker_reason": "maintenance_retry_limit_reached",
            }
            receipt_path = self._write_receipt(request, result)
            self._update_request_state(
                request,
                status="blocked",
                attempts=persisted_attempts,
                blocker_reason=result["blocker_reason"],
                receipt_path=receipt_path,
            )
            return {**result, "receipt_path": str(receipt_path)}
        attempts_limit = min(max(1, int(max_attempts)), 3 - persisted_attempts)
        feedback: list[str] = []
        final_result: dict[str, Any] = {}
        for attempt_number in range(persisted_attempts + 1, persisted_attempts + attempts_limit + 1):
            attempt_request = {**request, "reviewer_feedback": feedback}
            attempt_result = self._process_attempt(attempt_request, attempt_number)
            if attempt_result.get("status") == "approved":
                candidate = attempt_result.get("candidate")
                review = attempt_result.get("review")
                if isinstance(candidate, dict) and isinstance(review, dict):
                    applied = self._apply_and_commit(candidate, request, review)
                    final_result = {
                        **applied,
                        "request_id": request["request_id"],
                        "attempts": attempt_number,
                        "review": review,
                    }
                    break
                final_result = {
                    "status": "blocked",
                    "request_id": request["request_id"],
                    "attempts": attempt_number,
                    "blocker_reason": "approved_attempt_missing_candidate_or_review",
                }
                break
            feedback = self._reviewer_blockers(attempt_result)
            final_result = {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": attempt_number,
                "blocker_reason": attempt_result.get("blocker_reason", "reviewer_rejected"),
                "checks": attempt_result.get("checks", {}),
                "review": attempt_result.get("review", {}),
            }

        if not final_result:
            final_result = {
                "status": "blocked",
                "request_id": request["request_id"],
                "attempts": 0,
                "blocker_reason": "maintenance_attempts_not_started",
            }
        receipt_path = self._write_receipt(request, final_result)
        self._update_request_state(
            request,
            status=str(final_result["status"]),
            attempts=int(final_result["attempts"]),
            blocker_reason=final_result.get("blocker_reason"),
            receipt_path=receipt_path,
        )
        return {**final_result, "receipt_path": str(receipt_path)}

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
