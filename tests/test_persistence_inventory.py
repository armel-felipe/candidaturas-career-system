from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "persistence_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "persistence_inventory", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PersistenceInventoryTests(unittest.TestCase):
    def _build_fixture(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".career-state").mkdir(parents=True, exist_ok=True)
        (root / "app" / ".career-state").mkdir(parents=True, exist_ok=True)
        (root / "app" / "deploy" / "hermes").mkdir(parents=True, exist_ok=True)
        (root / "src" / "career" / "services").mkdir(parents=True, exist_ok=True)
        (root / "app" / "src" / "career" / "services").mkdir(parents=True, exist_ok=True)
        (root / "control-plane").mkdir(parents=True, exist_ok=True)
        (root / ".gitignore").write_text(
            ".career-state/\napp/.career-state/\noutputs/\n",
            encoding="utf-8",
        )

        (root / ".career-state" / "workflow_state.json").write_text(
            json.dumps({"stage": "created"}),
            encoding="utf-8",
        )
        (root / "app" / ".career-state" / "fit_map.json").write_text(
            json.dumps({"empresa": "Conexa"}),
            encoding="utf-8",
        )
        (root / "control-plane" / "authority.json").write_text(
            json.dumps({"control_db_id": "control_123"}),
            encoding="utf-8",
        )
        (root / "src" / "career" / "services" / "example.py").write_text(
            "VALUE = 'root'\n",
            encoding="utf-8",
        )
        (root / "app" / "src" / "career" / "services" / "example.py").write_text(
            "VALUE = 'app'\n",
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text("root agents\n", encoding="utf-8")
        (root / "app" / "AGENTS.md").write_text("app agents\n", encoding="utf-8")
        (root / "app" / "deploy" / "hermes" / "compose.yaml").write_text(
            "\n".join(
                [
                    "services:",
                    "  vagas_bot_01:",
                    "    volumes:",
                    "      - /repo/app:/workspace/candidaturas:rw",
                    "      - /repo/control-plane:/workspace/candidaturas/.career-control:rw",
                    "      - /repo/workspaces/vagas_bot_01/state:/workspace/candidaturas/.career-state:rw",
                    "      - /repo/workspaces/vagas_bot_01/outputs:/workspace/candidaturas/outputs:rw",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_build_inventory_reports_json_domains_divergences_and_hermes_mounts(self):
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"Missing task script at {SCRIPT_PATH}",
        )
        module = load_module()

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self._build_fixture(root)

            inventory = module.build_inventory(root)

        json_files = {entry["path"]: entry for entry in inventory["json_files"]}
        self.assertIn(".career-state/workflow_state.json", json_files)
        self.assertEqual(
            json_files[".career-state/workflow_state.json"]["domain"],
            "root_career_state",
        )
        self.assertIn("app/.career-state/fit_map.json", json_files)
        self.assertEqual(
            json_files["app/.career-state/fit_map.json"]["domain"],
            "app_career_state",
        )
        self.assertIn("control-plane/authority.json", json_files)
        self.assertEqual(
            json_files["control-plane/authority.json"]["domain"],
            "control_plane",
        )

        divergences = {
            entry["canonical_path"]: entry for entry in inventory["root_app_divergences"]
        }
        self.assertIn("AGENTS.md", divergences)
        self.assertIn("src/career/services/example.py", divergences)

        hermes = inventory["hermes"]
        self.assertEqual(hermes["compose_path"], "app/deploy/hermes/compose.yaml")
        service = hermes["services"]["vagas_bot_01"]
        mounts = {mount["target"]: mount for mount in service["mounts"]}
        self.assertIn("/workspace/candidaturas", mounts)
        self.assertEqual(mounts["/workspace/candidaturas"]["classification"], "runtime_code")
        self.assertIn("/workspace/candidaturas/.career-state", mounts)
        self.assertEqual(
            mounts["/workspace/candidaturas/.career-state"]["classification"],
            "bot_state",
        )
        self.assertIn("/workspace/candidaturas/.career-control", mounts)
        self.assertEqual(
            mounts["/workspace/candidaturas/.career-control"]["classification"],
            "control_plane",
        )

    def test_cli_writes_inventory_json_report(self):
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"Missing task script at {SCRIPT_PATH}",
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self._build_fixture(root)
            output_path = root / "outputs" / "_tmp" / "inventory.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--root",
                    str(root),
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertGreaterEqual(payload["summary"]["json_file_count"], 3)
            self.assertGreaterEqual(payload["summary"]["root_app_divergence_count"], 2)

    def test_build_inventory_does_not_modify_migration_runs_database(self):
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"Missing task script at {SCRIPT_PATH}",
        )
        module = load_module()

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self._build_fixture(root)
            db_path = root / "control-plane" / "career.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE migration_runs (id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO migration_runs (status) VALUES ('seeded')"
            )
            connection.commit()
            rows_before = connection.execute(
                "SELECT id, status FROM migration_runs ORDER BY id"
            ).fetchall()
            connection.close()
            bytes_before = db_path.read_bytes()

            inventory = module.build_inventory(root)

            self.assertNotIn("migration_run", inventory)
            rows_after_connection = sqlite3.connect(db_path)
            rows_after = rows_after_connection.execute(
                "SELECT id, status FROM migration_runs ORDER BY id"
            ).fetchall()
            rows_after_connection.close()
            bytes_after = db_path.read_bytes()

            self.assertEqual(rows_before, rows_after)
            self.assertEqual(bytes_before, bytes_after)


if __name__ == "__main__":
    unittest.main()
