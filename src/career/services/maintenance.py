from __future__ import annotations

import json
import hashlib
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT


CANONICAL_PREFIXES = ("src/", ".agents/skills/", "hermes-src/")
MAINTENANCE_REQUEST_VERSION = 2
GENERATED_STATE_PREFIXES = (".career-state/", "outputs/", "control-plane/")
SQLITE_SUFFIXES = (
    ".sqlite",
    ".sqlite3",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite-journal",
    ".db",
    ".db-wal",
    ".db-shm",
    ".db-journal",
)
FORBIDDEN_PATH_MARKERS = (
    ".env",
    "credentials",
    "credential",
    "cache",
    "dump",
    "sealed",
)


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


def _normalise_request_path(value: str) -> str:
    path = Path(str(value).strip())
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid maintenance path: {value}")
    normalised = path.as_posix()
    if not normalised:
        raise ValueError(f"invalid maintenance path: {value}")
    return normalised


def _git_path_exists_at_base(root: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"HEAD:{relative_path}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_repository(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_head(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _path_blocker(root: Path, relative_path: str) -> str | None:
    if relative_path.startswith(GENERATED_STATE_PREFIXES):
        return "generated_state_forbidden"
    path_parts = relative_path.split("/")
    if path_parts[-1].lower().endswith(SQLITE_SUFFIXES):
        return "sqlite_artifact_forbidden"
    if any(
        marker in part.lower() or (marker == ".env" and part.lower().startswith(".env"))
        for part in path_parts
        for marker in FORBIDDEN_PATH_MARKERS
    ):
        return "sensitive_artifact_forbidden"
    if not any(relative_path.startswith(prefix) for prefix in CANONICAL_PREFIXES):
        return "outside_canonical_allowlist"

    candidate = root / Path(relative_path)
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve(strict=False)
    except OSError:
        return "path_resolution_failed"
    if os.path.commonpath([str(resolved_root), str(resolved_candidate)]) != str(resolved_root):
        return "symlink_escape"

    if relative_path.startswith(".agents/skills/"):
        skill_name = relative_path.split("/", 3)[2]
        if not skill_name or not _git_path_exists_at_base(root, f".agents/skills/{skill_name}"):
            return "new_skill_forbidden"

    if _git_path_exists_at_base(root, relative_path):
        return None
    parent = Path(relative_path).parent.as_posix()
    if parent == "." or not _git_path_exists_at_base(root, parent):
        return "new_file_parent_missing"
    return None


def validate_maintenance_paths(root: Path, allowed_paths: list[str]) -> dict[str, Any]:
    """Validate an exact, repository-relative maintenance scope."""
    root = Path(root)
    if not _git_repository(root):
        return {"status": "blocked", "blocker": "not_a_git_repository", "paths": []}
    normalised: list[str] = []
    for value in allowed_paths:
        try:
            relative_path = _normalise_request_path(value)
        except ValueError:
            return {"status": "blocked", "blocker": "invalid_path", "path": str(value), "paths": normalised}
        blocker = _path_blocker(root, relative_path)
        if blocker:
            return {"status": "blocked", "blocker": blocker, "path": relative_path, "paths": normalised}
        normalised.append(relative_path)
    if not normalised:
        return {"status": "blocked", "blocker": "empty_scope", "paths": []}
    return {"status": "ok", "paths": sorted(set(normalised))}


def maintenance_request_fingerprint(payload: dict[str, Any]) -> str:
    volatile = {
        "applied_at",
        "attempts",
        "blocker_reason",
        "committed_at",
        "created_at",
        "receipt_path",
        "request_fingerprint",
        "request_id",
        "request_path",
        "status",
    }
    canonical = {key: value for key, value in payload.items() if key not in volatile}
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_maintenance_request(root: Path, request_path: Path) -> dict[str, Any]:
    payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != MAINTENANCE_REQUEST_VERSION:
        raise ValueError("unknown maintenance request schema_version")
    for field in ("request_id", "requester_profile", "roadmap_id", "base_commit"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"maintenance request {field} is required")
    if not str(payload.get("objective", "")).strip():
        raise ValueError("maintenance objective is required")
    spec = payload.get("spec")
    if not isinstance(spec, dict) or not isinstance(spec.get("requirements"), list) or not spec["requirements"]:
        raise ValueError("maintenance request spec must contain requirements")
    if not payload.get("evidence"):
        raise ValueError("maintenance request evidence is required")
    if bool(payload.get("application_id")) != bool(payload.get("run_id")):
        raise ValueError("application_id and run_id must be provided together")
    try:
        paths = sorted({_normalise_relative_path(path) for path in payload.get("allowed_paths", [])})
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid maintenance request paths: {exc}") from exc
    if not paths:
        raise ValueError("maintenance request has no canonical allowlist")
    if payload.get("request_fingerprint") != maintenance_request_fingerprint(payload):
        raise ValueError("maintenance request fingerprint mismatch")
    return {"status": "ok", "request_id": payload.get("request_id"), "paths": paths}


def create_maintenance_request(
    root: Path,
    *,
    objective: str,
    allowed_paths: list[str],
    spec: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    requester_profile: str = "",
    application_id: str | None = None,
    run_id: str | None = None,
    roadmap_id: str = "MAINT-002",
    base_commit: str | None = None,
) -> dict[str, Any]:
    if not objective.strip():
        raise ValueError("maintenance objective is required")
    if not allowed_paths:
        raise ValueError("at least one canonical path is required")
    if bool(application_id) != bool(run_id):
        raise ValueError("application_id and run_id must be provided together")
    normalised = sorted({_normalise_relative_path(path) for path in allowed_paths})
    request_id = f"maintenance_{uuid.uuid4().hex[:12]}"
    request_path = root / CAREER_STATE.name / "maintenance" / "requests" / f"{request_id}.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": request_id,
        "status": "requested",
        "objective": objective.strip(),
        "allowed_paths": normalised,
        "schema_version": MAINTENANCE_REQUEST_VERSION,
        "requester_profile": requester_profile,
        "application_id": application_id,
        "run_id": run_id,
        "roadmap_id": roadmap_id,
        "base_commit": base_commit or _git_head(root),
        "spec": spec if spec is not None else {},
        "evidence": evidence if evidence is not None else {},
        "created_at": _now(),
        "request_path": str(request_path),
    }
    payload["request_fingerprint"] = maintenance_request_fingerprint(payload)
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
    policy = validate_maintenance_paths(root, sorted(allowed))
    if policy["status"] != "ok":
        detail = policy.get("path", "")
        raise ValueError(
            f"maintenance path policy blocked: {policy['blocker']}"
            + (f" ({detail})" if detail else "")
        )
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
