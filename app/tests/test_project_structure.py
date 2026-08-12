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


def test_project_has_no_machine_specific_workspace_path():
    forbidden = "/Users/mac/llm server/projetos/candidaturas"
    assert forbidden in validate_project_structure.FORBIDDEN_TEXT
    assert validate_project_structure.main() == 0


def test_instruction_architecture_registry_and_limits():
    assert validate_project_structure.INSTRUCTION_MODULES == frozenset(
        {
            "runtime-core",
            "intake-fit-map",
            "cv-delivery",
            "notion-email",
            "cellular-runtime",
        }
    )
    assert validate_project_structure.ROUTED_CAREER_SKILLS["cv-generator"] == frozenset(
        {"runtime-core", "cv-delivery"}
    )


def test_instruction_architecture_rejects_unknown_module(tmp_path, monkeypatch):
    skills = tmp_path / ".agents" / "skills"
    skill = skills / "cv-generator" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\ninstruction_modules:\n  - runtime-core\n  - missing-module\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validate_project_structure, "ROOT", tmp_path)
    monkeypatch.setattr(validate_project_structure, "AGENT_SKILLS", skills)
    errors: list[str] = []

    validate_project_structure.validate_instruction_architecture(errors)

    assert "unknown instruction module: missing-module" in "\n".join(errors)
