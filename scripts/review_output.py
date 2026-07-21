#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from keyword_translation_utils import (
    DEFAULT_TRANSLATION_REGISTRY,
    find_keyword_or_translation_line,
    load_translation_registry,
    normalize_text,
)


DEFAULT_REGISTRY = Path(".career-state/derived/keyword_ats_registry.json")
ATS_TOP8_OPTIMAL_SCORE = 6.2
ATS_TOP8_MINIMUM_SCORE = 5.2
ATS_TOP15_OPTIMAL_SCORE = 9.0
ATS_TOP15_MINIMUM_SCORE = 7.0


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def docx_text(path: Path) -> str:
    if not path.exists():
        return ""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")

    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join(node.text or "" for node in root.findall(".//w:t", ns))


def compact_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_summary_text(lines: list[str]) -> str:
    for marker in ("Resumo", "Summary"):
        try:
            start = lines.index(marker)
            break
        except ValueError:
            continue
    else:
        return ""

    for marker in ("Experiência", "Experience"):
        try:
            end = lines.index(marker)
            break
        except ValueError:
            continue
    else:
        end = len(lines)

    if end <= start + 1:
        return ""
    return " ".join(lines[start + 1 : end]).strip()


def review_filename(path: Path) -> bool:
    return bool(re.fullmatch(r"felipe_armel_cv_[a-z0-9_]+_[a-z0-9_]+(?:_en)?\.docx", path.name))


def application_key(company: str, role: str) -> tuple[str, str]:
    def slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

    return slug(company), slug(role)


def find_application(registry: dict, company: str, role: str) -> dict | None:
    company_key, role_key = application_key(company, role)
    desired = f"{company_key}__{role_key}"
    for application in registry.get("applications", []):
        if application.get("application_key") == desired:
            return application
    return None


def find_line_with_keyword(lines: list[str], keyword: str) -> str | None:
    token = keyword.casefold()
    for line in lines:
        if token in line.casefold():
            return line
    return None


def is_portuguese_cv(path: Path) -> bool:
    return not path.name.endswith("_en.docx")


def english_cv_has_portuguese_role_titles(lines: list[str]) -> tuple[bool, str]:
    suspects = []
    patterns = [
        r"\bHead de Opera(?:ç|c)ões\b",
        r"\bDiretor de Opera(?:ç|c)ões\b",
        r"\bGerente de Planejamento Comercial e Opera(?:ç|c)ões\b",
        r"\bGerente de Customer Success\b",
        r"\bCoordenador(?:a)? de S&OP\b",
        r"\bCoordenador(?:a)? de Intelig[êe]ncia Comercial\b",
        r"\bCoordenador(?:a)? de Planejamento de Materiais\b",
        r"\bCoordenador(?:a)? de Expedi(?:ç|c)[aã]o\b",
        r"\bAnalista de Processos e Sistemas\b",
        r"\bOperador de Produ(?:ç|c)[aã]o\b",
    ]
    for line in lines:
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                suspects.append(line)
                break
    if not suspects:
        return False, "none"
    deduped = []
    seen = set()
    for item in suspects:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return True, " | ".join(deduped[:5])


def is_multiword_english_keyword(keyword: str) -> bool:
    if not keyword:
        return False
    if re.search(r"[áéíóúãõâêôçÁÉÍÓÚÃÕÂÊÔÇ]", keyword):
        return False
    tokens = re.findall(r"[A-Za-z]+", keyword)
    return len(tokens) >= 2


def exact_keyword_in_line(line: str, keyword: str) -> bool:
    return normalize_text(keyword) in normalize_text(line)


def extract_summary_experience_lines(lines: list[str]) -> list[str]:
    for marker in ("Resumo", "Summary"):
        try:
            start = lines.index(marker)
            break
        except ValueError:
            continue
    else:
        start = 0

    end = len(lines)
    for marker in ("Formação", "Stack técnica", "Idiomas", "Education", "Technical Skills", "Technical Stack", "Languages"):
        try:
            marker_index = lines.index(marker)
        except ValueError:
            continue
        end = min(end, marker_index)
    return [line for line in lines[start + 1 : end] if line.strip()]


