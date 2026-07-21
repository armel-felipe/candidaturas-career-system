from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

import review_output as legacy_review_output
from keyword_translation_utils import DEFAULT_TRANSLATION_REGISTRY

from career.paths import ROOT
from career.schemas.review import CvPolishReportSchema, CvReviewReportSchema
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


def review_cv(artifact: Path, fit_map_path: Path, registry_path: Path, report_path: Path) -> dict:
    """Run the objective review against the exact rendered DOCX revision."""
    fit_map = legacy_review_output.read_json(fit_map_path)
    registry = legacy_review_output.read_json(registry_path)
    report = legacy_review_output.build_cv_review(artifact, fit_map, registry, DEFAULT_TRANSLATION_REGISTRY)
    CvReviewReportSchema(report).validate()
    write_json(report_path, report)
    return report


def approve_cv(
    artifact: Path,
    fit_map_path: Path,
    registry_path: Path,
    report_path: Path,
    polish_report_path: Path | None = None,
) -> dict:
    command = [
        sys.executable,
        "scripts/register_keywords.py",
        "--fit-map",
        str(fit_map_path),
        "--cv",
        str(artifact),
        "--registry",
        str(registry_path),
        "--translation-candidates",
        str(registry_path.with_name("keyword_translation_candidates.json")),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(
            "Keyword registration failed before CV review.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    report = review_cv(artifact, fit_map_path, registry_path, report_path)
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
