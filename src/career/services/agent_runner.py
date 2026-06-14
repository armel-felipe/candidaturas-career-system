from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentRunRequest:
    stage: str
    record_key: str
    request_path: Path
    instruction: str
    runner_config: dict[str, Any]
    model: str = ""
    variant: str = ""


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
        resolved = shutil.which(command_name) or shutil.which("opencode.cmd") or command_name
        runner_kind = str(request.runner_config.get("kind") or Path(resolved).name).casefold()

        if runner_kind == "hermes":
            request_rel = request.request_path.relative_to(self.root)
            prompt = f"Leia o arquivo {request_rel}. {request.instruction}"
            command = [resolved, "--accept-hooks"]
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
                "workspace-write",
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
