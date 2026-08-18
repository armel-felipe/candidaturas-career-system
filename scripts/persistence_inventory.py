from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback only matters in constrained runtimes
    yaml = None


CANONICAL_MIRRORS = (
    "AGENTS.md",
    "package.json",
    ".agents/",
    "src/",
    "scripts/",
    "TELEGRAM_HARNESS_RUNBOOK.md",
    "LINKEDIN_AUTH_RUNBOOK.md",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_rg_files(root: Path, *patterns: str) -> list[str]:
    if shutil.which("rg"):
        command = ["rg", "--files", "--hidden", "-uu"]
        for pattern in patterns:
            command.extend(["-g", pattern])
        completed = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return [line for line in completed.stdout.splitlines() if line]

    matches: list[str] = []
    if not patterns:
        for path in root.rglob("*"):
            if path.is_file():
                matches.append(path.relative_to(root).as_posix())
        return sorted(matches)

    for pattern in patterns:
        matches.extend(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())
        matches.extend(
            path.relative_to(root).as_posix()
            for path in root.rglob(pattern)
            if path.is_file()
        )
    return sorted(dict.fromkeys(matches))


def _json_domain(relative_path: str) -> str:
    if relative_path.startswith(".career-state/"):
        return "root_career_state"
    if relative_path.startswith("app/.career-state/"):
        return "app_career_state"
    if relative_path.startswith("control-plane/") or relative_path.startswith(".career-control/"):
        return "control_plane"
    if relative_path.startswith("hermes/") or relative_path.startswith("hermes-src/"):
        return "hermes"
    if relative_path.startswith("workspaces/"):
        return "workspace_runtime"
    if relative_path.startswith(".agents/"):
        return "root_skills"
    if relative_path.startswith("app/.agents/"):
        return "app_skills"
    if relative_path.startswith("src/") or relative_path.startswith("scripts/"):
        return "root_runtime_code"
    if relative_path.startswith("app/src/") or relative_path.startswith("app/scripts/"):
        return "app_runtime_code"
    if relative_path.startswith("docs/") or relative_path.startswith("app/docs/"):
        return "docs"
    if relative_path.startswith("outputs/") or relative_path.startswith("inbox/"):
        return "generated_artifact"
    return "other"


def _classify_mount(target: str, source: str) -> str:
    if target == "/workspace/candidaturas" or target.startswith("/workspace/candidaturas/src") or target.startswith("/workspace/candidaturas/scripts") or target.startswith("/workspace/candidaturas/.agents"):
        return "runtime_code"
    if target.startswith("/workspace/candidaturas/.career-control"):
        return "control_plane"
    if target.startswith("/workspace/candidaturas/.career-state"):
        return "bot_state"
    if target.startswith("/workspace/candidaturas/outputs"):
        return "bot_outputs"
    if target.startswith("/workspace/candidaturas/inbox"):
        return "bot_inbox"
    if target == "/workspace/candidaturas/.env":
        return "bot_env"
    if target.startswith("/opt/data") or source.startswith("/opt/agent-projects/candidaturas/hermes/"):
        return "runtime_data"
    if "playwright" in target or "playwright" in source:
        return "browser_state"
    if "rclone" in target or "rclone" in source:
        return "external_binary"
    return "other"


def _parse_volume(entry: Any) -> dict[str, Any]:
    if isinstance(entry, str):
        parts = entry.split(":")
        if len(parts) >= 3:
            source = ":".join(parts[:-2])
            target = parts[-2]
            mode = parts[-1]
        elif len(parts) == 2:
            source, target = parts
            mode = "rw"
        else:
            source = parts[0]
            target = ""
            mode = "rw"
        return {
            "source": source,
            "target": target,
            "mode": mode,
            "classification": _classify_mount(target, source),
        }

    if isinstance(entry, dict):
        source = str(entry.get("source") or "")
        target = str(entry.get("target") or "")
        read_only = bool(entry.get("read_only"))
        return {
            "source": source,
            "target": target,
            "mode": "ro" if read_only else str(entry.get("mode") or "rw"),
            "classification": _classify_mount(target, source),
        }

    return {
        "source": "",
        "target": "",
        "mode": "rw",
        "classification": "other",
    }


def _load_compose(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"compose_path": path.as_posix(), "services": {}}
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse compose files for persistence inventory")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    services_payload = payload.get("services") or {}
    services: dict[str, Any] = {}
    for service_name, config in services_payload.items():
        mounts = [_parse_volume(entry) for entry in (config or {}).get("volumes", [])]
        services[service_name] = {
            "mounts": mounts,
            "working_dir": (config or {}).get("working_dir"),
        }
    return {
        "compose_path": path.relative_to(path.parents[3]).as_posix(),
        "services": services,
    }


def _is_canonical_mirror(relative_path: str) -> bool:
    return any(
        relative_path == candidate or relative_path.startswith(candidate)
        for candidate in CANONICAL_MIRRORS
    )


def _find_root_app_divergences(root: Path, file_paths: list[str]) -> list[dict[str, Any]]:
    divergences: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relative_path in file_paths:
        if not relative_path.startswith("app/"):
            continue
        canonical_path = relative_path.removeprefix("app/")
        if canonical_path in seen or not _is_canonical_mirror(canonical_path):
            continue
        root_path = root / canonical_path
        app_path = root / relative_path
        if not root_path.is_file() or not app_path.is_file():
            continue
        root_hash = _sha256(root_path)
        app_hash = _sha256(app_path)
        if root_hash == app_hash:
            continue
        seen.add(canonical_path)
        divergences.append(
            {
                "canonical_path": canonical_path,
                "root_path": canonical_path,
                "app_path": relative_path,
                "root_sha256": root_hash,
                "app_sha256": app_hash,
                "root_size": root_path.stat().st_size,
                "app_size": app_path.stat().st_size,
            }
        )
    divergences.sort(key=lambda entry: entry["canonical_path"])
    return divergences


def build_inventory(root: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    all_files = sorted(_run_rg_files(resolved_root))
    root_app_divergences = _find_root_app_divergences(resolved_root, all_files)
    json_files: list[dict[str, Any]] = []
    domain_counts: dict[str, int] = {}
    for relative_path in sorted(_run_rg_files(resolved_root, "*.json")):
        file_path = resolved_root / relative_path
        if not file_path.is_file():
            continue
        domain = _json_domain(relative_path)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        json_files.append(
            {
                "path": relative_path,
                "domain": domain,
                "sha256": _sha256(file_path),
                "size_bytes": file_path.stat().st_size,
            }
        )

    hermes = _load_compose(resolved_root / "app" / "deploy" / "hermes" / "compose.yaml")
    inventory = {
        "root": str(resolved_root),
        "generated_at": datetime.now(UTC).isoformat(),
        "json_files": json_files,
        "root_app_divergences": root_app_divergences,
        "hermes": hermes,
        "summary": {
            "json_file_count": len(json_files),
            "json_domains": domain_counts,
            "root_app_divergence_count": len(root_app_divergences),
            "hermes_service_count": len(hermes["services"]),
        },
    }
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a persistence inventory baseline")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/_tmp/persistence_inventory.json"),
    )
    args = parser.parse_args()

    inventory = build_inventory(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "json_file_count": inventory["summary"]["json_file_count"],
                "root_app_divergence_count": inventory["summary"]["root_app_divergence_count"],
                "hermes_service_count": inventory["summary"]["hermes_service_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
