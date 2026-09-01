from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from career.services.maintenance import (
    apply_maintenance_patch,
    create_maintenance_request,
)
from career.services import maintenance


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


def make_git_fixture(root: Path, *, files: dict[str, str] | None = None) -> Path:
    fixture_files = files or {"README.md": "base\n"}
    for relative_path, content in fixture_files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "tests@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Tests"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "base"],
        check=True,
    )
    return root


def test_request_contains_spec_evidence_scope_and_fingerprint(tmp_path: Path) -> None:
    request = create_maintenance_request(
        tmp_path,
        objective="Corrigir seletor canônico",
        allowed_paths=["src/career/services/cv_content.py"],
        spec={"requirements": [{"id": "REQ-1", "text": "Cobrir lacunas >36 meses"}]},
        evidence={"error": "seleção parava em seis experiências"},
        requester_profile="vagas_bot_01",
        application_id="app_demo",
        run_id="run_demo",
    )
    assert request["schema_version"] == 2
    assert request["application_id"] == "app_demo"
    assert request["spec"]["requirements"][0]["id"] == "REQ-1"
    assert len(request["request_fingerprint"]) == 64
    assert callable(getattr(maintenance, "validate_maintenance_request", None))
    assert maintenance.validate_maintenance_request(tmp_path, Path(request["request_path"]))["status"] == "ok"


def test_request_rejects_missing_requirement_spec(tmp_path: Path) -> None:
    request = create_maintenance_request(
        tmp_path, objective="Sem spec", allowed_paths=["src/x.py"]
    )
    validator = getattr(maintenance, "validate_maintenance_request", None)
    assert callable(validator)
    with pytest.raises(ValueError, match="spec"):
        validator(tmp_path, Path(request["request_path"]))


def test_existing_canonical_skill_file_is_allowed(tmp_path: Path) -> None:
    root = make_git_fixture(tmp_path, files={".agents/skills/demo/SKILL.md": "base\n"})
    validator = getattr(maintenance, "validate_maintenance_paths", None)
    assert callable(validator)
    result = validator(root, [".agents/skills/demo/SKILL.md"])
    assert result["status"] == "ok"


def test_new_skill_directory_is_rejected(tmp_path: Path) -> None:
    root = make_git_fixture(tmp_path)
    validator = getattr(maintenance, "validate_maintenance_paths", None)
    assert callable(validator)
    result = validator(root, [".agents/skills/new-skill/SKILL.md"])
    assert result["status"] == "blocked"
    assert result["blocker"] == "new_skill_forbidden"


def test_generated_state_is_rejected_even_when_versioned_scope_is_requested(tmp_path: Path) -> None:
    root = make_git_fixture(tmp_path)
    validator = getattr(maintenance, "validate_maintenance_paths", None)
    assert callable(validator)
    result = validator(root, [".career-state/applications_v2/demo/fit_map.json"])
    assert result["status"] == "blocked"
    assert result["blocker"] == "generated_state_forbidden"


if __name__ == "__main__":
    unittest.main()
