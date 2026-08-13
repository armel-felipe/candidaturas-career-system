from __future__ import annotations

import hashlib
import json
import os
import fnmatch
import sqlite3
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
    before_workspace_files: dict[str, str]
    allowed_workspace_changes: tuple[str, ...] = ()

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
        ]
        after_workspace = _protected_workspace_snapshot(
            self.root, self.application_dir
        )
        unauthorized_workspace = sorted(
            path
            for path in set(self.before_workspace_files) | set(after_workspace)
            if self.before_workspace_files.get(path) != after_workspace.get(path)
            and path not in self.allowed_workspace_changes
        )
        return {
            "status": "blocked" if unauthorized or unauthorized_workspace else "ok",
            "changed_files": changed,
            "allowed_outputs": sorted(
                str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
                for path in self.allowed_outputs
            ),
            "unauthorized_changes": unauthorized,
            "unauthorized_workspace_changes": unauthorized_workspace,
        }

    def finish(self, result: dict[str, Any], validation: dict[str, Any]) -> None:
        write_json(self.run_dir / "result.json", result)
        write_json(self.run_dir / "validation.json", validation)
        write_text(self.run_dir / "stdout.log", str(result.get("stdout") or ""))
        write_text(self.run_dir / "stderr.log", str(result.get("stderr") or ""))

    def _snapshot_application_files(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        immutable_run_controls = {"request.json", "request.md", "manifest.json"}
        for path in self.application_dir.rglob("*"):
            if not path.is_file():
                continue
            if self.run_dir in path.parents and path.name not in immutable_run_controls:
                continue
            snapshot[str(path.relative_to(self.application_dir))] = _file_hash(path)
        return snapshot


class HarnessRunStore:
    def __init__(self, root: Path, application_dir: Path):
        self.root = root
        self.application_dir = application_dir

    def begin(
        self,
        stage: str,
        request_json: Path,
        request_md: Path,
        *,
        allowed_workspace_changes: tuple[str, ...] = (),
    ) -> HarnessRun:
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
            before_workspace_files={},
            allowed_workspace_changes=allowed_workspace_changes,
        )
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
        run.before_files = run._snapshot_application_files()
        run.before_workspace_files = _protected_workspace_snapshot(
            self.root, self.application_dir
        )
        return run


def _protected_workspace_snapshot(root: Path, application_dir: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    root = root.resolve()
    application_dir = application_dir.resolve()
    ignored_names = {"career.db", "career.db-wal", "career.db-shm"}
    for relative_root in (".career-state", "outputs"):
        base = root / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            resolved = path.resolve()
            if (
                not resolved.is_file()
                or resolved.name in ignored_names
                or resolved.is_relative_to(application_dir)
            ):
                continue
            snapshot[str(resolved.relative_to(root))] = _file_hash(resolved)
    snapshot.update(_protected_database_snapshot(root))
    return snapshot


def _protected_database_snapshot(root: Path) -> dict[str, str]:
    database_path = root.resolve() / ".career-state" / "career.db"
    if not database_path.is_file():
        return {}
    snapshot: dict[str, str] = {}
    connection = sqlite3.connect(
        f"file:{database_path}?mode=ro", uri=True, timeout=2.0
    )
    try:
        schema_rows = sorted(
            (
                tuple(row)
                for row in connection.execute(
                    """SELECT type, name, tbl_name, sql FROM sqlite_master
                       WHERE name NOT LIKE 'sqlite_%'
                       ORDER BY type, name"""
                ).fetchall()
            ),
            key=repr,
        )
        snapshot[".career-state/career.db::schema"] = hashlib.sha256(
            json.dumps(schema_rows, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        tables = sorted(
            str(row[0])
            for row in connection.execute(
                """SELECT name FROM sqlite_master
                   WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"""
            )
        )
        normalized_queries = {
            # Only renewal timestamps may move while the specialist is alive.
            "workspace_leases": (
                "SELECT lease_name, worker_id, run_id, lease_epoch, acquired_at "
                "FROM workspace_leases"
            ),
            "resource_locks": (
                "SELECT resource_name, worker_id, lease_id, acquired_at "
                "FROM resource_locks"
            ),
            "cell_nodes": (
                "SELECT run_id, node_id, status, requires_json, reserved_by, "
                "latest_attempt, created_at FROM cell_nodes"
            ),
        }
        for table in tables:
            quoted = table.replace('"', '""')
            query = normalized_queries.get(table, f'SELECT * FROM "{quoted}"')
            rows = sorted(
                (tuple(row) for row in connection.execute(query).fetchall()),
                key=repr,
            )
            encoded = json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
            snapshot[f".career-state/career.db::{table}"] = hashlib.sha256(
                encoded
            ).hexdigest()
    except sqlite3.Error as exc:
        snapshot[".career-state/career.db::integrity"] = (
            f"error:{type(exc).__name__}:{exc}"
        )
    finally:
        connection.close()
    return snapshot


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
