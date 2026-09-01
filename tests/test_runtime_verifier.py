from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from career.services.database import Database
from career.services.maintenance_orchestrator import MaintenanceOrchestrator
from career.services.runtime_verifier import verify_runtime


ROOT = Path(__file__).resolve().parents[1]


class RuntimeVerifierTests(unittest.TestCase):
    def test_resume_requires_both_exact_application_and_run_ids(self) -> None:
        for request in (
            {"application_id": "app_exact", "run_id": ""},
            {"application_id": "", "run_id": "run_exact"},
        ):
            with self.subTest(request=request), patch(
                "career.services.maintenance_orchestrator.subprocess.run"
            ) as run:
                result = MaintenanceOrchestrator(ROOT).resume_original_run(request)

            self.assertEqual(result["status"], "not_requested")
            run.assert_not_called()

    def test_resume_requires_exact_application_and_run_ids(self) -> None:
        with patch("career.services.maintenance_orchestrator.subprocess.run") as run:
            result = MaintenanceOrchestrator(ROOT).resume_original_run(
                {"application_id": "", "run_id": ""}
            )

        self.assertEqual(result["status"], "not_requested")
        run.assert_not_called()

    def test_resume_uses_only_the_scoped_ids_from_the_request(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "resumed\n", "")
        with patch(
            "career.services.maintenance_orchestrator.subprocess.run",
            return_value=completed,
        ) as run:
            result = MaintenanceOrchestrator(ROOT).resume_original_run(
                {"application_id": "app_exact", "run_id": "run_exact"}
            )

        self.assertEqual(result["status"], "resumed")
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                "npm",
                "run",
                "applications:run",
                "--",
                "--application-id",
                "app_exact",
                "--run-id",
                "run_exact",
                "--run-agent",
            ],
        )
    def test_strict_verifier_blocks_unmigrated_database_without_mutating_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "missing.db"
            report = verify_runtime(ROOT, strict=True, database_path=database_path)

        self.assertEqual(report.status, "blocked")
        self.assertIn("DB_SCHEMA", {item["code"] for item in report.blockers})
        self.assertFalse(database_path.exists())

    def test_strict_verifier_passes_against_a_complete_migrated_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "control-plane" / "career.db"
            database = Database(db_path=database_path)
            database.migrate()
            database.close()

            report = verify_runtime(ROOT, strict=True, database_path=database_path)

        self.assertEqual(report.status, "passed")
        self.assertEqual(report.blockers, ())
        self.assertEqual({item["code"] for item in report.warnings}, set())

    def test_cli_writes_report_and_returns_nonzero_for_strict_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "missing.db"
            report_path = Path(directory) / "runtime.json"
            result = subprocess.run(
                [
                    str(ROOT / "scripts" / "python.sh"),
                    str(ROOT / "scripts" / "verify_runtime_unification.py"),
                    "--strict",
                    "--db",
                    str(database_path),
                    "--report",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["blockers"])


if __name__ == "__main__":
    unittest.main()
