from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_both_profiles_declare_the_same_three_tier_skill_precedence():
    expected = ["project", "global", "profile"]
    configs = [
        ROOT / "hermes" / profile / "config.yaml"
        for profile in ("vagas_bot_01", "vagas_bot_02")
    ] + [
        ROOT / "hermes" / "runtime" / profile / "config.yaml"
        for profile in ("vagas_bot_01", "vagas_bot_02")
    ]
    for config_path in configs:
        text = config_path.read_text(
            encoding="utf-8"
        )
        assert "project_dirs:" in text
        assert "    - /workspace/candidaturas/.agents/skills" in text
        assert "source_precedence:" in text
        actual = text.split("source_precedence:", 1)[1].split("\n", 4)[1:4]
        assert [line.strip(" -") for line in actual] == expected


def test_runtime_roots_keep_the_same_turn_and_context_limits():
    for profile in ("vagas_bot_01", "vagas_bot_02"):
        text = (ROOT / "hermes" / "runtime" / profile / "config.yaml").read_text(
            encoding="utf-8"
        )
        assert "  max_turns: 150" in text
        assert "context_file_max_chars: 80000" in text
        assert "tirith_enabled: false" in text


def test_confirmed_project_skill_duplicates_are_absent_from_profiles():
    forbidden = (
        "hermes/vagas_bot_01/skills/software-development/career-system-workflow",
        "hermes/vagas_bot_02/skills/software-development/candidaturas-operational-patterns",
        "hermes/vagas_bot_02/skills/career/cv-generator",
        "hermes/vagas_bot_02/skills/software-development/enquadramento-posicionamento",
        "hermes/vagas_bot_02/skills/software-development/linkedin-saved-jobs",
        "hermes/vagas_bot_02/skills/creative/feras-pitch",
    )
    for relative in forbidden:
        assert not (ROOT / relative).exists(), relative
