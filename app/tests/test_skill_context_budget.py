from pathlib import Path


def test_cv_generator_skill_fits_the_agent_request_budget():
    project_root = Path(__file__).resolve().parents[1]
    skill_paths = (
        project_root / ".agents/skills/cv-generator/SKILL.md",
        project_root.parent / ".agents/skills/cv-generator/SKILL.md",
    )
    for skill_path in skill_paths:
        assert skill_path.is_file()
        assert skill_path.stat().st_size < 50_000, f"oversized skill: {skill_path}"
