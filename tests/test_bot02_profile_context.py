from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


def _profile_value(config: str, pattern: str) -> str:
    match = re.search(pattern, config, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_both_profiles_share_canonical_skill_context_and_runtime_limits() -> None:
    configs = [
        (ROOT / "hermes/vagas_bot_01/config.yaml").read_text(encoding="utf-8"),
        (ROOT / "hermes/vagas_bot_02/config.yaml").read_text(encoding="utf-8"),
    ]

    assert all(
        _profile_value(config, r"^  max_turns:\s*(\d+)\s*$") == "150"
        for config in configs
    )
    context_caps = [
        int(_profile_value(config, r"^context_file_max_chars:\s*(\d+)\s*$"))
        for config in configs
    ]
    assert context_caps == [80000, 80000]
    assert all(cap >= (ROOT / "AGENTS.md").stat().st_size for cap in context_caps)
    assert all(
        "/workspace/candidaturas/.agents/skills" in config
        for config in configs
    )
    assert all(
        _profile_value(config, r"^\s+tirith_enabled:\s*(\w+)\s*$") == "false"
        for config in configs
    )

    canonical_skill = ROOT / ".agents/skills/processe-a-vaga/SKILL.md"
    assert canonical_skill.stat().st_size < 100_000
    assert not (
        ROOT
        / "hermes/vagas_bot_02/skills/software-development/processe-a-vaga"
    ).exists()
