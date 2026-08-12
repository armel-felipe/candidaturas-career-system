#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import shutil
from pathlib import Path

import yaml

from _bootstrap import bootstrap

ROOT = bootstrap()
PLUGIN_NAME = "career-harness-output"
PLUGIN_SOURCE = ROOT / "integrations" / "hermes" / PLUGIN_NAME


def install(config_path: Path, *, apply: bool) -> dict:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    command = " ".join(
        [
            shlex.quote(str((ROOT / "scripts" / "python.sh").resolve())),
            shlex.quote(str((ROOT / "scripts" / "hermes_harness_context_hook.py").resolve())),
        ]
    )
    hooks = payload.setdefault("hooks", {})
    entries = hooks.setdefault("pre_llm_call", [])
    exists = any(isinstance(item, dict) and item.get("command") == command for item in entries)
    if not exists:
        entries.append({"command": command, "timeout": 300})
    enabled_plugins = payload.setdefault("plugins", {}).setdefault("enabled", [])
    plugin_enabled = PLUGIN_NAME in enabled_plugins
    if not plugin_enabled:
        enabled_plugins.append(PLUGIN_NAME)
    plugin_target = config_path.parent / "plugins" / PLUGIN_NAME
    needs_apply = not exists or not plugin_enabled or not plugin_target.exists()
    result = {
        "status": "already_configured" if not needs_apply else "dry_run_ok",
        "config": str(config_path),
        "command": command,
        "plugin": str(plugin_target),
        "apply": apply,
    }
    if apply and needs_apply:
        backup = config_path.with_suffix(config_path.suffix + ".bak.harness")
        shutil.copy2(config_path, backup)
        plugin_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PLUGIN_SOURCE, plugin_target, dirs_exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        result["status"] = "installed"
        result["backup"] = str(backup)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=str(Path.home() / ".hermes" / "profiles" / "candidaturas" / "config.yaml"),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = install(Path(args.config).expanduser().resolve(), apply=args.apply)
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
