#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE
from career.services.application_context import validate_application_id
from career.utils import read_json, utc_now_iso


MIGRATION_MANIFEST = "cellular_migration_manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_sources(application_dir: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in sorted(application_dir.iterdir()):
        if not path.is_file() or path.name == MIGRATION_MANIFEST:
            continue
        sources.append(
            {
                "source_path": str(path.relative_to(application_dir)),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return sources


def _cv_review_status(application_dir: Path) -> tuple[str, str]:
    docx_files = sorted(application_dir.glob("*.docx"))
    if not docx_files:
        return "blocked", "legacy_cv_artifact_missing"
    review_path = application_dir / "cv_review_report.json"
    polish_path = application_dir / "polish_review.json"
    if not review_path.is_file() or not polish_path.is_file():
        return "blocked", "legacy_cv_review_unknown_or_unapproved"
    try:
        review = read_json(review_path)
        polish = read_json(polish_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return "blocked", "legacy_cv_review_unknown_or_unapproved"
    reviewed_artifact = str(review.get("artifact") or "")
    artifact_matches = any(
        reviewed_artifact in {str(path), path.name, str(path.resolve())}
        for path in docx_files
    )
    explicitly_approved = (
        review.get("approved") is True
        and review.get("approved_for_delivery") is True
        and artifact_matches
        and isinstance(polish.get("approval_blockers"), list)
        and not polish["approval_blockers"]
    )
    if explicitly_approved:
        return "validated", "legacy_explicit_review_receipts"
    return "blocked", "legacy_cv_review_unknown_or_unapproved"


def _node_records(application_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    records: list[dict[str, str]] = []
    blockers: list[str] = []
    candidates = (
        ("capture_source", "job_description.md", "source_artifact_hash_only"),
        ("analyze_fit", "fit_map.json", "source_artifact_hash_only"),
        ("compose_cv", "cv_content.json", "source_artifact_hash_only"),
    )
    for node_id, file_name, origin in candidates:
        status = "imported_unvalidated" if (application_dir / file_name).is_file() else "blocked"
        records.append(
            {
                "node_id": node_id,
                "status": status,
                "source_path": file_name,
                "validation_origin": origin,
            }
        )
    review_status, review_origin = _cv_review_status(application_dir)
    for node_id in ("render_cv", "review_cv"):
        records.append(
            {
                "node_id": node_id,
                "status": review_status,
                "source_path": "*.docx",
                "validation_origin": review_origin,
            }
        )
    if review_status != "validated":
        blockers.append(review_origin)
    return records, blockers


def migrate_application(
    application_dir: str | Path,
    *,
    application_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Inventory legacy files without rewriting them or inventing validation."""
    application_id = validate_application_id(application_id)
    app_dir = Path(application_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"legacy application directory not found: {app_dir}")
    manifest_path = app_dir / MIGRATION_MANIFEST
    sources = _legacy_sources(app_dir)
    nodes, blockers = _node_records(app_dir)
    imported_nodes = {item["node_id"]: item["status"] for item in nodes}
    payload = {
        "kind": "cellular_legacy_import_manifest",
        "version": 1,
        "application_id": application_id,
        "legacy_application_dir": str(app_dir),
        "source_artifacts": sources,
        "nodes": nodes,
        "blockers": blockers,
        "migration_policy": {
            "source_artifacts_rewritten": False,
            "validation_fabricated": False,
            "unknown_cv_review": "blocked",
        },
        "created_at": utc_now_iso(),
    }
    result = {
        "status": "dry_run" if dry_run else "migrated",
        "application_id": application_id,
        "manifest_path": str(manifest_path),
        "imported_nodes": imported_nodes,
        "blockers": blockers,
        "source_artifact_count": len(sources),
    }
    if dry_run:
        return result
    if manifest_path.exists():
        existing = read_json(manifest_path)
        if (
            existing.get("application_id") != application_id
            or existing.get("source_artifacts") != sources
        ):
            raise RuntimeError("existing cellular migration manifest does not match legacy sources")
        result["status"] = "already_migrated"
        return result
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--application-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    application_dir = Path(args.application_dir) if args.application_dir else (
        CAREER_STATE / "applications_v2" / args.application_id
    )
    print(
        json.dumps(
            migrate_application(
                application_dir,
                application_id=args.application_id,
                dry_run=args.dry_run,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