def extract_experience_lines(lines: list[str]) -> list[str]:
    for marker in ("Experiência", "Experience"):
        try:
            start = lines.index(marker)
            break
        except ValueError:
            continue
    else:
        return []

    end = len(lines)
    for marker in ("Formação", "Stack técnica", "Idiomas", "Education", "Technical Skills", "Technical Stack", "Languages"):
        try:
            marker_index = lines.index(marker)
        except ValueError:
            continue
        end = min(end, marker_index)
    return [line for line in lines[start + 1 : end] if line.strip()]


def extract_summary_fact_anchors(summary_text: str) -> list[str]:
    patterns = [
        r"R\$\s?\d+(?:[.,]\d+)?\s?(?:MM|M|mil)?",
        r"\d+(?:[.,]\d+)?%",
        r"\d+\+?\s*POPs?",
        r"\d+\+?\s*SKUs",
        r"\d+\+?\s*cidades",
        r"\d+\+?\s*pessoas",
        r"\d+\+?\s*pedidos/m[eê]s",
        r"\d+\s*[KkMm]?\s*→\s*\d+\s*[KkMm]?",
    ]
    anchors: list[str] = []
    for pattern in patterns:
        anchors.extend(re.findall(pattern, summary_text, flags=re.IGNORECASE))
    deduped = []
    seen = set()
    for anchor in anchors:
        key = normalize_text(anchor)
        if key and key not in seen:
            seen.add(key)
            deduped.append(anchor)
    return deduped


def summary_supported_by_experiences(summary_text: str, experience_lines: list[str]) -> tuple[bool, str]:
    anchors = extract_summary_fact_anchors(summary_text)
    if not anchors:
        return True, "no_numeric_anchors"
    experience_text = "\n".join(experience_lines)
    missing = [anchor for anchor in anchors if normalize_text(anchor) not in normalize_text(experience_text)]
    if not missing:
        return True, "all_summary_anchors_found_in_experiences"
    return False, "missing_summary_anchors=" + ", ".join(missing[:8])


def normalized_path_string(path_text: str | None) -> str | None:
    if not path_text:
        return None
    return str(Path(path_text).resolve())


def is_validated_cellular_artifact(artifact: Path) -> bool:
    """Allow non-outputs DOCX files only through their immutable cell manifest."""
    if "artifacts" not in artifact.parts or artifact.name != "cv.docx":
        return False
    manifest_path = artifact.parent / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return False
    return (
        manifest.get("status") == "validated"
        and manifest.get("artifact_name") == "cv.docx"
        and normalized_path_string(manifest.get("path")) == str(artifact.resolve())
        and manifest.get("sha256") == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )


