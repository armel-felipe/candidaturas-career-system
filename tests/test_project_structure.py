from pathlib import Path

from scripts import validate_project_structure


ROOT = Path(__file__).resolve().parent.parent


def test_agents_skill_root_is_canonical_and_valid(capsys):
    assert (ROOT / ".agents" / "skills" / "career-system" / "SKILL.md").is_file()
    assert not (ROOT / ".opencode").exists()
    assert ".agents" in validate_project_structure.SCAN_ROOTS
    assert ".opencode" not in validate_project_structure.SCAN_ROOTS
    assert ".opencode" in validate_project_structure.FORBIDDEN_PATHS
    assert ".opencode/skills" in validate_project_structure.FORBIDDEN_TEXT
    assert validate_project_structure.main() == 0
    assert "Project structure validation passed." in capsys.readouterr().out
