from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROFILE_CONFIGS = (
    ROOT / "hermes" / "vagas_bot_01" / "config.yaml",
    ROOT / "hermes" / "vagas_bot_02" / "config.yaml",
)
BOT_02_CONFIG = ROOT / "hermes" / "vagas_bot_02" / "config.yaml"
EXPECTED_PROVIDER = "ollama-cloud"
OPTIONAL_LOCAL_PROVIDER = "tailscale-openai-local"
EXPECTED_LOCAL_ENDPOINT = "http://100.87.71.48:11434/v1"


def test_bot_profiles_use_ollama_cloud_for_main_agent() -> None:
    for config_path in PROFILE_CONFIGS:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        model = config.get("model") or {}

        assert model.get("provider") == EXPECTED_PROVIDER, config_path
        assert str(model.get("default") or "").strip(), config_path


def test_bot_profiles_keep_local_provider_available_for_explicit_selection() -> None:
    for config_path in PROFILE_CONFIGS:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        providers = config.get("providers") or {}
        local_provider = providers.get(OPTIONAL_LOCAL_PROVIDER) or {}

        assert local_provider.get("api") == EXPECTED_LOCAL_ENDPOINT, config_path
        assert local_provider.get("transport") == "chat_completions", config_path


def test_unattended_bot_profiles_stop_repeated_tool_failures() -> None:
    config = yaml.safe_load(BOT_02_CONFIG.read_text(encoding="utf-8")) or {}
    agent = config.get("agent") or {}
    guardrails = config.get("tool_loop_guardrails") or {}

    assert agent.get("max_turns") == 150, BOT_02_CONFIG
    assert guardrails.get("hard_stop_enabled") is True, BOT_02_CONFIG
    assert guardrails.get("hard_stop_after", {}).get("same_tool_failure") == 8, BOT_02_CONFIG
