from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTAINER_HERMES_BINARY = Path("/opt/hermes/bin/hermes")


def resolve_hermes_command(root: Path) -> tuple[list[str], Path | None]:
    """Resolve the Hermes launcher and identify a workspace-local binary."""
    if CONTAINER_HERMES_BINARY.is_file():
        return [str(CONTAINER_HERMES_BINARY)], None
    found = shutil.which("hermes")
    if found:
        return [found], None
    local_binary = root / "hermes-src" / "hermes"
    if not local_binary.is_file():
        return ["hermes"], None
    local_python = local_binary.parent / "venv" / "bin" / "python"
    interpreter = local_python if local_python.is_file() else Path(sys.executable)
    return [str(interpreter), str(local_binary)], local_binary


@dataclass(frozen=True)
class AgentRunRequest:
    stage: str
    record_key: str
    request_path: Path
    instruction: str
    runner_config: dict[str, Any]
    model: str = ""
    variant: str = ""
    profile_name: str = ""
    read_only: bool = False


@dataclass(frozen=True)
class AgentRunResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class SubprocessAgentRunner:
    """Starts one fresh harness process for a single, file-scoped agent task."""

    def __init__(self, root: Path):
        self.root = root

    def build_command(self, request: AgentRunRequest) -> list[str]:
        command_name = str(request.runner_config.get("command") or "opencode")
        local_hermes_binary: Path | None = None
        if command_name == "hermes":
            hermes_command, local_hermes_binary = resolve_hermes_command(self.root)
            resolved = hermes_command[-1]
        else:
            resolved = shutil.which(command_name) or shutil.which("opencode.cmd") or command_name
        runner_kind = str(request.runner_config.get("kind") or Path(resolved).name).casefold()

        if runner_kind == "hermes":
            request_rel = request.request_path.relative_to(self.root)
            prompt = f"Leia o arquivo {request_rel}. {request.instruction}"
            if local_hermes_binary is not None:
                command = list(hermes_command)
            else:
                command = [resolved]
            profile_name = str(
                request.profile_name
                or request.runner_config.get("profile_name")
                or os.environ.get("CAREER_HERMES_PROFILE_NAME")
                or ""
            ).strip()
            if profile_name:
                command.extend(["--profile", profile_name])
            command.append("--accept-hooks")
            if request.model:
                command.extend(["--model", request.model])
            command.extend(["-z", prompt])
            return command

        if runner_kind == "codex":
            request_rel = request.request_path.relative_to(self.root)
            prompt = f"Leia o arquivo {request_rel}. {request.instruction}"
            command = [
                resolved,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only" if request.read_only else "workspace-write",
                "-C",
                str(self.root),
            ]
            if request.model:
                command.extend(["--model", request.model])
            command.append(prompt)
            return command

        if runner_kind not in {"opencode", "opencode.cmd"}:
            raise ValueError(
                f"Unsupported agent runner kind {runner_kind!r}. "
                "Use kind=hermes, kind=opencode or kind=codex."
            )

        command = [
            resolved,
            "run",
            "--agent",
            str(request.runner_config.get("agent") or "build"),
            "--file",
            str(request.request_path),
            "--title",
            f"{request.stage.title()} candidatura v2 {request.record_key}",
        ]
        if request.model:
            command.extend(["--model", request.model])
        if request.variant:
            command.extend(["--variant", request.variant])
        command.append(request.instruction)
        return command

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        command = self.build_command(request)
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                env={**os.environ, "CAREER_HARNESS_SUBAGENT": "1"},
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(request.runner_config.get("timeout_minutes") or 90) * 60,
            )
        except subprocess.TimeoutExpired as exc:
            return AgentRunResult(
                command=command,
                returncode=124,
                stdout=str(exc.stdout or ""),
                stderr=f"Agent runner timed out after {request.runner_config.get('timeout_minutes') or 90} minute(s).",
            )
        return AgentRunResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
