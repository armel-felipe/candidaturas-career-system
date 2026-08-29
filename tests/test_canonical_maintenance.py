from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from career.services.maintenance import (
    apply_maintenance_patch,
    create_maintenance_request,
)


class CanonicalMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "src" / "career" / "services").mkdir(parents=True)
        (self.root / "src" / "career" / "services" / "cv_content.py").write_text(
            "CLAUSES = {}\n", encoding="utf-8"
        )
        self._git("init", "-q")
        self._git("config", "user.email", "tests@example.com")
        self._git("config", "user.name", "Tests")
        self._git("add", ".")
        self._git("commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def _make_patch(self, relative_path: str, content: str) -> Path:
        target = self.root / relative_path
        original = target.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")
        patch_path = self.root / "maintenance.patch"
        patch_path.write_text(
            self._git("diff", "--", relative_path).stdout,
            encoding="utf-8",
        )
        target.write_text(original, encoding="utf-8")
        return patch_path

    def test_allowlisted_canonical_patch_is_dry_run_then_applied(self) -> None:
        request = create_maintenance_request(
            self.root,
            objective="Adicionar cláusulas ATS defensáveis em PT-BR",
            allowed_paths=["src/career/services/cv_content.py"],
        )
        patch = self._make_patch(
            "src/career/services/cv_content.py",
            'CLAUSES = {"governanca operacional": "Liderei governança operacional."}\n',
        )

        dry_run = apply_maintenance_patch(
            root=self.root,
            patch_path=patch,
            request_path=Path(request["request_path"]),
            apply=False,
        )
        self.assertEqual(dry_run["status"], "dry_run_ok")
        self.assertEqual(
            (self.root / "src/career/services/cv_content.py").read_text(encoding="utf-8"),
            "CLAUSES = {}\n",
        )

        applied = apply_maintenance_patch(
            root=self.root,
            patch_path=patch,
            request_path=Path(request["request_path"]),
            apply=True,
        )
        self.assertEqual(applied["status"], "applied")
        self.assertIn("governanca operacional", (self.root / "src/career/services/cv_content.py").read_text(encoding="utf-8"))

    def test_patch_outside_canonical_allowlist_is_rejected(self) -> None:
        request = create_maintenance_request(
            self.root,
            objective="Tentativa inválida",
            allowed_paths=["src/career/services/cv_content.py"],
        )
        (self.root / "outputs").mkdir()
        patch = self._make_patch("src/career/services/cv_content.py", "CLAUSES = {}\n")
        patch.write_text(
            patch.read_text(encoding="utf-8")
            + "diff --git a/outputs/x.txt b/outputs/x.txt\n"
            + "new file mode 100644\n"
            + "--- /dev/null\n+++ b/outputs/x.txt\n@@ -0,0 +1 @@\n+forbidden\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "outside canonical maintenance allowlist"):
            apply_maintenance_patch(
                root=self.root,
                patch_path=patch,
                request_path=Path(request["request_path"]),
                apply=False,
            )


if __name__ == "__main__":
    unittest.main()
