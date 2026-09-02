from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".agents/skills/bot-runtime-switch/SKILL.md"


def test_runtime_switch_skill_contains_the_user_help_manual():
    text = SKILL.read_text(encoding="utf-8")

    assert "## Ajuda / Manual de uso" in text
    assert "O que a skill faz" in text
    assert "O que acontece automaticamente" in text
    assert "Opções disponíveis" in text
    assert "bot:runtime" in text
    assert "Hermes continua" in text
    assert "application_id" in text
    assert "run_id" in text
    assert "/opt/agent-projects/candidaturas" in text
    assert "NOTION_TOKEN" in text
