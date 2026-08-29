from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ProcesseAVagaContractTests(unittest.TestCase):
    def test_main_skill_closes_only_the_base_package(self) -> None:
        text = (ROOT / ".agents/skills/processe-a-vaga/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("## Pacote-base", text)
        self.assertIn("## Pós-processamento", text)
        self.assertIn("core_package_sealed", text)
        self.assertIn("applications:resolve", text)
        self.assertIn("applications:reconcile", text)
        self.assertIn("application_id", text)
        self.assertNotIn("workflow_state.json` será escrito", text)
        self.assertNotIn("gerar FERAS automaticamente", text)
        self.assertNotIn("gerar carta automaticamente", text)
        self.assertNotIn("gerar habilidades Gupy automaticamente", text)

    def test_end_to_end_package_uses_cellular_orchestrator(self) -> None:
        text = (ROOT / ".agents/skills/processe-a-vaga/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("applications:plan", text)
        self.assertIn("applications:run", text)
        self.assertIn("injetar provenance", text.casefold())
        self.assertIn("não pode cair para `fit-map:finalize`", text.casefold())

    def test_governance_docs_agree_on_post_processing_boundary(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        career_system = (
            ROOT / ".agents/skills/career-system/SKILL.md"
        ).read_text(encoding="utf-8")

        for text in (agents, career_system):
            self.assertIn("core_package_sealed", text)
            self.assertIn("pós-processamento", text.casefold())
            self.assertIn("application_id", text)

    def test_post_processing_skills_use_explicit_application_scope(self) -> None:
        for relative_path in (
            ".agents/skills/feras-pitch/SKILL.md",
            ".agents/skills/habilidades-chave/SKILL.md",
            ".agents/skills/cover-letter/SKILL.md",
        ):
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("application_id", text)
            self.assertIn("create_post_artifact", text)
            self.assertNotIn("Use `.career-state/fit_map.json` como FIT_MAP ativo", text)


if __name__ == "__main__":
    unittest.main()
