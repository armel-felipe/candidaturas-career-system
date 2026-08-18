from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3")
SQLITE_DATABASE_NAMES = {"career.db"}
PRESERVED_DIRECTORIES = (
    ".career-state",
    "app/.career-state",
    "outputs",
    "inbox",
    "control-plane",
)
WORKSPACE_PRESERVED_RELATIVE_DIRECTORIES = (
    "inbox",
    "outputs",
    "state/applications_v2",
    "state/applications",
    "state/derived",
    "state/memory",
    "state/agent_requests",
    "state/approvals",
    "state/phase_d_gates",
    "state/pending_actions",
    "state/telegram",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_dump_sha256(path: Path) -> str:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        payload = "\n".join(connection.iterdump()).encode("utf-8")
    finally:
        connection.close()
    return hashlib.sha256(payload).hexdigest()


def _is_sqlite_file(path: Path) -> bool:
    if path.suffix in SQLITE_SUFFIXES:
        return True
    return path.name.endswith((".db-wal", ".db-shm"))


def _relative_to(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _discover_sqlite_databases(root: Path) -> list[Path]:
    databases: list[Path] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix not in SQLITE_SUFFIXES:
            continue
        if candidate.name not in SQLITE_DATABASE_NAMES:
            continue
        databases.append(candidate)
    return sorted(databases)


def _discover_preserved_directories(root: Path) -> list[Path]:
    directories: list[Path] = []
    for relative in PRESERVED_DIRECTORIES:
        candidate = root / relative
        if candidate.exists() and candidate.is_dir():
            directories.append(candidate)
    workspaces_root = root / "workspaces"
    if workspaces_root.exists() and workspaces_root.is_dir():
        for workspace_dir in sorted(path for path in workspaces_root.iterdir() if path.is_dir()):
            for relative in WORKSPACE_PRESERVED_RELATIVE_DIRECTORIES:
                candidate = workspace_dir / relative
                if candidate.exists() and candidate.is_dir():
                    directories.append(candidate)
    return directories


def _iter_preserved_files(root: Path, directory: Path, destination: Path) -> list[Path]:
    files: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if destination == path or destination in path.parents:
            continue
        if _is_sqlite_file(path):
            continue
        files.append(path)
    return sorted(files)


def _directory_digest(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size_bytes"]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _build_report(root: Path, destination: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    resolved_destination = destination.resolve()

    sqlite_backups: list[dict[str, Any]] = []
    for source_db in _discover_sqlite_databases(resolved_root):
        backup_relative = Path("sqlite") / _relative_to(source_db, resolved_root)
        sqlite_backups.append(
            {
                "source": _relative_to(source_db, resolved_root),
                "source_sha256": _sqlite_dump_sha256(source_db),
                "backup": backup_relative.as_posix(),
            }
        )

    preserved_directories: list[dict[str, Any]] = []
    preserved_files: list[dict[str, Any]] = []
    for source_dir in _discover_preserved_directories(resolved_root):
        backup_relative_dir = Path("files") / _relative_to(source_dir, resolved_root)
        directory_files: list[dict[str, Any]] = []
        for source_file in _iter_preserved_files(
            resolved_root, source_dir, resolved_destination
        ):
            file_entry = {
                "path": _relative_to(source_file, resolved_root),
                "backup_path": (
                    Path("files") / _relative_to(source_file, resolved_root)
                ).as_posix(),
                "sha256": _file_sha256(source_file),
                "size_bytes": source_file.stat().st_size,
            }
            directory_files.append(file_entry)
            preserved_files.append(file_entry)
        preserved_directories.append(
            {
                "source": _relative_to(source_dir, resolved_root),
                "backup": backup_relative_dir.as_posix(),
                "file_count": len(directory_files),
                "sha256": _directory_digest(directory_files),
            }
        )

    report = {
        "root": str(resolved_root),
        "destination": str(resolved_destination),
        "generated_at": datetime.now(UTC).isoformat(),
        "sqlite_backups": sqlite_backups,
        "preserved_directories": preserved_directories,
        "preserved_files": preserved_files,
        "summary": {
            "sqlite_database_count": len(sqlite_backups),
            "preserved_directory_count": len(preserved_directories),
            "preserved_file_count": len(preserved_files),
        },
    }
    return report


def _ensure_destination_ready(destination: Path) -> None:
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Backup destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise ValueError(f"Backup destination must be empty: {destination}")
    else:
        destination.mkdir(parents=True, exist_ok=True)


def _copy_preserved_files(root: Path, destination: Path, report: dict[str, Any]) -> None:
    for file_entry in report["preserved_files"]:
        source_path = root / file_entry["path"]
        backup_path = destination / file_entry["backup_path"]
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, backup_path)


def _backup_sqlite_databases(root: Path, destination: Path, report: dict[str, Any]) -> None:
    for sqlite_entry in report["sqlite_backups"]:
        source_path = root / sqlite_entry["source"]
        backup_path = destination / sqlite_entry["backup"]
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source_connection = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
        target_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        sqlite_entry["backup_sha256"] = _sqlite_dump_sha256(backup_path)


def create_backup(root: Path, destination: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    resolved_destination = destination.resolve()
    report = _build_report(resolved_root, resolved_destination)

    _ensure_destination_ready(resolved_destination)
    _backup_sqlite_databases(resolved_root, resolved_destination, report)
    _copy_preserved_files(resolved_root, resolved_destination, report)

    manifest_path = resolved_destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a restorable persistence backup baseline"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = _build_report(args.root.resolve(), args.destination.resolve())
    if args.dry_run:
        payload = {
            "status": "dry_run",
            "destination": report["destination"],
            "sqlite_database_count": report["summary"]["sqlite_database_count"],
            "preserved_directory_count": report["summary"]["preserved_directory_count"],
            "preserved_file_count": report["summary"]["preserved_file_count"],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    result = create_backup(args.root, args.destination)
    payload = {
        "status": "created",
        "destination": result["destination"],
        "manifest": str((args.destination.resolve() / "manifest.json")),
        "sqlite_database_count": result["summary"]["sqlite_database_count"],
        "preserved_directory_count": result["summary"]["preserved_directory_count"],
        "preserved_file_count": result["summary"]["preserved_file_count"],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
