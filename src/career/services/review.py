from __future__ import annotations

from pathlib import Path
import re
import subprocess

import review_output as legacy_review_output

from career.paths import ROOT
from career.cells.capabilities import (
    canonical_python_executable,
    canonical_subprocess_environment,
)
from career.schemas.review import CvPolishReportSchema, CvReviewReportSchema
from career.services.database import Database
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.artifact_repository import ArtifactRecord, ArtifactRepository
from career.services.persistence.gate_repository import GateReceipt, GateRepository
from career.utils import sha256_file, write_json


ARTIFICIAL_ENGLISH_TERMS = {
    "experimentation": "experimentação / testes controlados",
    "data-driven decision making": "tomada de decisão orientada por dados",
    "cross-functional leadership": "liderança transversal",
    "operational excellence": "excelência operacional",
    "decision automation": "automação de decisões",
    "process governance": "governança de processos",
}

NATURAL_PT_BR_TERMS = {
    "SQL",
    "Python",
    "S&OP",
    "OTIF",
    "WMS",
    "MRP",
    "DRP",
    "Power BI",
    "Salesforce",
    "pricing",
    "pipeline",
    "stakeholders",
    "growth",
    "roadmap",
    "startup",
    "SaaS",
    "CSAT",
    "NPS",
}


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _term_in_text(term: str, text: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9&+./# -]+", term):
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE) is not None
    return term.casefold() in text.casefold()


def polish_cv(
    artifact: Path,
    report_path: Path,
    *,
    review_report: dict | None = None,
) -> dict:
    lines = legacy_review_output.compact_lines(legacy_review_output.docx_text(artifact))
    is_pt_br = legacy_review_output.is_portuguese_cv(artifact)
    prose_lines = legacy_review_output.extract_summary_experience_lines(lines) if is_pt_br else []
    prose_text = "\n".join(prose_lines)
    blockers = []
    terms_replaced: list[str] = []
    terms_kept: list[str] = []
    registry_required: list[str] = []
    notes: list[str] = []

    if not artifact.exists():
        blockers.append("artifact_missing")
    if is_pt_br:
        for term, preferred in ARTIFICIAL_ENGLISH_TERMS.items():
            if _term_in_text(term, prose_text):
                blockers.append(f"artificial_english_term:{term}")
                registry_required.append(term)
                notes.append(f"Replacement required before approval: {term} -> {preferred}")
        for term in NATURAL_PT_BR_TERMS:
            if _term_in_text(term, prose_text):
                terms_kept.append(term)
    else:
        notes.append("Non PT-BR CV; editorial polish gate recorded as not applicable.")

    top8 = (review_report or {}).get("top8_keywords", [])
    for item in top8:
        keyword = str(item.get("keyword", "")).strip()
        matched = str(item.get("matched_variant") or "").strip()
        if item.get("coverage_class") == "covered_similar" and matched and matched.casefold() != keyword.casefold():
            registry_required.append(f"{keyword} -> {matched}")

    payload = {
        "artifact_path": str(artifact),
        "language": "pt-BR" if is_pt_br else "non-pt-BR",
        "polish_executed": True,
        "changed": False,
        "sections_reviewed": ["Resumo", "Experiência"] if is_pt_br else [],
        "english_terms_replaced": _dedupe(terms_replaced),
        "english_terms_kept": _dedupe(terms_kept),
        "translation_registry_updates_required": _dedupe(registry_required),
        "translation_registry_updates_applied": [],
        "rerun_required": False,
        "approval_blockers": _dedupe(blockers),
        "notes": notes,
    }
    CvPolishReportSchema(payload).validate()
    write_json(report_path, payload)
    return payload


def review_cv(
    artifact: Path,
    fit_map_path: Path,
    registry_path: Path,
    report_path: Path,
    *,
    translation_registry_path: Path,
    control_db_path: Path | None = None,
) -> dict:
    """Run the objective review against the exact rendered DOCX revision."""
    fit_map = legacy_review_output.read_json(fit_map_path)
    registry = legacy_review_output.read_json(registry_path)
    report = legacy_review_output.build_cv_review(
        artifact,
        fit_map,
        registry,
        Path(translation_registry_path),
        cellular_db_path=control_db_path,
    )
    CvReviewReportSchema(report).validate()
    write_json(report_path, report)
    return report


