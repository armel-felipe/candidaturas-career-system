#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import shutil
from pathlib import Path

import yaml

from _bootstrap import bootstrap

ROOT = bootstrap()


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
    result = {
        "status": "already_configured" if exists else "dry_run_ok",
        "config": str(config_path),
        "command": command,
        "apply": apply,
    }
    if apply and not exists:
        backup = config_path.with_suffix(config_path.suffix + ".bak.harness")
        shutil.copy2(config_path, backup)
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
