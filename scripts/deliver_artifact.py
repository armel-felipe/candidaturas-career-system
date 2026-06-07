#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()
DEFAULT_REPORT = ROOT / "outputs" / "_tmp" / "delivery_report.json"
REQUIRED_BASE_FOLDER = "01_armel/Curriculos/personalizados"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _write_report(report_path: Path, payload: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_remote_path(remote: str, folder: str, filename: str) -> str:
    folder = folder.strip().strip("/")
    if folder:
        return f"{remote}:{folder}/{filename}"
    return f"{remote}:{filename}"


def _normalize_remote_folder(folder: str) -> str:
    cleaned = "/".join(part for part in folder.strip().replace("\\", "/").split("/") if part and part != ".")
    if not cleaned:
        return REQUIRED_BASE_FOLDER
    return cleaned


def _validate_remote_folder(folder: str) -> tuple[bool, str]:
    normalized = _normalize_remote_folder(folder)
    if normalized == REQUIRED_BASE_FOLDER:
        return True, normalized
    if normalized.startswith(REQUIRED_BASE_FOLDER + "/"):
        return True, normalized
    return False, normalized


def deliver(args: argparse.Namespace) -> int:
    _load_env_file(ROOT / ".env")

    artifact = Path(args.file)
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    artifact = artifact.absolute()

    remote = args.remote or os.environ.get("RCLONE_ONEDRIVE_REMOTE", "onedrive")
    requested_folder = args.folder or os.environ.get("RCLONE_ONEDRIVE_DELIVERY_DIR", REQUIRED_BASE_FOLDER)
    folder_allowed, folder = _validate_remote_folder(requested_folder)
    report_path = Path(args.report) if args.report else DEFAULT_REPORT
    if not report_path.is_absolute():
        report_path = ROOT / report_path

    payload = {
        "status": "pending",
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "artifact": _rel_or_abs(artifact),
        "artifact_exists": artifact.exists(),
        "artifact_size_bytes": artifact.stat().st_size if artifact.exists() else None,
        "method": "rclone copyto",
        "remote": remote,
        "required_base_folder": REQUIRED_BASE_FOLDER,
        "requested_folder": requested_folder,
        "folder": folder,
        "dry_run": bool(args.dry_run),
        "timeout_seconds": args.timeout,
        "report": _rel_or_abs(report_path),
    }

    if not folder_allowed:
        payload.update(
            {
                "status": "failed",
                "error": "folder_outside_required_base",
                "hint": "Use only 01_armel/Curriculos/personalizados or a subfolder inside it.",
            }
        )
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 7

    if not artifact.exists() or not artifact.is_file():
        payload.update({"status": "failed", "error": "artifact_not_found"})
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    rclone = shutil.which("rclone")
    if not rclone:
        payload.update(
            {
                "status": "failed",
                "error": "rclone_not_found",
                "hint": "Install rclone and run rclone config on this machine.",
            }
        )
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 3

    destination = _build_remote_path(remote, folder, artifact.name)
    command = [rclone, "copyto", str(artifact), destination]
    if args.dry_run:
        command.append("--dry-run")
    if args.extra_args:
        command.extend(args.extra_args)

    payload["destination"] = destination
    payload["command"] = " ".join(command)

    try:
        result = _run(command, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        payload.update(
            {
                "status": "failed",
                "error": "rclone_timeout",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }
        )
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 4

    payload["returncode"] = result.returncode
    payload["stdout"] = result.stdout[-4000:]
    payload["stderr"] = result.stderr[-4000:]

    if result.returncode != 0:
        payload.update({"status": "failed", "error": "rclone_copy_failed"})
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return result.returncode or 5

    if args.dry_run:
        payload["status"] = "dry_run_ok"
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    check = _run([rclone, "lsf", destination], timeout=args.timeout)
    payload["verify_returncode"] = check.returncode
    payload["verify_stdout"] = check.stdout[-4000:]
    payload["verify_stderr"] = check.stderr[-4000:]
    if check.returncode != 0:
        payload.update({"status": "failed", "error": "rclone_verify_failed"})
        _write_report(report_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return check.returncode or 6

    payload["status"] = "delivered"
    _write_report(report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deliver a generated artifact to OneDrive using rclone.")
    parser.add_argument("--file", required=True, help="Local artifact path, for example outputs/cv.docx")
    parser.add_argument("--remote", help="rclone remote name. Defaults to RCLONE_ONEDRIVE_REMOTE or onedrive.")
    parser.add_argument("--folder", help="Remote folder. Must be 01_armel/Curriculos/personalizados or a subfolder inside it.")
    parser.add_argument("--report", help="Report path. Defaults to outputs/_tmp/delivery_report.json.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args passed to rclone after --")
    args = parser.parse_args()
    if args.extra_args and args.extra_args[0] == "--":
        args.extra_args = args.extra_args[1:]
    return deliver(args)


if __name__ == "__main__":
    raise SystemExit(main())
