from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.services.runtime_verifier import verify_runtime


ROOT = Path(__file__).resolve().parents[1]


class RuntimeVerifierTests(unittest.TestCase):
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
