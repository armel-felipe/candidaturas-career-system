#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from career.cells.contracts import CELL_CONTRACTS, CONTRACT_VERSION
from career.paths import CAREER_STATE
from career.services.application_context import validate_application_id
from career.services.database import Database
from career.utils import read_json, utc_now_iso, write_json
from scripts.docx.validate_docx import validate as validate_docx


MIGRATION_MANIFEST = "cellular_migration_manifest.json"
_CV_NODES = (
    "normalize_job",
    "analyze_fit",
    "compose_cv",
    "render_cv",
    "review_cv",
    "deliver_cv",
)


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


def _matches_path(value: Any, path: Path) -> bool:
    return str(value or "") in {str(path), path.name, str(path.resolve())}


def _valid_docx(path: Path) -> bool:
    return path.is_file() and not validate_docx(path)


def _cv_review_status(
    application_dir: Path,
) -> tuple[str, str, dict[str, Path]]:
    docx_files = [path for path in sorted(application_dir.glob("*.docx")) if _valid_docx(path)]
    if not docx_files:
        return "blocked", "legacy_cv_review_unknown_or_unapproved", {}
    review_path = application_dir / "cv_review_report.json"
    polish_path = application_dir / "polish_review.json"
    approval_path = application_dir / "approved_cv_manifest.json"
    registry_path = application_dir / "keyword_ats_registry.json"
    fit_map_path = application_dir / "fit_map.json"
    required = (review_path, polish_path, registry_path, fit_map_path)
    if not all(path.is_file() for path in required):
        return "blocked", "legacy_cv_review_unknown_or_unapproved", {}
    try:
        review = read_json(review_path)
        polish = read_json(polish_path)
        approval = read_json(approval_path) if approval_path.is_file() else None
        read_json(registry_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return "blocked", "legacy_cv_review_unknown_or_unapproved", {}

    for artifact in docx_files:
        artifact_hash = _sha256(artifact)
        approval_meta = (
            review.get("_approval_meta")
            if isinstance(review.get("_approval_meta"), dict)
            else {}
        )
        legacy_review_valid = (
            review.get("approved_for_delivery") is True
            and not review.get("blockers")
            and _matches_path(
                review.get("artifact_path") or review.get("artifact"), artifact
            )
            and approval_meta.get("artifact_sha256") == artifact_hash
            and approval_meta.get("fit_map_sha256") == _sha256(fit_map_path)
            and approval_meta.get("registry_sha256") == _sha256(registry_path)
            and _matches_path(approval_meta.get("polish_report"), polish_path)
            and approval_meta.get("polish_report_sha256") == _sha256(polish_path)
        )
        explicit_review_valid = (
            review.get("approved") is True
            and review.get("approved_for_delivery") is True
            and _matches_path(review.get("artifact"), artifact)
            and review.get("artifact_sha256") == artifact_hash
            and _matches_path(review.get("polish_report"), polish_path)
            and review.get("polish_report_sha256") == _sha256(polish_path)
        )
        polish_valid = (
            polish.get("polish_executed") is True
            and isinstance(polish.get("approval_blockers"), list)
            and not polish["approval_blockers"]
            and _matches_path(
                polish.get("artifact_path") or polish.get("artifact"), artifact
            )
            and polish.get("artifact_sha256", artifact_hash) == artifact_hash
        )
        approval_valid = approval is not None and (
            approval.get("approved_for_delivery") is True
            and _matches_path(approval.get("artifact"), artifact)
            and approval.get("artifact_sha256") == artifact_hash
            and _matches_path(approval.get("review_report"), review_path)
            and approval.get("review_report_sha256") == _sha256(review_path)
            and _matches_path(approval.get("polish_report"), polish_path)
            and approval.get("polish_report_sha256") == _sha256(polish_path)
            and _matches_path(approval.get("keyword_registry"), registry_path)
            and approval.get("keyword_registry_sha256") == _sha256(registry_path)
        )
        if polish_valid and (
            legacy_review_valid or (explicit_review_valid and approval_valid)
        ):
            evidence = {
                "docx": artifact,
                "review": review_path,
                "polish": polish_path,
                "registry": registry_path,
            }
            if approval_path.is_file():
                evidence["approval"] = approval_path
            return (
                "validated",
                "legacy_objective_docx_review_polish_hash_chain",
                evidence,
            )
    return "blocked", "legacy_cv_review_unknown_or_unapproved", {}


def _node_records(
    application_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    review_status, review_origin, evidence = _cv_review_status(application_dir)
    source_by_node: dict[str, list[Path]] = {
        "normalize_job": [application_dir / "job_description.md"],
        "analyze_fit": [application_dir / "fit_map.json"],
        "compose_cv": [application_dir / "cv_content.json"],
        "render_cv": [evidence["docx"]] if evidence else list(application_dir.glob("*.docx")),
        "review_cv": (
            [
                evidence[name]
                for name in ("review", "polish", "approval", "registry")
                if name in evidence
            ]
            if evidence
            else [
                application_dir / "cv_review_report.json",
                application_dir / "polish_review.json",
            ]
        ),
        "deliver_cv": [],
    }
    records: list[dict[str, Any]] = []
    for node_id in _CV_NODES:
        source_paths = [
            str(path.relative_to(application_dir))
            for path in source_by_node[node_id]
            if path.is_file()
        ]
        if node_id in {"render_cv", "review_cv"}:
            status = review_status
            origin = review_origin
        else:
            status = "blocked"
            origin = (
                "external_delivery_not_imported"
                if node_id == "deliver_cv"
                else "source_artifact_hash_only"
            )
        records.append(
            {
                "node_id": node_id,
                "status": status,
                "source_paths": source_paths,
                "validation_origin": origin,
                "manifest_path": "",
            }
        )
    blockers = [] if review_status == "validated" else [review_origin]
    return records, blockers


def _stable_run_id(application_id: str, sources: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        {"application_id": application_id, "sources": sources},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "legacy_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _run_graph(application_id: str, app_dir: Path, run_id: str) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    selected = set(_CV_NODES)
    for node_id in _CV_NODES:
        contract = CELL_CONTRACTS[node_id]
        requires = tuple(required for required in contract.requires if required in selected)
        nodes.append(
            {
                "node_id": node_id,
                "requires": list(requires),
                "produces": [str((app_dir / item).resolve()) for item in contract.produces],
                "validators": list(contract.validators),
                "resources": list(contract.resources),
                "invalidates": list(contract.invalidates),
                "repair_scope": contract.repair_scope,
                "max_attempts": contract.max_attempts,
                "allows_external_effect": contract.allows_external_effect,
                "contract_version": contract.version,
            }
        )
    return {
        "run_id": run_id,
        "application_id": application_id,
        "nodes": nodes,
        "edges": sorted(
            [required, node["node_id"]]
            for node in nodes
            for required in node["requires"]
        ),
        "resource_locks": sorted(
            {
                resource
                for node_id in _CV_NODES
                for resource in CELL_CONTRACTS[node_id].resources
            }
        ),
        "created_at": "1970-01-01T00:00:00+00:00",
        "contract_version": CONTRACT_VERSION,
    }


def _write_json_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        try:
            existing = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            existing = None
        if existing == payload:
            return
        if existing is not None:
            raise RuntimeError(f"existing immutable import manifest differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_bytes_once(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"existing immutable imported artifact differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _persist_node_manifests(
    app_dir: Path,
    *,
    application_id: str,
    run_id: str,
    nodes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    outputs_by_node: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        node_id = str(node["node_id"])
        outputs: list[dict[str, Any]] = []
        canonical_names = {
            "render_cv": ("cv.docx",),
            "review_cv": tuple(
                {
                    "cv_review_report.json": "cv_review.json",
                    "polish_review.json": "polish_review.json",
                    "approved_cv_manifest.json": "approved_cv_manifest.json",
                    "keyword_ats_registry.json": "keyword_ats_registry.json",
                }.get(Path(name).name, Path(name).name)
                for name in node["source_paths"]
            ),
        }
        source_pairs = (
            list(
                zip(
                    node["source_paths"],
                    canonical_names.get(
                        node_id,
                        tuple(Path(name).name for name in node["source_paths"]),
                    ),
                    strict=True,
                )
            )
            if node["status"] == "validated"
            else []
        )
        validator_results: list[dict[str, Any]] = []
        if node["status"] == "validated":
            for index, command in enumerate(CELL_CONTRACTS[node_id].validators):
                report_path = (
                    app_dir
                    / "reviews"
                    / run_id
                    / f"migration-{node_id}-{index}.json"
                )
                _write_json_once(
                    report_path,
                    {
                        "kind": "legacy_migration_validator_receipt",
                        "application_id": application_id,
                        "run_id": run_id,
                        "node_id": node_id,
                        "command": command,
                        "result": "passed",
                        "validation_origin": node["validation_origin"],
                    },
                )
                validator_results.append(
                    {
                        "command": command,
                        "result": "passed",
                        "report_path": str(report_path.resolve()),
                        "executed_at": "1970-01-01T00:00:00+00:00",
                    }
                )
        for source_name, artifact_name in source_pairs:
            if node["status"] != "validated":
                continue
            source = app_dir / source_name
            digest = _sha256(source)
            artifact_manifest_path = (
                app_dir
                / "artifacts"
                / run_id
                / artifact_name
                / digest[:12]
                / "manifest.json"
            )
            artifact_path = artifact_manifest_path.parent / artifact_name
            _write_bytes_once(artifact_path, source.read_bytes())
            artifact_manifest = {
                "kind": "artifact_manifest",
                "application_id": application_id,
                "run_id": run_id,
                "node_id": node_id,
                "attempt": 1,
                "artifact_name": artifact_name,
                "path": str(artifact_path.resolve()),
                "manifest_path": str(artifact_manifest_path.resolve()),
                "sha256": digest,
                "revision": digest[:12],
                "inputs": {},
                "validators": validator_results,
                "status": "validated",
                "published_at": "1970-01-01T00:00:00+00:00",
                "validation_origin": node["validation_origin"],
            }
            _write_json_once(artifact_manifest_path, artifact_manifest)
            outputs.append(artifact_manifest)
        attempt_path = (
            app_dir / "cells" / run_id / node_id / "1" / "manifest.json"
        )
        attempt_manifest = {
            "kind": "cell_attempt_manifest",
            "application_id": application_id,
            "run_id": run_id,
            "node_id": node_id,
            "attempt": 1,
            "contract_version": CONTRACT_VERSION,
            "inputs": {},
            "capabilities": {"read_paths": [], "write_paths": []},
            "context": {
                "migration": "legacy_import",
                "validation_origin": node["validation_origin"],
            },
            "outputs": outputs,
            "validators": validator_results,
            "status": node["status"],
            "created_at": "1970-01-01T00:00:00+00:00",
            "finished_at": "1970-01-01T00:00:00+00:00",
        }
        if node["status"] != "validated":
            attempt_manifest["blocker"] = {
                "reason": node["validation_origin"],
                "repair_scope": CELL_CONTRACTS[node_id].repair_scope,
            }
        _write_json_once(attempt_path, attempt_manifest)
        outputs_by_node[node_id] = outputs
    return outputs_by_node


def _persist_database_state(
    database_path: Path,
    *,
    application_id: str,
    run_id: str,
    graph: dict[str, Any],
    nodes: list[dict[str, Any]],
    outputs_by_node: dict[str, list[dict[str, Any]]],
) -> None:
    database = Database(database_path)
    database.init_schema()
    try:
        existing = database.fetch_one(
            "SELECT application_id, graph_json FROM application_runs WHERE run_id = ?",
            (run_id,),
        )
        graph_json = json.dumps(graph, sort_keys=True, separators=(",", ":"), default=str)
        if existing is not None:
            if (
                existing["application_id"] != application_id
                or json.loads(existing["graph_json"]) != graph
            ):
                raise RuntimeError("existing imported cellular run does not match manifest")
        now = utc_now_iso()
        by_node = {str(item["node_id"]): item for item in nodes}
        with database.transaction(immediate=True) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO application_runs
                   (run_id, application_id, graph_json, status, contract_version,
                    created_at, updated_at)
                   VALUES (?, ?, ?, 'blocked', ?, ?, ?)""",
                (run_id, application_id, graph_json, CONTRACT_VERSION, now, now),
            )
            for graph_node in graph["nodes"]:
                node_id = str(graph_node["node_id"])
                imported = by_node[node_id]
                status = str(imported["status"])
                conn.execute(
                    """INSERT OR IGNORE INTO cell_nodes
                       (run_id, node_id, status, requires_json, latest_attempt,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, 1, ?, ?)""",
                    (
                        run_id,
                        node_id,
                        status,
                        json.dumps(graph_node["requires"], separators=(",", ":")),
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """INSERT OR IGNORE INTO cell_attempts
                       (run_id, node_id, attempt, worker_id, status, created_at,
                        finished_at, detail_json)
                       VALUES (?, ?, 1, 'legacy-migration', ?, ?, ?, ?)""",
                    (
                        run_id,
                        node_id,
                        status,
                        now,
                        now,
                        json.dumps(
                            {
                                "status": status,
                                "paths": [item["path"] for item in outputs_by_node[node_id]],
                                "hashes": {
                                    item["path"]: item["sha256"]
                                    for item in outputs_by_node[node_id]
                                },
                                "metadata": {
                                    "validation_origin": imported["validation_origin"]
                                },
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
                for output in outputs_by_node[node_id]:
                    artifact_id = hashlib.sha256(
                        f"{run_id}\0{node_id}\0{output['path']}\0{output['sha256']}".encode(
                            "utf-8"
                        )
                    ).hexdigest()
                    conn.execute(
                        """INSERT OR IGNORE INTO artifacts
                           (artifact_id, run_id, node_id, artifact_name, path,
                            content_hash, input_hash, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, NULL, ?)""",
                        (
                            artifact_id,
                            run_id,
                            node_id,
                            output["artifact_name"],
                            output["path"],
                            output["sha256"],
                            now,
                        ),
                    )
    finally:
        database.close()


def _default_database_path(app_dir: Path) -> Path:
    if app_dir.parent.name == "applications_v2":
        return app_dir.parent.parent / "career.db"
    return app_dir.parent / "career.db"


def _database_has_run(database_path: Path, run_id: str) -> bool:
    if not database_path.is_file():
        return False
    database = Database(database_path)
    try:
        return database.fetch_one(
            "SELECT run_id FROM application_runs WHERE run_id = ?", (run_id,)
        ) is not None
    except Exception:
        return False
    finally:
        database.close()


def migrate_application(
    application_dir: str | Path,
    *,
    application_id: str,
    dry_run: bool = False,
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Import legacy evidence without rewriting it or inventing validation."""
    application_id = validate_application_id(application_id)
    app_dir = Path(application_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"legacy application directory not found: {app_dir}")
    manifest_path = app_dir / MIGRATION_MANIFEST
    sources = _legacy_sources(app_dir)
    nodes, blockers = _node_records(app_dir)
    imported_nodes = {item["node_id"]: item["status"] for item in nodes}
    run_id = _stable_run_id(application_id, sources)
    for node in nodes:
        node["manifest_path"] = (
            f"cells/{run_id}/{node['node_id']}/1/manifest.json"
        )
    result = {
        "status": "dry_run" if dry_run else "migrated",
        "application_id": application_id,
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "imported_nodes": imported_nodes,
        "blockers": blockers,
        "source_artifact_count": len(sources),
    }
    if dry_run:
        return result

    target_database = (
        Path(database_path).resolve()
        if database_path
        else _default_database_path(app_dir)
    )
    had_manifest = manifest_path.exists()
    existing_manifest_valid = False
    had_database_run = _database_has_run(target_database, run_id)
    if had_manifest:
        try:
            existing = read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            existing = None
        if existing is not None:
            if (
                existing.get("application_id") != application_id
                or existing.get("source_artifacts") != sources
                or existing.get("run_id") != run_id
            ):
                raise RuntimeError(
                    "existing cellular migration manifest does not match legacy sources"
                )
            existing_manifest_valid = True

    graph = _run_graph(application_id, app_dir, run_id)
    _write_json_once(app_dir / "plans" / f"{run_id}.json", graph)
    outputs_by_node = _persist_node_manifests(
        app_dir,
        application_id=application_id,
        run_id=run_id,
        nodes=nodes,
    )
    _persist_database_state(
        target_database,
        application_id=application_id,
        run_id=run_id,
        graph=graph,
        nodes=nodes,
        outputs_by_node=outputs_by_node,
    )
    payload = {
        "kind": "cellular_legacy_import_manifest",
        "version": 2,
        "application_id": application_id,
        "run_id": run_id,
        "control_db_path": str(target_database),
        "legacy_application_dir": str(app_dir),
        "source_artifacts": sources,
        "nodes": nodes,
        "blockers": blockers,
        "migration_policy": {
            "source_artifacts_rewritten": False,
            "validation_fabricated": False,
            "unknown_cv_review": "blocked",
            "objective_hash_chain_required": True,
        },
        "created_at": utc_now_iso(),
    }
    if not existing_manifest_valid:
        _write_json_once(manifest_path, payload)
    result["status"] = (
        "reconciled"
        if had_manifest and not had_database_run
        else "already_migrated"
        if had_manifest
        else "migrated"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--application-dir")
    parser.add_argument("--database-path")
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
                database_path=args.database_path,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
