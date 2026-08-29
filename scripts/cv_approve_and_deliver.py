#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import bootstrap


ROOT = bootstrap()
from career.services import application_context
DEFAULT_DELIVERY_REPORT = ROOT / "outputs" / "_tmp" / "delivery_report.json"
DEFAULT_COMBINED_REPORT = ROOT / "outputs" / "_tmp" / "cv_deliver_report.json"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run(command: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _scoped_path(value: str | None, canonical: Path, *, label: str) -> Path:
    """Resolve an optional argument without allowing a global compatibility path."""
    if value is None:
        return canonical
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    if candidate != canonical.resolve():
        raise ValueError(
            f"{label} must be scoped to the application: {canonical.relative_to(ROOT)}"
        )
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve a CV and deliver it to OneDrive only if approved.")
    parser.add_argument("--artifact", required=True, help="Final CV artifact in outputs/, for example outputs/cv.docx")
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--fit-map")
    parser.add_argument("--registry")
    parser.add_argument("--review-report")
    parser.add_argument("--polish-report")
    parser.add_argument("--delivery-report", default=str(DEFAULT_DELIVERY_REPORT))
    parser.add_argument("--combined-report", default=str(DEFAULT_COMBINED_REPORT))
    parser.add_argument("--dry-run", action="store_true", help="Run approval and rclone delivery dry-run.")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    application_paths = application_context.paths_for(args.application_id)
    fit_map = _scoped_path(args.fit_map, application_paths.fit_map, label="--fit-map")
    registry = _scoped_path(
        args.registry,
        application_paths.derived_dir / "keyword_ats_registry.json",
        label="--registry",
    )
    review_report = _scoped_path(
        args.review_report, application_paths.cv_review_report, label="--review-report"
    )
    polish_report = _scoped_path(
        args.polish_report, application_paths.polish_review, label="--polish-report"
    )

    artifact = Path(args.artifact)
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    artifact = artifact.absolute()

    delivery_report = Path(args.delivery_report)
    if not delivery_report.is_absolute():
        delivery_report = ROOT / delivery_report
    combined_report = Path(args.combined_report)
    if not combined_report.is_absolute():
        combined_report = ROOT / combined_report

    payload = {
        "status": "pending",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "artifact": rel(artifact),
        "artifact_exists": artifact.exists(),
        "review_report": rel(review_report),
        "polish_report": rel(polish_report),
        "delivery_report": rel(delivery_report),
        "dry_run": args.dry_run,
    }

    if not artifact.exists() or not artifact.is_file():
        payload.update({"status": "failed", "error": "artifact_not_found"})
        write_report(combined_report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    approve_command = [
        sys.executable,
        "scripts/career_cli.py",
        "cv",
        "approve",
        "--artifact",
        rel(artifact),
        "--application-id",
        args.application_id,
        "--fit-map",
        rel(fit_map),
        "--registry",
        rel(registry),
        "--report",
        rel(review_report),
        "--polish-report",
        rel(polish_report),
    ]
    approval = run(approve_command, timeout=args.timeout)
    payload["approval"] = {
        "command": " ".join(approve_command),
        "returncode": approval.returncode,
        "stdout": approval.stdout[-4000:],
        "stderr": approval.stderr[-4000:],
    }

    if approval.returncode != 0:
        payload.update({"status": "failed", "error": "cv_approval_failed"})
        write_report(combined_report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return approval.returncode or 3

    report = read_json(review_report)
    polish = read_json(polish_report) if polish_report.exists() else {}
    payload["approved_for_delivery"] = bool(report.get("approved_for_delivery"))
    payload["polish_blockers"] = polish.get("approval_blockers", []) if isinstance(polish, dict) else []

    if not payload["approved_for_delivery"] or payload["polish_blockers"]:
        payload.update({"status": "failed", "error": "approval_report_not_deliverable"})
        write_report(combined_report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 4

    deliver_command = [
        sys.executable,
        "scripts/deliver_artifact.py",
        "--file",
        rel(artifact),
        "--report",
        rel(delivery_report),
        "--timeout",
        str(args.timeout),
    ]
    if args.dry_run:
        deliver_command.append("--dry-run")
    delivery = run(deliver_command, timeout=args.timeout)
    payload["delivery"] = {
        "command": " ".join(deliver_command),
        "returncode": delivery.returncode,
        "stdout": delivery.stdout[-4000:],
        "stderr": delivery.stderr[-4000:],
    }

    if delivery.returncode != 0:
        payload.update({"status": "failed", "error": "artifact_delivery_failed"})
        write_report(combined_report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return delivery.returncode or 5

    delivery_payload = read_json(delivery_report) if delivery_report.exists() else {}
    payload["delivery_status"] = delivery_payload.get("status")
    payload["destination"] = delivery_payload.get("destination")
    if payload["delivery_status"] not in {"delivered", "dry_run_ok"}:
        payload.update({"status": "failed", "error": "delivery_report_not_successful"})
        write_report(combined_report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 6

    payload["status"] = "approved_and_delivered" if not args.dry_run else "approved_and_delivery_dry_run_ok"
    write_report(combined_report, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
