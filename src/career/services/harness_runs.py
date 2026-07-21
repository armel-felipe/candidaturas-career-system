from __future__ import annotations

import hashlib
import json
import os
import fnmatch
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from career.utils import ValidationFailure, read_json, utc_now_iso, write_json, write_text


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def allowed_outputs_from_request(request_json: Path, root: Path) -> list[Path]:
    if not request_json.exists():
        return []
    payload = read_json(request_json)
    if payload.get("cellular") is True:
        write_allowlist = payload.get("write_allowlist")
        if not isinstance(write_allowlist, list) or not write_allowlist:
            raise ValidationFailure("cellular harness request requires write_allowlist")
        return [
            (root / str(item)).resolve()
            for item in write_allowlist
            if item and "<" not in str(item)
        ]
    raw: list[str] = []
    outputs = payload.get("outputs")
    if isinstance(outputs, dict):
        allowed_files = outputs.get("allowed_files")
        if isinstance(allowed_files, list):
            raw.extend(str(item) for item in allowed_files)
    required = payload.get("required_output")
    if isinstance(required, dict):
        raw.extend(str(item) for item in required.values())
    allowed = payload.get("allowed_outputs")
    if isinstance(allowed, list):
        raw.extend(str(item) for item in allowed)
    return [(root / item).resolve() for item in raw if item and "<" not in item]


@dataclass
class HarnessRun:
    root: Path
    application_dir: Path
    run_dir: Path
    stage: str
    allowed_outputs: list[Path]
    before_files: dict[str, str]

    def inspect(self) -> dict[str, Any]:
        after_files = self._snapshot_application_files()
        changed = sorted(
            path
            for path in set(self.before_files) | set(after_files)
            if self.before_files.get(path) != after_files.get(path)
        )
        allowed = [path.resolve() for path in self.allowed_outputs]
        unauthorized = [
            path
            for path in changed
            if not any(
                (self.application_dir / path).resolve() == allowed_path
                or (self.application_dir / path).resolve().is_relative_to(allowed_path)
                for allowed_path in allowed
            )
            and not path.startswith("requests/")
        ]
        return {
            "status": "blocked" if unauthorized else "ok",
            "changed_files": changed,
            "allowed_outputs": sorted(
                str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
                for path in self.allowed_outputs
            ),
            "unauthorized_changes": unauthorized,
        }

    def finish(self, result: dict[str, Any], validation: dict[str, Any]) -> None:
        write_json(self.run_dir / "result.json", result)
        write_json(self.run_dir / "validation.json", validation)
        write_text(self.run_dir / "stdout.log", str(result.get("stdout") or ""))
        write_text(self.run_dir / "stderr.log", str(result.get("stderr") or ""))

    def _snapshot_application_files(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in self.application_dir.rglob("*"):
            if not path.is_file() or self.run_dir in path.parents or "requests" in path.relative_to(self.application_dir).parts:
                continue
            snapshot[str(path.relative_to(self.application_dir))] = _file_hash(path)
        return snapshot


class HarnessRunStore:
    def __init__(self, root: Path, application_dir: Path):
        self.root = root
        self.application_dir = application_dir

    def begin(self, stage: str, request_json: Path, request_md: Path) -> HarnessRun:
        timestamp = utc_now_iso().replace(":", "").replace("-", "").replace("+", "_").replace(".", "")
        run_id = f"{timestamp}_{stage}_{uuid.uuid4().hex[:8]}"
        run_dir = self.application_dir / "requests" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        if request_json.exists():
            write_text(run_dir / "request.json", request_json.read_text(encoding="utf-8"))
        if request_md.exists():
            write_text(run_dir / "request.md", request_md.read_text(encoding="utf-8"))
        allowed_outputs = allowed_outputs_from_request(request_json, self.root)
        run = HarnessRun(
            root=self.root,
            application_dir=self.application_dir,
            run_dir=run_dir,
            stage=stage,
            allowed_outputs=allowed_outputs,
            before_files={},
        )
        run.before_files = run._snapshot_application_files()
        write_json(
            run_dir / "manifest.json",
            {
                "run_id": run_id,
                "stage": stage,
                "created_at": utc_now_iso(),
                "source_request_json": str(request_json.relative_to(self.root)),
                "source_request_md": str(request_md.relative_to(self.root)),
                "allowed_outputs": [
                    str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
                    for path in allowed_outputs
                ],
            },
        )
        return run


def _workspace_snapshot(root: Path, excluded: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for relative_root in (".career-state", "outputs", "inbox"):
        base = root / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path == excluded or excluded in path.parents:
                continue
            stat = path.stat()
            snapshot[str(path.relative_to(root))] = f"{stat.st_size}:{stat.st_mtime_ns}"
    return snapshot


def _git_status_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return set()
    return {line[3:].strip() for line in result.stdout.splitlines() if len(line) > 3}


@dataclass
class SpecialistHarnessRun:
    root: Path
    run_dir: Path
    allowed_patterns: list[str]
    before_files: dict[str, str]
    before_git_status: set[str]

    def inspect(self) -> dict[str, Any]:
        after_files = _workspace_snapshot(self.root, self.run_dir)
        changed = sorted(
            path
            for path in set(self.before_files) | set(after_files)
            if self.before_files.get(path) != after_files.get(path)
        )
        after_git = _git_status_paths(self.root)
        new_git_changes = sorted(after_git - self.before_git_status)
        unauthorized = [
            path for path in changed if not any(fnmatch.fnmatch(path, pattern) for pattern in self.allowed_patterns)
        ]
        unauthorized.extend(
            path
            for path in new_git_changes
            if path not in unauthorized
            and not any(fnmatch.fnmatch(path, pattern) for pattern in self.allowed_patterns)
        )
        allowed_changed = [
            path for path in changed if any(fnmatch.fnmatch(path, pattern) for pattern in self.allowed_patterns)
        ]
        return {
            "status": "blocked" if unauthorized else "ok",
            "changed_files": changed,
            "allowed_changed_files": sorted(allowed_changed),
            "allowed_patterns": self.allowed_patterns,
            "unauthorized_changes": sorted(unauthorized),
        }

    def finish(self, result: dict[str, Any], validation: dict[str, Any]) -> None:
        write_json(self.run_dir / "result.json", result)
        write_json(self.run_dir / "validation.json", validation)
        write_text(self.run_dir / "stdout.log", str(result.get("stdout") or ""))
        write_text(self.run_dir / "stderr.log", str(result.get("stderr") or ""))


def begin_specialist_run(root: Path, run_dir: Path, allowed_patterns: list[str]) -> SpecialistHarnessRun:
    run_dir.mkdir(parents=True, exist_ok=True)
    return SpecialistHarnessRun(
        root=root,
        run_dir=run_dir,
        allowed_patterns=allowed_patterns,
        before_files=_workspace_snapshot(root, run_dir),
        before_git_status=_git_status_paths(root),
    )


class ExclusiveRunLock:
    def __init__(self, path: Path, purpose: str):
        self.path = path
        self.purpose = purpose
        self.handle = None

    def __enter__(self) -> "ExclusiveRunLock":
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.seek(0)
            owner = self.handle.read().strip()
            self.handle.close()
            self.handle = None
            raise ValidationFailure(
                f"{self.purpose} is already running"
                + (f" ({owner})" if owner else "")
            ) from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(json.dumps({"pid": os.getpid(), "purpose": self.purpose, "started_at": utc_now_iso()}))
        self.handle.flush()
        os.fsync(self.handle.fileno())
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.handle:
            return
        import fcntl

        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None
