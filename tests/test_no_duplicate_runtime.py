from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DuplicateRuntimeTests(unittest.TestCase):
    def test_app_is_documented_as_compatibility_only(self) -> None:
        readme = (ROOT / "app" / "README.md").read_text(encoding="utf-8")
        agents = (ROOT / "app" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("não é um runtime de produção", readme)
        self.assertIn("runtime canônico", agents)
        self.assertIn("Não importe módulos de `app/src`", agents)

    def test_production_compose_has_no_app_runtime_mount(self) -> None:
        for path in (ROOT / "compose.yaml", ROOT / "app" / "deploy" / "hermes" / "compose.yaml"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("/opt/agent-projects/candidaturas/app:/workspace/candidaturas", content)
            self.assertNotIn("/opt/agent-projects/candidaturas/app/src:", content)
            self.assertNotIn("/opt/agent-projects/candidaturas/app/scripts:", content)

    def test_compatibility_skills_point_to_root_skills(self) -> None:
        for relative in (
            "app/.agents/skills/career-system/SKILL.md",
            "app/.agents/skills/processe-a-vaga/SKILL.md",
        ):
            content = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("compatibilidade", content.lower())
            self.assertIn("raiz", content.lower())

    def test_vps_migration_syncs_root_runtime_not_app_runtime(self) -> None:
        content = (ROOT / "app" / "deploy" / "hermes" / "migrate-to-vps.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('"$project_root/" "$target_host:$target_root/"', content)
        self.assertIn("--exclude=app/", content)
        self.assertNotIn('"$project_root/app/" "$target_host:$target_root/app/"', content)


if __name__ == "__main__":
    unittest.main()