def record_approved_cv_provenance(
    *,
    artifact: Path,
    report_path: Path,
    application_id: str,
    source_revision_id: str,
    run_id: str,
    database: Database,
) -> ArtifactRecord:
    """Publish a CV only after the objective report approved that exact file.

    The report is evidence, not a receipt.  This function creates the immutable
    artifact provenance, records the SQLite gate receipt, and then attaches that
    receipt to the artifact in that order.
    """
    artifact = Path(artifact).resolve()
    report_path = Path(report_path).resolve()
    if not artifact.is_file():
        raise ValueError("artifact path must exist before review provenance is recorded")
    if not report_path.is_file():
        raise ValueError("review report path must exist before review provenance is recorded")
    report = legacy_review_output.read_json(report_path)
    CvReviewReportSchema(report).validate()
    if report.get("kind") != "cv":
        raise ValueError("review provenance only supports cv reports")
    if report.get("approved_for_delivery") is not True:
        raise ValueError("approved review report is required before publishing artifact")
    if Path(str(report["artifact"])).resolve() != artifact:
        raise ValueError("approved review report points to a different artifact path")
    reviewed_artifact_hash = _required_reviewed_artifact_hash(report)
    if reviewed_artifact_hash != sha256_file(artifact):
        raise ValueError(
            "approved review report artifact_sha256 does not match current artifact bytes"
        )

    application = ApplicationRepository(database).resolve(application_id=application_id)
    artifacts = ArtifactRepository(database)
    artifact_record = artifacts.register(
        application.application_id,
        "cv",
        artifact,
        None,
        source_revision_id,
        run_id,
    )
    receipt_id = GateRepository(database).record(
        GateReceipt(
            application_id=application.application_id,
            application_fingerprint=str(application.fingerprint or ""),
            run_id=run_id,
            gate="cv_review_passed",
            validator="cv.review",
            input_hash=sha256_file(artifact),
            output_hash=sha256_file(report_path),
            revision_id=source_revision_id,
        )
    )
    return artifacts.mark_review_passed(
        artifact_record.artifact_id,
        receipt_id=receipt_id,
        report_path=report_path,
    )


def _required_reviewed_artifact_hash(report: dict) -> str:
    value = report.get("artifact_sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("approved review report artifact_sha256 is required")
    return value


def approve_cv(
    artifact: Path,
    fit_map_path: Path,
    registry_path: Path,
    report_path: Path,
    polish_report_path: Path | None = None,
    *,
    translation_registry_path: Path,
    control_db_path: Path | None = None,
) -> dict:
    command = [
        str(canonical_python_executable()),
        str((ROOT / "scripts/register_keywords.py").resolve()),
        "--fit-map",
        str(fit_map_path),
        "--cv",
        str(artifact),
        "--registry",
        str(registry_path),
        "--translation-registry",
        str(translation_registry_path),
        "--translation-candidates",
        str(registry_path.with_name("keyword_translation_candidates.json")),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=canonical_subprocess_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(
            "Keyword registration failed before CV review.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    report = review_cv(
        artifact,
        fit_map_path,
        registry_path,
        report_path,
        translation_registry_path=translation_registry_path,
        control_db_path=control_db_path,
    )
    polish_path = polish_report_path or report_path.with_name("polish_review.json")
    polish = polish_cv(artifact, polish_path, review_report=report)
    if polish.get("approval_blockers"):
        raise SystemExit(
            "CV polish gate failed; artifact is not approved for delivery.\n"
            f"Report: {polish_path}\n"
            "Blockers: "
            f"{', '.join(polish.get('approval_blockers', []))}"
        )
    report["_approval_meta"] = {
        "artifact_sha256": sha256_file(artifact),
        "fit_map_sha256": sha256_file(fit_map_path),
        "registry_sha256": sha256_file(registry_path),
        "polish_report": str(polish_path),
        "polish_report_sha256": sha256_file(polish_path),
    }
    write_json(report_path, report)
    if not report.get("approved_for_delivery"):
        totals = report.get("totals", {})
        blockers = report.get("blockers", [])
        blocker_ids = [item.get("id", "<unknown>") for item in blockers]
        raise SystemExit(
            "CV review failed; artifact is not approved for delivery.\n"
            f"Report: {report_path}\n"
            "Blocker checks: "
            f"{totals.get('weight_total_passed')}/{totals.get('weight_total_total')}\n"
            "ATS top8: "
            f"{report.get('ats_policy', {}).get('top8', {}).get('score')}/"
            f"{report.get('ats_policy', {}).get('top8', {}).get('score_max')}\n"
            "Minor checks: "
            f"{totals.get('minor_passed')}/{totals.get('minor_total')}\n"
            "Blockers: "
            f"{', '.join(blocker_ids) if blocker_ids else 'none'}"
        )
    return report
