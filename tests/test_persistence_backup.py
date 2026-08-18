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
SCRIPT_PATH = ROOT / "scripts" / "backup_persistence.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "backup_persistence", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PersistenceBackupTests(unittest.TestCase):
    def _build_fixture(self, root: Path) -> tuple[Path, Path]:
        control_plane = root / "control-plane"
        control_plane.mkdir(parents=True, exist_ok=True)
        db_path = control_plane / "career.db"
        connection = sqlite3.connect(db_path)
        connection.execute(
            "CREATE TABLE applications (id TEXT PRIMARY KEY, company TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO applications (id, company) VALUES (?, ?)",
            ("app_123", "Conexa"),
        )
        connection.commit()
        connection.close()

        legacy_path = root / ".career-state" / "workflow_state.json"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps({"stage": "fit_map_validated"}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_path = root / "outputs" / "cv.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-docx")
        return db_path, legacy_path

    def test_create_backup_uses_sqlite_backup_and_preserves_legacy_files(self):
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"Missing task script at {SCRIPT_PATH}",
        )
        module = load_module()

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            db_path, legacy_path = self._build_fixture(root)
            destination = root / "backups" / "runtime-unification-baseline"
            source_bytes_before = db_path.read_bytes()

            report = module.create_backup(root, destination)

            source_bytes_after = db_path.read_bytes()
            self.assertEqual(source_bytes_before, source_bytes_after)

            sqlite_backups = report["sqlite_backups"]
            self.assertEqual(len(sqlite_backups), 1)
            sqlite_entry = sqlite_backups[0]
            self.assertEqual(sqlite_entry["source"], "control-plane/career.db")
            self.assertTrue((destination / sqlite_entry["backup"]).exists())
            self.assertEqual(
                sqlite_entry["source_sha256"],
                sqlite_entry["backup_sha256"],
            )

            backup_connection = sqlite3.connect(destination / sqlite_entry["backup"])
            rows = backup_connection.execute(
                "SELECT id, company FROM applications ORDER BY id"
            ).fetchall()
            backup_connection.close()
            self.assertEqual(rows, [("app_123", "Conexa")])

            preserved = {
                entry["source"]: entry for entry in report["preserved_directories"]
            }
            self.assertIn(".career-state", preserved)
            self.assertIn("outputs", preserved)
            copied_legacy = destination / preserved[".career-state"]["backup"] / "workflow_state.json"
            self.assertTrue(copied_legacy.exists())
            self.assertEqual(
                copied_legacy.read_text(encoding="utf-8"),
                legacy_path.read_text(encoding="utf-8"),
            )

            manifest_path = destination / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["sqlite_backups"][0]["backup_sha256"],
                sqlite_entry["backup_sha256"],
            )
            copied_files = {
                entry["path"]: entry for entry in manifest["preserved_files"]
            }
            self.assertIn(".career-state/workflow_state.json", copied_files)
            self.assertIn("outputs/cv.docx", copied_files)

    def test_cli_dry_run_prints_manifest_preview_without_writing_backup(self):
        self.assertTrue(
            SCRIPT_PATH.exists(),
            f"Missing task script at {SCRIPT_PATH}",
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self._build_fixture(root)
            destination = root / "backups" / "preview"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--root",
                    str(root),
                    "--destination",
                    str(destination),
                    "--dry-run",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "dry_run")
            self.assertEqual(payload["destination"], str(destination.resolve()))
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
