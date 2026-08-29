from __future__ import annotations

import unittest
import os
from pathlib import Path
from unittest import mock

import yaml
from career.services import agent_runner
from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (ROOT / "compose.yaml", ROOT / "app" / "deploy" / "hermes" / "compose.yaml")


class RuntimeMountTests(unittest.TestCase):
    def test_runtime_root_is_traversable_and_context_hook_is_executable(self) -> None:
        # Hermes drops to UID 10000 before invoking tools.  The bind-mounted
        # source tree must therefore be traversable by non-root processes.
        self.assertEqual(ROOT.stat().st_mode & 0o555, 0o555)
        hook = ROOT / "scripts" / "hermes_harness_context_hook.py"
        self.assertEqual(hook.stat().st_mode & 0o111, 0o111)

    def test_canonical_database_honors_runtime_control_db_path(self) -> None:
        from career.services import application_context

        with mock.patch.dict(
            os.environ,
            {"CAREER_CONTROL_DB_PATH": "/workspace/candidaturas/.career-control/career.db"},
            clear=False,
        ):
            database = application_context.canonical_database()
        try:
            self.assertEqual(
                database.db_path,
                Path("/workspace/candidaturas/.career-control/career.db"),
            )
        finally:
            database.close()

    def test_hermes_runner_resolves_absolute_container_binary(self) -> None:
        request = AgentRunRequest(
            stage="fit-map",
            record_key="test-run",
            request_path=ROOT / "README.md",
            instruction="test",
            runner_config={"kind": "hermes", "command": "hermes"},
        )
        with mock.patch.object(agent_runner.shutil, "which", return_value=None), mock.patch.object(
            agent_runner.Path, "is_file", return_value=True
        ):
            command = SubprocessAgentRunner(ROOT).build_command(request)
        self.assertEqual(command[0], "/opt/hermes/bin/hermes")

    def test_hermes_cellular_runner_selects_the_active_profile(self) -> None:
        request = AgentRunRequest(
            stage="analyze",
            record_key="test-run",
            request_path=ROOT / "README.md",
            instruction="test",
            runner_config={"kind": "hermes", "command": "hermes"},
        )
        with mock.patch.dict(
            os.environ, {"CAREER_HERMES_PROFILE_NAME": "vagas_bot_01"}, clear=False
        ), mock.patch.object(agent_runner.shutil, "which", return_value=None), mock.patch.object(
            agent_runner.Path, "is_file", return_value=True
        ):
            command = SubprocessAgentRunner(ROOT).build_command(request)
        self.assertEqual(command[0], "/opt/hermes/bin/hermes")
        self.assertEqual(command[1:3], ["--profile", "vagas_bot_01"])
        self.assertIn("-z", command)

    def test_hermes_cellular_runner_honors_request_profile_over_environment(self) -> None:
        request = AgentRunRequest(
            stage="analyze",
            record_key="test-run",
            request_path=ROOT / "README.md",
            instruction="test",
            runner_config={"kind": "hermes", "command": "hermes"},
            profile_name="vagas_bot_02",
        )
        with mock.patch.dict(
            os.environ, {"CAREER_HERMES_PROFILE_NAME": "vagas_bot_01"}, clear=False
        ), mock.patch.object(agent_runner.shutil, "which", return_value=None), mock.patch.object(
            agent_runner.Path, "is_file", return_value=True
        ):
            command = SubprocessAgentRunner(ROOT).build_command(request)
        self.assertEqual(command[1:3], ["--profile", "vagas_bot_02"])

    def test_image_contains_mountpoints_under_read_only_canonical_root(self) -> None:
        dockerfile = (ROOT / "hermes-src" / "Dockerfile").read_text(encoding="utf-8")
        for mountpoint in (
            "/workspace/candidaturas/.career-control",
            "/workspace/candidaturas/.career-state",
            "/workspace/candidaturas/inbox",
            "/workspace/candidaturas/outputs",
        ):
            self.assertIn(mountpoint, dockerfile)

    def test_container_python_launcher_prefers_hermes_virtualenv(self) -> None:
        launcher = (ROOT / "scripts" / "python.sh").read_text(encoding="utf-8")
        self.assertIn('/opt/hermes/.venv/bin/python', launcher)

    def test_bots_mount_canonical_root_and_isolated_writable_overlays(self) -> None:
        for compose_path in COMPOSE_FILES:
            payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
            for bot_id in ("vagas_bot_01", "vagas_bot_02"):
                service = payload["services"][bot_id]
                volumes = [str(item) for item in service.get("volumes", [])]
                self.assertIn(
                    "/opt/agent-projects/candidaturas:/workspace/candidaturas:ro",
                    volumes,
                    compose_path,
                )
                self.assertNotIn(
                    "/opt/agent-projects/candidaturas/app:/workspace/candidaturas:rw",
                    volumes,
                )
                self.assertFalse(any("/app/src:" in item or "/app/scripts:" in item for item in volumes))
                self.assertIn(
                    "/opt/agent-projects/candidaturas/control-plane:/workspace/candidaturas/.career-control:rw",
                    volumes,
                )
                self.assertIn(
                    f"/opt/agent-projects/candidaturas/workspaces/{bot_id}/state:/workspace/candidaturas/.career-state:rw",
                    volumes,
                )
                self.assertIn(
                    f"/opt/agent-projects/candidaturas/workspaces/{bot_id}/outputs:/workspace/candidaturas/outputs:rw",
                    volumes,
                )
                self.assertEqual(service["working_dir"], "/workspace/candidaturas")
                environment = service["environment"]
                self.assertEqual(
                    environment["CAREER_CONTROL_DB_PATH"],
                    "/workspace/candidaturas/.career-control/career.db",
                )
                self.assertTrue(environment["CAREER_CONTROL_DB_ID"])


if __name__ == "__main__":
    unittest.main()
