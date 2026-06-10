from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
import unicodedata

from career.paths import CAREER_STATE, ROOT
from career.utils import read_json, write_json


REFERENCES = ROOT / ".opencode" / "skills" / "career-system" / "references"
MEMORY_DIR = CAREER_STATE / "memory"
DERIVED_DIR = CAREER_STATE / "derived"
NOTION_CACHE = ROOT / "inbox" / "notion" / "applications_cache.json"
KEYWORD_REGISTRY = DERIVED_DIR / "keyword_ats_registry.json"


def _keyword_registry_summary() -> dict[str, Any]:
    registry_path = KEYWORD_REGISTRY
    if not registry_path.exists():
        return {"applications": 0, "canonical_keywords": 0, "top_keywords": []}
    registry = read_json(registry_path)
    canonical = registry.get("canonical_keywords", {})
    applications = registry.get("applications", [])
    counts = Counter()
    for item in applications:
        for keyword in item.get("keywords", []) or []:
            if isinstance(keyword, str) and keyword.strip():
                counts[keyword.strip()] += 1
    return {
        "applications": len(applications),
        "canonical_keywords": len(canonical),
        "top_keywords": [{"keyword": keyword, "count": count} for keyword, count in counts.most_common(25)],
    }


def build_memory_bundle(output_dir: Path = MEMORY_DIR) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    competencies_matrix = REFERENCES / "competencias_matrix.json"
    competencies_by_experience = REFERENCES / "competencias_por_experiencia.json"
    payloads = {
        "profile_facts.json": {
            "language_rules": {"english": "Avancado", "spanish": "never include as competency"},
            "protected_claims": [
                "Never claim full P&L ownership.",
                "VivaReal CS is described as arquiteto da area.",
                "Fill rate belongs to Trifil.",
                "wehandle must stay lowercase in final documents.",
            ],
            "critical_metrics": {
                "wehandle": ["margem bruta 15%", "custo por atendimento R$4,14 -> R$3,61 (-13%)"],
                "iFood": ["saving simulador R$70MM/ano", "budget OPEX logistico R$300MM/ano", "cobertura 400 -> 800 cidades"],
                "VivaReal": ["conversao SDR inbound 18% -> 50%", "area de CS 91 pessoas"],
                "Trifil": ["reducao de GGF R$8MM"],
            },
        },
        "application_rules.json": {
            "tone": "factual, direct, first person, no coach language",
            "fit_rules": [
                "Prioritize interview defensibility over semantic similarity.",
                "Repositioning never becomes direct coverage by narrative strength alone.",
                "Sensitive claims without literal proof must remain explicit gaps.",
            ],
        },
        "ats_keyword_summary.json": _keyword_registry_summary(),
        "evidence_index.json": {
            "sources": [
                str((REFERENCES / "palavras_chave_carreira.md").relative_to(ROOT)),
                str((REFERENCES / "autoconhecimento.md").relative_to(ROOT)),
                str(competencies_matrix.relative_to(ROOT)),
                str(competencies_by_experience.relative_to(ROOT)),
            ],
            "competencies_matrix_items": len(read_json(competencies_matrix)) if competencies_matrix.exists() else 0,
            "competencies_by_experience_items": len(read_json(competencies_by_experience)) if competencies_by_experience.exists() else 0,
            "purpose": "Compact lookup manifest for evidence-oriented reads before opening long-form references.",
        },
    }
    written: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = output_dir / name
        write_json(path, payload)
        written[name] = path
    return written


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(text)).strip("_")