def run_docx_validator(artifact: Path) -> tuple[bool, str]:
    command = [sys.executable, "scripts/docx/validate_docx.py", str(artifact)]
    result = subprocess.run(command, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()


def top_keywords(fit_map: dict, limit: int = 8) -> list[dict]:
    items = [
        item
        for item in fit_map.get("keywords_habilidade_ats", [])
        if isinstance(item, dict) and isinstance(item.get("prioridade"), int)
    ]
    return sorted(items, key=lambda item: item["prioridade"])[:limit]


def _keyword_declared_gap(keyword: str, fit_map: dict, record: dict, item: dict) -> bool:
    status = str(record.get("status", "")).strip()
    origin = str(record.get("origin") or item.get("origem") or "").strip()
    if status == "gap" or "gap" in origin.casefold():
        return True
    keyword_key = normalize_text(keyword)
    if not keyword_key:
        return False
    gap_text = normalize_text(" ".join(str(gap) for gap in fit_map.get("gaps_sem_cobertura", [])))
    return keyword_key in gap_text


def _coverage_class(status: str, evidence_line: str | None, translation_equivalent: bool, declared_gap: bool) -> tuple[str, float, bool]:
    if status == "covered_cv" or (evidence_line and not translation_equivalent):
        return "covered_exact", 1.0, True
    if status == "covered_similar_cv" or translation_equivalent:
        return "covered_similar", 0.8, True
    if declared_gap:
        return "declared_gap", 0.0, False
    return "missing_unexplained", 0.0, False


def top_keyword_results(
    fit_map: dict,
    application: dict | None,
    lines: list[str],
    translation_registry: dict,
    limit: int = 8,
) -> tuple[list[dict], list[str]]:
    registry_records = {}
    if application:
        for record in application.get("keyword_records", []):
            keyword = str(record.get("keyword", "")).strip()
            if keyword:
                registry_records[keyword] = record

    results = []
    missing = []
    for item in top_keywords(fit_map, limit=limit):
        keyword = str(item.get("keyword", "")).strip()
        record = registry_records.get(keyword, {})
        status = str(record.get("status", "")).strip()
        exact = bool(record.get("exact_match_in_cv"))
        similar = bool(record.get("similar_match_in_cv"))
        declared_gap = _keyword_declared_gap(keyword, fit_map, record, item)
        evidence_line, matched_variant = find_keyword_or_translation_line(
            lines,
            keyword,
            translation_registry,
            allow_translation=True,
        )
        translation_equivalent = bool(matched_variant and matched_variant.casefold() != keyword.casefold())
        coverage_class, coverage_score, covered = _coverage_class(
            status,
            evidence_line,
            translation_equivalent,
            declared_gap,
        )
        if coverage_class == "missing_unexplained":
            missing.append(keyword)
        results.append(
            {
                "priority": item.get("prioridade"),
                "keyword": keyword,
                "covered": covered,
                "coverage_class": coverage_class,
                "coverage_score": coverage_score,
                "declared_gap": declared_gap,
                "present_exact": exact,
                "present_similar": similar,
                "covered_by_translation_equivalent": translation_equivalent,
                "matched_variant": matched_variant,
                "status": (
                    "covered_translation_equivalent"
                    if translation_equivalent and status not in {"covered_cv", "covered_similar_cv"}
                    else status or ("covered_cv" if evidence_line else "missing_cv")
                ),
                "evidence_line": evidence_line,
                "experience_target": record.get("experience_target"),
                "coverage_note": (
                    record.get("coverage_note")
                    or (
                        f"Coberta no CV PT-BR por equivalente canônico: {matched_variant}"
                        if translation_equivalent
                        else None
                    )
                ),
            }
        )
    return results, missing


def ats_score_summary(results: list[dict], *, limit: int) -> dict:
    score = round(sum(float(item.get("coverage_score", 0.0)) for item in results), 2)
    missing_unexplained = [
        str(item.get("keyword"))
        for item in results
        if item.get("coverage_class") == "missing_unexplained"
    ]
    declared_gaps = [
        str(item.get("keyword"))
        for item in results
        if item.get("coverage_class") == "declared_gap"
    ]
    exact = sum(1 for item in results if item.get("coverage_class") == "covered_exact")
    similar = sum(1 for item in results if item.get("coverage_class") == "covered_similar")
    threshold_optimal = ATS_TOP8_OPTIMAL_SCORE if limit == 8 else ATS_TOP15_OPTIMAL_SCORE
    threshold_minimum = ATS_TOP8_MINIMUM_SCORE if limit == 8 else ATS_TOP15_MINIMUM_SCORE
    if missing_unexplained or score < threshold_minimum:
        level = "blocked"
    elif score >= threshold_optimal:
        level = "optimal"
    else:
        level = "minimum"
    return {
        "limit": limit,
        "score": score,
        "score_max": limit,
        "minimum_score": threshold_minimum,
        "optimal_score": threshold_optimal,
        "level": level,
        "covered_exact": exact,
        "covered_similar": similar,
        "declared_gap": len(declared_gaps),
        "missing_unexplained": len(missing_unexplained),
        "missing_unexplained_keywords": missing_unexplained,
        "declared_gap_keywords": declared_gaps,
    }


def blocker(blocker_id: str, message: str, evidence: str = "") -> dict:
    return {"id": blocker_id, "message": message, "evidence": evidence}


def warning(warning_id: str, message: str, evidence: str = "") -> dict:
    return {"id": warning_id, "message": message, "evidence": evidence}


def pt_keyword_shotgun_check(lines: list[str], top_results: list[dict]) -> tuple[bool, str]:
    prose_lines = extract_summary_experience_lines(lines)
    tracked = [
        item
        for item in top_results
        if is_multiword_english_keyword(str(item.get("keyword", "")))
    ]

    total_hits = 0
    unique_hits: set[str] = set()
    max_hits_on_line = 0
    hard_line_violations: list[str] = []
    soft_line_clusters: list[str] = []
    translation_suggestions: list[str] = []

    for line in prose_lines:
        hits = [
            item
            for item in tracked
            if exact_keyword_in_line(line, str(item.get("keyword", "")))
        ]
        if hits:
            hit_keywords = [str(item["keyword"]) for item in hits]
            total_hits += len(hit_keywords)
            unique_hits.update(hit_keywords)
            max_hits_on_line = max(max_hits_on_line, len(hit_keywords))

            for item in hits:
                matched_variant = str(item.get("matched_variant") or "").strip()
                keyword = str(item.get("keyword") or "").strip()
                if matched_variant and matched_variant.casefold() != keyword.casefold():
                    translation_suggestions.append(f"{keyword} -> {matched_variant}")

            if len(hit_keywords) >= 4:
                hard_line_violations.append(f"{line} :: {', '.join(hit_keywords)}")
            elif len(hit_keywords) == 2:
                soft_line_clusters.append(f"{line} :: {', '.join(hit_keywords)}")

    soft_cluster_count = len(soft_line_clusters)
    passed = (
        total_hits <= 8
        and len(unique_hits) <= 8
        and max_hits_on_line <= 3
        and soft_cluster_count <= 2
        and not hard_line_violations
    )

    evidence = (
        f"total_multiword_english_hits={total_hits}; "
        f"unique_multiword_english_keywords={len(unique_hits)}; "
        f"max_hits_on_line={max_hits_on_line}; "
        f"soft_clusters={soft_cluster_count}"
    )
    if hard_line_violations:
        evidence += " | hard_line_violations=" + " || ".join(hard_line_violations[:3])
    if soft_line_clusters:
        evidence += " | soft_line_clusters=" + " || ".join(soft_line_clusters[:3])
    if translation_suggestions:
        deduped = []
        seen = set()
        for item in translation_suggestions:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        evidence += " | translation_suggestions=" + ", ".join(deduped[:5])
    return passed, evidence


def build_cv_review(
    artifact: Path,
    fit_map: dict,
    registry: dict,
    translation_registry_path: Path,
) -> dict:
    company = fit_map.get("empresa", "")
    role = fit_map.get("cargo", "")
    lines = compact_lines(docx_text(artifact))
    full_text = "\n".join(lines)
    summary_text = extract_summary_text(lines)
    experience_lines = extract_experience_lines(lines)
    validator_ok, validator_output = run_docx_validator(artifact)
    application = find_application(registry, company, role)
    translation_registry = load_translation_registry(translation_registry_path)

    top8_results, missing_top8 = top_keyword_results(fit_map, application, lines, translation_registry, limit=8)
    top15_results, _missing_top15 = top_keyword_results(fit_map, application, lines, translation_registry, limit=15)
    ats_top8 = ats_score_summary(top8_results, limit=8)
    ats_top15 = ats_score_summary(top15_results, limit=15)

    registry_path_matches = False
    if application:
        stored_cv_path = application.get("cv_path")
        registry_path_matches = normalized_path_string(stored_cv_path) == str(artifact.resolve())

    keyword_shotgun_ok, keyword_shotgun_evidence = (
        pt_keyword_shotgun_check(lines, top8_results) if is_portuguese_cv(artifact) else (True, "english_cv")
    )
    english_role_titles_in_pt, english_role_titles_evidence = (
        english_cv_has_portuguese_role_titles(lines) if not is_portuguese_cv(artifact) else (False, "pt_cv")
    )
    summary_supported, summary_supported_evidence = summary_supported_by_experiences(summary_text, experience_lines)

    technical_checks = [
        {
            "id": "artifact_exists_in_outputs",
            "passed": artifact.exists() and (
                ("outputs" in artifact.parts and "_tmp" not in artifact.parts)
                or is_validated_cellular_artifact(artifact)
            ),
            "evidence": str(artifact),
        },
        {
            "id": "docx_validation_passed",
            "passed": validator_ok,
            "evidence": validator_output,
        },
        {
            "id": "fit_map_has_company_and_role",
            "passed": bool(company and role),
            "evidence": f"company={company!r}; role={role!r}",
        },
        {
            "id": "registry_application_exists",
            "passed": application is not None,
            "evidence": f"application_key={application.get('application_key') if application else 'missing'}",
        },
        {
            "id": "registry_points_to_final_artifact",
            "passed": registry_path_matches,
            "evidence": f"registry_cv_path={application.get('cv_path') if application else None}",
        },
        {
            "id": "ats_top8_minimum_score",
            "passed": ats_top8["score"] >= ATS_TOP8_MINIMUM_SCORE,
            "evidence": f"score={ats_top8['score']}/{ats_top8['score_max']}; minimum={ATS_TOP8_MINIMUM_SCORE}",
        },
        {
            "id": "ats_top8_no_missing_unexplained",
            "passed": not missing_top8,
            "evidence": "missing_unexplained=" + (", ".join(missing_top8) if missing_top8 else "none"),
        },
        {
            "id": "english_cv_role_titles_in_english",
            "passed": not english_role_titles_in_pt,
            "evidence": english_role_titles_evidence,
        },
        {
            "id": "summary_facts_backed_by_experiences",
            "passed": summary_supported,
            "evidence": summary_supported_evidence,
        },
    ]

    minor_checks = [
        {
            "id": "filename_follows_convention",
            "passed": review_filename(artifact),
            "evidence": artifact.name,
        },
        {
            "id": "summary_within_limit",
            "passed": bool(summary_text) and len(summary_text) <= 480,
            "evidence": f"summary_chars={len(summary_text)}",
        },
        {
            "id": "pt_cv_natural_keyword_mix",
            "passed": keyword_shotgun_ok,
            "evidence": keyword_shotgun_evidence,
        },
        {
            "id": "header_has_linkedin",
            "passed": "linkedin.com/in/felipearmel" in full_text,
            "evidence": "linkedin.com/in/felipearmel",
        },
        {
            "id": "header_has_phone",
            "passed": "(11) 98674-8218" in full_text,
            "evidence": "(11) 98674-8218",
        },
        {
            "id": "header_has_email",
            "passed": "armelfelipe@gmail.com" in full_text,
            "evidence": "armelfelipe@gmail.com",
        },
        {
            "id": "header_has_location",
            "passed": "São Paulo, SP" in full_text or "Sao Paulo, SP" in full_text,
            "evidence": "São Paulo, SP / Sao Paulo, SP",
        },
        {
            "id": "stack_section_present",
            "passed": "Stack técnica" in full_text or "Technical Skills" in full_text or "Technical Stack" in full_text,
            "evidence": "Stack técnica / Technical Skills / Technical Stack",
        },
        {
            "id": "idiomas_section_present",
            "passed": "Idiomas" in full_text or "Languages" in full_text,
            "evidence": "Idiomas / Languages",
        },
        {
            "id": "english_advanced_not_fluent",
            "passed": ("Inglês — Avançado" in full_text or "English — Advanced" in full_text) and "Fluente" not in full_text and "Fluent" not in full_text.replace("Fluent or native", ""),
            "evidence": "Inglês — Avançado / English — Advanced",
        },
        {
            "id": "spanish_absent",
            "passed": "Espanhol" not in full_text,
            "evidence": "Espanhol absent",
        },
    ]

    blockers = []
    for check in technical_checks:
        if not check["passed"]:
            blockers.append(blocker(check["id"], f"CV delivery blocked by {check['id']}", check["evidence"]))

    if not keyword_shotgun_ok:
        blockers.append(
            blocker(
                "pt_cv_keyword_shotgun_control",
                "CV delivery blocked by forced English keyword density in PT-BR prose.",
                keyword_shotgun_evidence,
            )
        )

    warnings = []
    if ats_top8["declared_gap_keywords"]:
        warnings.append(
            warning(
                "ats_top8_declared_gaps",
                "Top 8 keywords include declared gaps; these are visible but do not block delivery.",
                ", ".join(ats_top8["declared_gap_keywords"]),
            )
        )
    if ats_top15["score"] < ATS_TOP15_OPTIMAL_SCORE:
        warnings.append(
            warning(
                "ats_top15_below_optimal",
                "Top 15 ATS coverage is below the optimal target.",
                f"score={ats_top15['score']}/{ats_top15['score_max']}; optimal={ATS_TOP15_OPTIMAL_SCORE}",
            )
        )

    total_passed = sum(1 for check in technical_checks if check["passed"])
    minor_passed = sum(1 for check in minor_checks if check["passed"])
    minor_total = len(minor_checks)
    minor_rate = minor_passed / minor_total if minor_total else 1.0
    approved_for_delivery = not blockers
    approved = approved_for_delivery

    return {
        "kind": "cv",
        "artifact": str(artifact),
        "company": company,
        "role": role,
        "approved": approved,
        "approved_for_delivery": approved_for_delivery,
        "ats_policy": {
            "top8": ats_top8,
            "top15": ats_top15,
            "weights": {
                "covered_exact": 1.0,
                "covered_similar": 0.8,
                "declared_gap": 0.0,
                "missing_unexplained": 0.0,
            },
        },
        "blockers": blockers,
        "warnings": warnings,
        "totals": {
            "weight_total_passed": total_passed,
            "weight_total_total": len(technical_checks),
            "minor_passed": minor_passed,
            "minor_total": minor_total,
            "minor_rate": round(minor_rate, 4),
            "blockers": len(blockers),
            "warnings": len(warnings),
        },
        "weight_total_checks": technical_checks,
        "minor_checks": minor_checks,
        "top8_keywords": top8_results,
        "top15_keywords": top15_results,
        "summary_chars": len(summary_text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate objetivo para output-reviewer.")
    parser.add_argument("--kind", choices=["cv"], required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--fit-map", default=".career-state/fit_map.json")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--translation-registry", default=str(DEFAULT_TRANSLATION_REGISTRY))
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    artifact = Path(args.artifact)
    fit_map = read_json(Path(args.fit_map))
    registry = read_json(Path(args.registry))
    translation_registry_path = Path(args.translation_registry)

    if args.kind != "cv":
        print(f"Unsupported review kind: {args.kind}")
        return 2

    report = build_cv_review(artifact, fit_map, registry, translation_registry_path)
    write_json(Path(args.report), report)

    print(f"Review report written: {args.report}")
    print(f"Approved for delivery: {'yes' if report['approved_for_delivery'] else 'no'}")
    print(
        "Blocker checks: "
        f"{report['totals']['weight_total_passed']}/{report['totals']['weight_total_total']}"
    )
    print(
        "ATS top8: "
        f"{report['ats_policy']['top8']['score']}/{report['ats_policy']['top8']['score_max']} "
        f"({report['ats_policy']['top8']['level']})"
    )
    print(
        "Minor checks: "
        f"{report['totals']['minor_passed']}/{report['totals']['minor_total']} "
        f"({report['totals']['minor_rate'] * 100:.0f}%)"
    )
    print(
        "Blockers: "
        + ("; ".join(item["id"] for item in report["blockers"]) if report["blockers"] else "none")
    )
    print(
        "Warnings: "
        + ("; ".join(item["id"] for item in report["warnings"]) if report["warnings"] else "none")
    )
    failed_top = report["ats_policy"]["top8"]["missing_unexplained_keywords"]
    print("Missing unexplained top8: " + (", ".join(failed_top) if failed_top else "none"))
    return 0 if report["approved_for_delivery"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
