from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT


CANONICAL_PREFIXES = ("src/", ".agents/skills/", "hermes-src/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_relative_path(value: str) -> str:
    path = Path(str(value).strip())
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid maintenance path: {value}")
    normalised = path.as_posix()
    if not normalised or not any(normalised.startswith(prefix) for prefix in CANONICAL_PREFIXES):
        raise ValueError(f"path outside canonical maintenance allowlist: {value}")
    return normalised


def create_maintenance_request(
    root: Path,
    *,
    objective: str,
    allowed_paths: list[str],
) -> dict[str, Any]:
    if not objective.strip():
        raise ValueError("maintenance objective is required")
    if not allowed_paths:
        raise ValueError("at least one canonical path is required")
    normalised = sorted({_normalise_relative_path(path) for path in allowed_paths})
    request_id = f"maintenance_{uuid.uuid4().hex[:12]}"
    request_path = root / CAREER_STATE.name / "maintenance" / "requests" / f"{request_id}.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": request_id,
        "status": "requested",
        "objective": objective.strip(),
        "allowed_paths": normalised,
        "created_at": _now(),
        "request_path": str(request_path),
    }
    request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _patch_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        if not (line.startswith("--- ") or line.startswith("+++ ")):
            continue
        value = line[4:].split("\t", 1)[0].split(" ", 1)[0]
        if value == "/dev/null":
            continue
        if value.startswith("a/") or value.startswith("b/"):
            value = value[2:]
        paths.append(_normalise_relative_path(value))
    if not paths:
        raise ValueError("maintenance patch has no canonical file paths")
    return sorted(set(paths))


def _git_apply(root: Path, patch_path: Path, *, check: bool) -> None:
    command = ["git", "-C", str(root), "apply"]
    if check:
        command.extend(["--check", "--whitespace=error"])
    command.append(str(patch_path))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"maintenance patch rejected by git: {detail}")


def apply_maintenance_patch(
    *,
    root: Path = ROOT,
    patch_path: Path,
    request_path: Path,
    apply: bool = False,
) -> dict[str, Any]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    allowed = {_normalise_relative_path(path) for path in request.get("allowed_paths", [])}
    if not allowed:
        raise ValueError("maintenance request has no canonical allowlist")
    patch_files = set(_patch_paths(patch_path.read_text(encoding="utf-8")))
    outside = sorted(patch_files - allowed)
    if outside:
        raise ValueError(
            "patch contains paths outside canonical maintenance allowlist: "
            + ", ".join(outside)
        )
    _git_apply(root, patch_path, check=True)
    if not apply:
        return {
            "status": "dry_run_ok",
            "request_id": request.get("request_id"),
            "patch": str(patch_path),
            "paths": sorted(patch_files),
        }
    _git_apply(root, patch_path, check=False)
    request["status"] = "applied"
    request["applied_at"] = _now()
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "applied",
        "request_id": request.get("request_id"),
        "patch": str(patch_path),
        "paths": sorted(patch_files),
    }
