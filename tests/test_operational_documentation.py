from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class OperationalDocumentationTests(unittest.TestCase):
    def test_phase8_docs_define_profile_aware_package_contract(self) -> None:
        documents = (
            ROOT / "AGENTS.md",
            ROOT / ".agents/skills/career-system/SKILL.md",
            ROOT / ".agents/skills/processe-a-vaga/SKILL.md",
        )
        for path in documents:
            text = path.read_text(encoding="utf-8")
            self.assertIn("delivery_profile", text, str(path))
            self.assertIn("gupy_registration", text, str(path))

    def test_phase8_docs_keep_sqlite_only_recovery_explicit(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("control-plane/career.db", text)
        self.assertIn("applications:reconcile", text)
        self.assertIn("workflow_state.json", text)

    def test_phase8_recovery_commands_exist_in_package(self) -> None:
        package = (ROOT / "package.json").read_text(encoding="utf-8")
        self.assertIn('"applications:resolve"', package)
        self.assertIn('"applications:artifact"', package)


if __name__ == "__main__":
    unittest.main()