def application_key(company: str, role: str) -> str:
    return f"{normalize_key(company)}__{normalize_key(role)}"


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = normalize_text(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def extract_section_lines(body_text: str, heading: str, stop_headings: list[str]) -> list[str]:
    lines = [line.rstrip() for line in (body_text or "").splitlines()]
    capture = False
    collected: list[str] = []
    heading_norm = normalize_text(heading)
    stop_norms = {normalize_text(item) for item in stop_headings}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if capture and collected:
                continue
            continue
        normalized = normalize_text(line)
        if not capture:
            if normalized == heading_norm:
                capture = True
            continue
        if normalized in stop_norms:
            break
        collected.append(line)
    return collected


def parse_keywords_from_body(body_text: str) -> list[dict]:
    lines = extract_section_lines(
        body_text,
        "Keywords-habilidade para ATS",
        ["Feedback em caso de Reprovação", "Feedback em caso de Reprovacao"],
    )
    entries: list[dict] = []
    for line in lines:
        match = re.match(r"^(\d+)\.\s*(.+)$", line)
        if not match:
            continue
        priority = int(match.group(1))
        remainder = match.group(2).strip()
        parts = [part.strip() for part in remainder.split("|")]
        keyword = parts[0].strip()
        origin = ""
        for part in parts[1:]:
            lowered = normalize_text(part)
            if lowered.startswith("origem:"):
                origin = part.split(":", 1)[1].strip()
        if keyword:
            entries.append({"keyword": keyword, "priority": priority, "origin": origin})
    return entries


def choose_status(keyword: str, covered: list[str], gaps: list[str]) -> str:
    keyword_norm = normalize_text(keyword)
    if any(normalize_text(item) == keyword_norm for item in gaps):
        return "gap"
    if any(normalize_text(item) == keyword_norm for item in covered):
        return "covered_cv"
    return "missing_cv"


def build_keyword_records(application: dict) -> list[dict]:
    parsed_entries = parse_keywords_from_body(application.get("body_text", "") or "")
    parsed_top8 = [entry["keyword"] for entry in parsed_entries if entry.get("priority") and entry["priority"] <= 8]
    parsed_all = [entry["keyword"] for entry in parsed_entries]
    parsed_gap_keywords = [entry["keyword"] for entry in parsed_entries if "gap" in normalize_text(entry.get("origin", ""))]

    top8 = unique_strings((application.get("top8_keywords", []) or []) + parsed_top8)
    covered = unique_strings(application.get("covered_keywords", []) or [])
    gaps = unique_strings(
        (application.get("declared_gap_keywords", []) or [])
        + (application.get("gaps", []) or [])
        + parsed_gap_keywords
    )
    keyword_pool = unique_strings(top8 + (application.get("keywords", []) or []) + parsed_all)
    records: list[dict] = []
    top8_lookup = {normalize_text(keyword): index for index, keyword in enumerate(top8, start=1)}
    parsed_origin_lookup = {normalize_text(entry["keyword"]): entry.get("origin", "") for entry in parsed_entries}
    for keyword in keyword_pool:
        keyword_norm = normalize_text(keyword)
        priority = top8_lookup.get(keyword_norm)
        status = choose_status(keyword, covered, gaps)
        records.append(
            {
                "keyword": keyword,
                "canonical": keyword,
                "priority": priority,
                "status": status,
                "exact_match_in_cv": status == "covered_cv",
                "similar_match_in_cv": False,
                "experience_target": None,
                "suggested_bullet_slot": None,
                "origin": parsed_origin_lookup.get(keyword_norm) or "notion_cache",
                "linkedin_use": "recommended" if status == "covered_cv" and priority and priority <= 8 else "optional",
            }
        )
    return records


def rebuild_canonical_stats(registry: dict) -> None:
    canonical: dict[str, dict] = {}
    for application in registry.get("applications", []):
        for record in application.get("keyword_records", []):
            key = normalize_key(record["canonical"])
            entry = canonical.setdefault(
                key,
                {
                    "keyword": record["canonical"],
                    "times_extracted": 0,
                    "times_covered_cv": 0,
                    "times_covered_similar_cv": 0,
                    "times_missing_cv": 0,
                    "times_gap": 0,
                    "recommended_for_linkedin": False,
                    "experience_targets": [],
                },
            )
            entry["times_extracted"] += 1
            if record["status"] == "covered_cv":
                entry["times_covered_cv"] += 1
            if record["status"] == "covered_similar_cv":
                entry["times_covered_similar_cv"] += 1
            if record["status"] == "missing_cv":
                entry["times_missing_cv"] += 1
            if record["status"] == "gap":
                entry["times_gap"] += 1
            if record.get("linkedin_use") == "recommended":
                entry["recommended_for_linkedin"] = True
    registry["canonical_keywords"] = canonical


def build_registry_from_cache(cache: dict) -> dict:
    applications_payload = cache.get("applications", [])
    registry_applications: list[dict] = []
    for application in applications_payload:
        company = str(application.get("company") or "").strip()
        role = str(application.get("role") or application.get("title") or "").strip()
        if not company and not role:
            continue
        keyword_records = build_keyword_records(application)
        if not keyword_records:
            continue
        registry_applications.append(
            {
                "application_key": application_key(company, role),
                "company": company,
                "role": role,
                "mode": "notion_rebuild",
                "fit_score": application.get("fit_score"),
                "central_pain": None,
                "cv_path": application.get("final_artifact") or None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "keyword_records": keyword_records,
                "linkedin_bullet_candidates": [
                    {
                        "keyword": record["keyword"],
                        "experience_target": record.get("experience_target"),
                        "source": record["status"],
                    }
                    for record in keyword_records
                    if record["linkedin_use"] == "recommended"
                ][:8],
                "missing_keywords": [
                    record["keyword"]
                    for record in keyword_records
                    if record["status"] in {"missing_cv", "gap"}
                ],
                "source_record_id": application.get("record_id"),
                "source_page_id": application.get("page_id"),
                "source": "notion_cache",
            }
        )

    registry = {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "applications": registry_applications,
        "canonical_keywords": {},
        "rebuilt_from": {
            "source": "notion_applications_cache",
            "generated_at": cache.get("generated_at"),
            "application_count": len(applications_payload),
        },
    }
    rebuild_canonical_stats(registry)
    return registry


def rebuild_keyword_registry_from_cache(
    cache_path: Path = NOTION_CACHE,
    output_path: Path = KEYWORD_REGISTRY,
) -> dict[str, Any]:
    cache = read_json(cache_path)
    registry = build_registry_from_cache(cache)
    write_json(output_path, registry)
    return {
        "cache_path": str(cache_path),
        "output_path": str(output_path),
        "applications_exported": len(registry["applications"]),
        "canonical_keywords": len(registry["canonical_keywords"]),
    }
