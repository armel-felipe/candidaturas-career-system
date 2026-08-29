"""Persist evidence produced by the cellular application pipeline.

Cell execution stores immutable attempt artifacts, while the application
projection reads the canonical SQLite lineage tables.  This module is the
explicit bridge between those two layers.  It never promotes a failed cell or
an unverified external receipt.
"""

from __future__ import annotations

import json
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.paths import ROOT
from career.services import fit_map as fit_map_service
from career.services.application_context import build_application_projection
from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.utils import json_fingerprint, read_json, sha256_file, utc_now_iso, write_json


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
def intake_texts_equivalent(left: str, right: str) -> bool:
    """Return true only when the intake difference is its extraction timestamp."""
    pattern = re.compile(r"(?im)^(Extraído em:\s*).*$")
    normalized_left = pattern.sub(r"\1<TIMESTAMP>", str(left))
    normalized_right = pattern.sub(r"\1<TIMESTAMP>", str(right))
    return normalized_left == normalized_right


def align_application_intake(
    *,
    database: Database,
    application_id: str,
    refreshed_text: str,
) -> str:
    """Create a new current intake revision for a timestamp-only refresh.

    The original application ID and prior job description remain intact.  The
    operation is deliberately narrow: a refreshed source is accepted only if
    its normalized content is byte-for-byte equivalent apart from the
    extraction timestamp.
    """
    database.migrate()
    applications = ApplicationRepository(database)
    application = applications.resolve(application_id=application_id)
    current = applications.get_latest_job_description(application_id)
    refreshed_text = str(refreshed_text)
    if not intake_texts_equivalent(current.content, refreshed_text):
        raise ValueError("refreshed intake is not equivalent apart from extraction timestamp")
    refreshed_hash = hashlib.sha256(refreshed_text.encode("utf-8")).hexdigest()
    if refreshed_hash == current.content_hash:
        return applications.get_current_revision_id(application_id) or ""

    now = utc_now_iso()
    source_id = f"source_{uuid4().hex}"
    description_id = f"job_{uuid4().hex}"
    revision_id = f"rev_{uuid4().hex}"
    source_metadata = {
        "source_type": application.source_type,
        "source_url": application.source_url,
        "refreshed_from_description_id": current.description_id,
        "equivalence": "extraction_timestamp_only",
    }
    source_metadata_json = json.dumps(source_metadata, sort_keys=True, separators=(",", ":"))
    revision_payload = {
        "job_description_id": description_id,
        "job_source_id": source_id,
        "job_description_hash": refreshed_hash,
        "job_description_path": application.job_description_path,
        "source_type": application.source_type,
        "source_url": application.source_url,
        "source_metadata_hash": hashlib.sha256(source_metadata_json.encode("utf-8")).hexdigest(),
    }
    with database.transaction(immediate=True) as conn:
        conn.execute(
            """INSERT INTO job_sources
               (source_id, application_id, source_type, source_url, fingerprint,
                metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id,
                application_id,
                application.source_type,
                application.source_url,
                refreshed_hash,
                source_metadata_json,
                now,
            ),
        )
        conn.execute(
            """INSERT INTO job_descriptions
               (description_id, application_id, source_id, language, content,
                content_hash, created_at)
               VALUES (?, ?, ?, NULL, ?, ?, ?)""",
            (description_id, application_id, source_id, refreshed_text, refreshed_hash, now),
        )
        conn.execute(
            """INSERT INTO application_revisions
               (revision_id, application_id, revision_kind, fingerprint, source_hash,
                payload_json, created_at)
               VALUES (?, ?, 'job_description', ?, ?, ?, ?)""",
            (
                revision_id,
                application_id,
                refreshed_hash,
                refreshed_hash,
                json.dumps(revision_payload, sort_keys=True, separators=(",", ":")),
                now,
            ),
        )
        conn.execute(
            "UPDATE applications SET updated_at = ? WHERE id = ?",
            (now, application_id),
        )
    GateRepository(database).record(
        GateReceipt(
            application_id=application_id,
            application_fingerprint=refreshed_hash,
            run_id=f"intake-refresh-{application_id}-{refreshed_hash[:16]}",
            gate="job_description_saved",
            validator="project.save_job_description",
            input_hash=refreshed_hash,
            output_hash=refreshed_hash,
        )
    )
    return revision_id


def _require_hash(value: str, field: str) -> str:
    value = str(value or "").strip().lower()
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a sha256 hex digest")
    return value


def build_delivery_binding(
    *,
    application_id: str,
    artifact_version_id: str,
    artifact_hash: str,
    source_revision_id: str,
    positioning_revision_id: str | None,
    run_id: str,
    external_report_path: str,
    external_report_hash: str,
    destination: str,
    filename: str,
) -> dict[str, Any]:
    """Build a projection-verifiable receipt around the rclone report."""
    return {
        "status": "delivered",
        "channel": "onedrive",
        "application_id": str(application_id),
        "artifact_version_id": str(artifact_version_id),
        "artifact_hash": _require_hash(artifact_hash, "artifact_hash"),
        "source_revision_id": str(source_revision_id),
        "positioning_revision_id": positioning_revision_id,
        "run_id": str(run_id),
        "destination": str(destination),
        "filename": str(filename),
        "external_report_path": str(external_report_path),
        "external_report_hash": _require_hash(external_report_hash, "external_report_hash"),
    }


def build_notion_binding(
    *,
    application_id: str,
    record_id: str,
    page_id: str,
    url: str,
    artifact_version_id: str,
    artifact_hash: str,
    source_revision_id: str,
    positioning_revision_id: str | None,
    run_id: str,
    external_receipt_path: str,
    external_receipt_hash: str,
) -> dict[str, Any]:
    """Build a projection-verifiable receipt around a Notion page receipt."""
    return {
        "status": "succeeded",
        "application_id": str(application_id),
        "record_id": str(record_id),
        "page_id": str(page_id),
        "url": str(url),
        "artifact_version_id": str(artifact_version_id),
        "artifact_hash": _require_hash(artifact_hash, "artifact_hash"),
        "source_revision_id": str(source_revision_id),
        "positioning_revision_id": positioning_revision_id,
        "run_id": str(run_id),
        "external_receipt_path": str(external_receipt_path),
        "external_receipt_hash": _require_hash(external_receipt_hash, "external_receipt_hash"),
    }


def registry_entry_matches_application(
    entry: dict[str, Any],
    *,
    application_id: str,
    application_company: str,
    application_role: str,
    fit_map: dict[str, Any],
) -> bool:
    """Match a cellular keyword registry entry to the current application.

    New registries may carry the immutable application ID. Older registries
    do not, so their company/role binding must use the current FIT_MAP rather
    than a raw intake title that may include location or employment metadata.
    """
    entry_application_id = str(entry.get("application_id") or "").strip()
    if entry_application_id:
        return entry_application_id == str(application_id).strip()

    expected_company = str(fit_map.get("empresa") or application_company).strip()
    expected_role = str(fit_map.get("cargo") or application_role).strip()
    return (
        str(entry.get("company") or "").strip() == expected_company
        and str(entry.get("role") or "").strip() == expected_role
    )


def reconciliation_cv_language(*, current_language: str | None, job_description: str) -> str:
    """Preserve the canonical job language when projecting a cellular run."""
    if str(job_description or "").strip():
        from career.services.job_language import detect_job_language

        return detect_job_language(job_description)
    return str(current_language or "pt-BR").strip() or "pt-BR"


def reconcile_standard_cv(
    *,
    database: Database,
    application_id: str,
    fit_map_path: Path,
    draft_path: Path,
    cv_path: Path,
    registry_path: Path,
    cv_run_id: str,
    delivery_report_path: Path,
    notion_receipt_path: Path,
    notion_run_id: str,
    state_root: Path,
) -> dict[str, Any]:
    """Import a completed cellular standard-CV run into canonical SQLite.

    All inputs are explicit paths from a completed cellular run.  The function
    re-runs the objective CV review against the host-visible artifact so its
    report path and hash are valid in the authoritative workspace.
    """
    from career.services import review as review_service

    database.migrate()
    application = ApplicationRepository(database).resolve(application_id=application_id)
    fit_map_path = Path(fit_map_path).resolve()
    draft_path = Path(draft_path).resolve()
    cv_path = Path(cv_path).resolve()
    registry_path = Path(registry_path).resolve()
    delivery_report_path = Path(delivery_report_path).resolve()
    notion_receipt_path = Path(notion_receipt_path).resolve()
    for path in (fit_map_path, draft_path, cv_path, registry_path, delivery_report_path, notion_receipt_path):
        if not path.is_file():
            raise ValueError(f"cellular evidence file is missing: {path}")

    fit_map = read_json(fit_map_path)
    job_description_text = ""
    if application.job_description_path:
        try:
            job_description_text = Path(application.job_description_path).read_text(
                encoding="utf-8"
            )
        except OSError:
            job_description_text = ""
    reconciled_cv_language = reconciliation_cv_language(
        current_language=str(application.cv_language or ""),
        job_description=job_description_text,
    )
    provenance = fit_map.get("provenance") if isinstance(fit_map, dict) else None
    job_fingerprint = str((provenance or {}).get("job_fingerprint") or "").strip()
    if job_fingerprint != str(application.fingerprint or ""):
        raise ValueError(
            "cellular FIT_MAP fingerprint does not match the current application intake"
        )
    application_revision_id = ApplicationRepository(database).get_current_revision_id(application_id)
    if not application_revision_id:
        raise ValueError("current application revision is required before cellular reconciliation")

    draft_validation = fit_map_service.validate_draft(draft_path)
    draft_hash = sha256_file(draft_path)
    fit_hash = sha256_file(fit_map_path)
    validated_hash = json_fingerprint(fit_map_service.validate_fit_map(fit_map_path))
    analysis = AnalysisRepository(database)
    gates = GateRepository(database)
    with database.transaction(immediate=True) as conn:
        revision_id = analysis.create_revision(
            application_id,
            fit_map,
            source_hash=fit_hash,
            application_revision_id=application_revision_id,
            conn=conn,
        )
        gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=str(application.fingerprint),
                run_id=cv_run_id,
                gate="fit_map_draft_valid",
                validator="fit_map.validate_draft",
                input_hash=draft_hash,
                output_hash=json_fingerprint(draft_validation),
            ),
            conn=conn,
        )
        gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=str(application.fingerprint),
                run_id=cv_run_id,
                gate="fit_map_built",
                validator="fit_map.build",
                input_hash=draft_hash,
                output_hash=fit_hash,
                revision_id=revision_id,
            ),
            conn=conn,
        )
        gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=str(application.fingerprint),
                run_id=cv_run_id,
                gate="fit_map_scored",
                validator="fit_map.score",
                input_hash=fit_hash,
                output_hash=fit_hash,
                revision_id=revision_id,
            ),
            conn=conn,
        )
        gates.record(
            GateReceipt(
                application_id=application_id,
                application_fingerprint=str(application.fingerprint),
                run_id=cv_run_id,
                gate="fit_map_validated",
                validator="fit_map.validate",
                input_hash=fit_hash,
                output_hash=validated_hash,
                revision_id=revision_id,
            ),
            conn=conn,
        )

    bridge_dir = Path(state_root).resolve() / "applications_v2" / application_id / "reviews" / "cellular_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    delivery = read_json(delivery_report_path)
    if delivery.get("status") != "delivered":
        raise ValueError("external OneDrive report is not delivered")
    destination = str(delivery.get("destination") or "").strip()
    filename = str(delivery.get("filename") or "").strip()
    if not destination or not filename or Path(filename).name != filename:
        raise ValueError("external OneDrive report lacks a safe destination filename")
    output_path = Path(state_root).resolve().parent / "outputs" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and sha256_file(output_path) != sha256_file(cv_path):
        raise ValueError(f"output artifact already exists with different bytes: {output_path}")
    if not output_path.exists():
        shutil.copyfile(cv_path, output_path)
    bridge_registry_path = bridge_dir / f"{cv_run_id}_keyword_ats_registry.json"
    registry = read_json(registry_path)
    applications = registry.get("applications") if isinstance(registry, dict) else None
    if not isinstance(applications, list):
        raise ValueError("cellular keyword registry has no applications list")
    matched_registry_entry = False
    for entry in applications:
        if not isinstance(entry, dict):
            continue
        if registry_entry_matches_application(
            entry,
            application_id=application_id,
            application_company=str(application.company),
            application_role=str(application.role),
            fit_map=fit_map,
        ):
            entry["cv_path"] = str(output_path)
            matched_registry_entry = True
    if not matched_registry_entry:
        raise ValueError("cellular keyword registry lacks this application")
    write_json(bridge_registry_path, registry)
    review_report_path = bridge_dir / f"{cv_run_id}_cv_review.json"
    review_service.review_cv(
        output_path,
        fit_map_path,
        bridge_registry_path,
        review_report_path,
        translation_registry_path=ROOT / ".agents/skills/career-system/references/keyword_translation_registry.json",
        control_db_path=database.db_path,
    )
    artifact = review_service.record_approved_cv_provenance(
        artifact=output_path,
        report_path=review_report_path,
        application_id=application_id,
        source_revision_id=revision_id,
        run_id=cv_run_id,
        database=database,
    )

    delivery_binding = build_delivery_binding(
        application_id=application_id,
        artifact_version_id=artifact.artifact_id,
        artifact_hash=artifact.content_hash,
        source_revision_id=artifact.source_revision_id,
        positioning_revision_id=artifact.positioning_revision_id,
        run_id=artifact.run_id or cv_run_id,
        external_report_path=str(delivery_report_path),
        external_report_hash=sha256_file(delivery_report_path),
        destination=destination,
        filename=filename,
    )
    delivery_binding_path = bridge_dir / f"{cv_run_id}_delivery_binding.json"
    write_json(delivery_binding_path, delivery_binding)
    now = utc_now_iso()
    with database.transaction(immediate=True) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO deliveries
               (delivery_id, application_id, artifact_version_id, channel, target,
                status, report_path, report_hash, payload_json, delivered_at)
               VALUES (?, ?, ?, 'onedrive', ?, 'delivered', ?, ?, ?, ?)""",
            (
                f"cellular-delivery-{cv_run_id}-{artifact.artifact_id}",
                application_id,
                artifact.artifact_id,
                destination,
                str(delivery_binding_path),
                sha256_file(delivery_binding_path),
                json.dumps(delivery_binding, sort_keys=True, separators=(",", ":")),
                now,
            ),
        )

    notion = read_json(notion_receipt_path)
    page_id = str(notion.get("page_id") or "").strip()
    url = str(notion.get("url") or "").strip()
    if str(notion.get("application_id") or "") != application_id or not page_id or not url:
        raise ValueError("external Notion receipt lacks application identity or page URL")
    record_id = f"notion:{page_id}"
    notion_binding = build_notion_binding(
        application_id=application_id,
        record_id=record_id,
        page_id=page_id,
        url=url,
        artifact_version_id=artifact.artifact_id,
        artifact_hash=artifact.content_hash,
        source_revision_id=artifact.source_revision_id,
        positioning_revision_id=artifact.positioning_revision_id,
        run_id=artifact.run_id or cv_run_id,
        external_receipt_path=str(notion_receipt_path),
        external_receipt_hash=sha256_file(notion_receipt_path),
    )
    notion_binding_path = bridge_dir / f"{cv_run_id}_notion_binding.json"
    write_json(notion_binding_path, notion_binding)
    with database.transaction(immediate=True) as conn:
        conn.execute(
            """INSERT INTO notion_records
               (record_id, application_id, notion_page_id, notion_database_id,
                notion_unique_id, notion_url, created_at, updated_at)
               VALUES (?, ?, ?, NULL, NULL, ?, ?, ?)
               ON CONFLICT(application_id) DO UPDATE SET
                 record_id = excluded.record_id,
                 notion_page_id = excluded.notion_page_id,
                 notion_url = excluded.notion_url,
                 updated_at = excluded.updated_at""",
            (record_id, application_id, page_id, url, now, now),
        )
        actual_record = conn.execute(
            "SELECT record_id FROM notion_records WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        if actual_record is None or str(actual_record["record_id"]) != record_id:
            raise ValueError("Notion record binding was not persisted")
        notion_payload = {
            **notion_binding,
            "receipt_path": str(notion_binding_path),
            "receipt_hash": sha256_file(notion_binding_path),
        }
        conn.execute(
            """INSERT OR IGNORE INTO notion_syncs
               (sync_id, application_id, record_id, action, status, payload_json, synced_at)
               VALUES (?, ?, ?, 'cellular_initial_sync', 'succeeded', ?, ?)""",
            (
                f"cellular-notion-{notion_run_id}-{artifact.artifact_id}",
                application_id,
                record_id,
                json.dumps(notion_payload, sort_keys=True, separators=(",", ":")),
                now,
            ),
        )

    projection = build_application_projection(application_id, database)
    if not projection.base_package_sealed:
        raise ValueError(
            f"cellular reconciliation did not seal core package: {projection.stage.value}"
        )
    score = fit_map.get("nota_aderencia", {}).get("final") if isinstance(fit_map.get("nota_aderencia"), dict) else None
    with database.transaction(immediate=True) as conn:
        conn.execute(
            """UPDATE applications
                  SET stage = ?, score = ?, cv_language = ?,
                      fit_map_path = ?, cv_path = ?, notion_id = ?, updated_at = ?
                WHERE id = ?""",
            (
                projection.stage.value,
                float(score) if score is not None else None,
                reconciled_cv_language,
                str(fit_map_path),
                str(output_path),
                page_id,
                now,
                application_id,
            ),
        )
    return {
        "status": "core_package_sealed",
        "application_id": application_id,
        "fit_map_revision_id": revision_id,
        "artifact_version_id": artifact.artifact_id,
        "review_report_path": str(review_report_path),
        "delivery_binding_path": str(delivery_binding_path),
        "notion_binding_path": str(notion_binding_path),
        "notion_page_id": page_id,
        "notion_url": url,
        "score": score,
    }
