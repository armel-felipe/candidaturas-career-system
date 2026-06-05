#!/usr/bin/env python3
import argparse
import difflib
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from keyword_translation_utils import (
    DEFAULT_TRANSLATION_CANDIDATES,
    DEFAULT_TRANSLATION_REGISTRY,
    build_translation_candidates,
    load_translation_registry,
    write_json as write_translation_json,
)


DEFAULT_REGISTRY = Path(".opencode/skills/career-system/references/keyword_ats_registry.json")


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def keyword_tokens(text: str) -> set[str]:
    stopwords = {
        "a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em", "para",
        "com", "por", "no", "na", "nos", "nas",
    }
    normalized = normalize_text(text)
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    tokens = set()
    for token in raw_tokens:
        if token in stopwords or len(token) <= 2:
            continue
        simplified = re.sub(r"(s|es)$", "", token)
        tokens.add(simplified)
    return tokens


def best_similar_record(keyword: str, covered_records: list[dict]):
    target_norm = normalize_text(keyword)
    target_tokens = keyword_tokens(keyword)
    best_match = None
    best_score = 0.0

    for record in covered_records:
        candidate = record.get("keyword", "")
        if not candidate:
            continue

        candidate_norm = normalize_text(candidate)
        candidate_tokens = keyword_tokens(candidate)
        shared_tokens = sorted(target_tokens & candidate_tokens)
        token_score = len(shared_tokens) / max(len(target_tokens), len(candidate_tokens), 1)
        ratio = difflib.SequenceMatcher(None, target_norm, candidate_norm).ratio()
        score = max(token_score, ratio)

        if not shared_tokens and ratio < 0.72:
            continue
        if shared_tokens and score < 0.34:
            continue
        if score > best_score:
            best_score = score
            best_match = {
                "keyword": candidate,
                "shared_tokens": shared_tokens,
                "score": round(score, 3),
            }

    return best_match


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def docx_text(path: Path) -> str:
    if not path or not path.exists():
        return ""

    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")

    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join(node.text or "" for node in root.findall(".//w:t", ns))


def annotate_similar_keyword_coverage(records: list[dict]) -> None:
    covered_records = [record for record in records if record.get("status") == "covered_cv"]
    for record in records:
        if record.get("status") != "missing_cv":
            continue
        match = best_similar_record(record.get("keyword", ""), covered_records)
        if not match:
            continue

        record["status"] = "covered_similar_cv"
        record["similar_match_in_cv"] = True
        record["substituted_by_keyword"] = match["keyword"]
        record["shared_tokens_with_substitute"] = match["shared_tokens"]
        record["substitution_score"] = match["score"]
        record["coverage_note"] = (
            f"Keyword exata ausente no CV; coberta por wording semelhante: {match['keyword']}"
        )


def keyword_records(fit_map: dict, cv_text: str) -> list[dict]:
    records = []
    cv_text_lower = cv_text.lower()
    cv_text_normalized = normalize_text(cv_text)
    gap_text = " ".join(fit_map.get("gaps_sem_cobertura", [])).lower()
    gap_text_normalized = normalize_key(gap_text)

    for item in fit_map.get("keywords_habilidade_ats", []):
        keyword = item.get("keyword", "").strip()
        if not keyword:
            continue

        keyword_normalized = normalize_text(keyword)
        exact_present = bool(cv_text) and (
            keyword.lower() in cv_text_lower
            or (keyword_normalized and keyword_normalized in cv_text_normalized)
        )
        origin = item.get("origem", "")
        status = "covered_cv" if exact_present else "pending_cv"
        if "gap" in origin.lower():
            status = "gap"
        elif cv_text and not exact_present:
            status = "missing_cv"

        records.append({
            "keyword": keyword,
            "canonical": keyword,
            "priority": item.get("prioridade"),
            "status": status,
            "exact_match_in_cv": exact_present,
            "similar_match_in_cv": False,
            "experience_target": item.get("experiencia_alvo"),
            "suggested_bullet_slot": item.get("bullet_sugerido"),
            "origin": origin,
            "linkedin_use": "recommended" if status == "covered_cv" and item.get("prioridade", 99) <= 8 else "optional",
        })

    extracted_terms = {record["keyword"].lower() for record in records}
    for item in fit_map.get("keywords_vaga", []):
        term = item.get("termo", "").strip()
        if term and term.lower() not in extracted_terms:
            term_normalized = normalize_text(term)
            exact_present = bool(cv_text) and (
                term.lower() in cv_text_lower
                or (term_normalized and term_normalized in cv_text_normalized)
            )
            status = "covered_cv" if exact_present else ("missing_cv" if cv_text else "pending_cv")
            if term.lower() in gap_text or normalize_key(term) in gap_text_normalized:
                status = "gap"
            records.append({
                "keyword": term,
                "canonical": term,
                "priority": None,
                "status": status,
                "exact_match_in_cv": exact_present,
                "similar_match_in_cv": False,
                "experience_target": None,
                "suggested_bullet_slot": None,
                "origin": item.get("origem"),
                "linkedin_use": "optional",
            })

    annotate_similar_keyword_coverage(records)
    return records


def upsert_application(registry: dict, application: dict) -> None:
    applications = registry.setdefault("applications", [])
    app_key = application["application_key"]
    for index, existing in enumerate(applications):
        if existing.get("application_key") == app_key:
            applications[index] = application
            return
    applications.append(application)


def rebuild_canonical_stats(registry: dict) -> None:
    canonical = {}
    for application in registry.get("applications", []):
      for record in application.get("keyword_records", []):
        key = normalize_key(record["canonical"])
        entry = canonical.setdefault(key, {
            "keyword": record["canonical"],
            "times_extracted": 0,
            "times_covered_cv": 0,
            "times_covered_similar_cv": 0,
            "times_missing_cv": 0,
            "times_gap": 0,
            "recommended_for_linkedin": False,
            "experience_targets": [],
        })

        entry["times_extracted"] += 1
        if record["status"] == "covered_cv":
            entry["times_covered_cv"] += 1
        if record["status"] == "covered_similar_cv":
            entry["times_covered_similar_cv"] += 1
        if record["status"] == "missing_cv":
            entry["times_missing_cv"] += 1
        if record["status"] == "gap":
            entry["times_gap"] += 1
        if record["linkedin_use"] == "recommended":
            entry["recommended_for_linkedin"] = True

        target = record.get("experience_target")
        if target and target not in entry["experience_targets"]:
            entry["experience_targets"].append(target)
    registry["canonical_keywords"] = canonical


def build_application(fit_map: dict, cv_path, cv_text: str) -> dict:
    company = fit_map.get("empresa", "")
    role = fit_map.get("cargo", "")
    app_key = f"{normalize_key(company)}__{normalize_key(role)}"
    records = keyword_records(fit_map, cv_text)

    return {
        "application_key": app_key,
        "company": company,
        "role": role,
        "mode": fit_map.get("modo"),
        "fit_score": fit_map.get("nota_aderencia"),
        "central_pain": fit_map.get("dor_central"),
        "cv_path": str(cv_path) if cv_path else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "keyword_records": records,
        "linkedin_bullet_candidates": [
            {
                "keyword": record["keyword"],
                "experience_target": record["experience_target"],
                "source": record["status"],
            }
            for record in records
            if record["linkedin_use"] == "recommended"
        ][:8],
        "missing_keywords": [
            record["keyword"]
            for record in records
            if record["status"] in {"missing_cv", "gap"}
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-map", default=".career-state/fit_map.json")
    parser.add_argument("--cv")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--translation-registry", default=str(DEFAULT_TRANSLATION_REGISTRY))
    parser.add_argument("--translation-candidates", default=str(DEFAULT_TRANSLATION_CANDIDATES))
    args = parser.parse_args()

    fit_map_path = Path(args.fit_map)
    registry_path = Path(args.registry)
    cv_path = Path(args.cv) if args.cv else None
    if cv_path and not cv_path.exists():
        print(f"CV file not found: {cv_path}", flush=True)
        return 1

    fit_map = read_json(fit_map_path)
    registry = read_json(registry_path) if registry_path.exists() else {
        "version": 1,
        "last_updated": None,
        "applications": [],
        "canonical_keywords": {},
    }
    cv_content = docx_text(cv_path) if cv_path else ""

    application = build_application(fit_map, cv_path, cv_content)
    upsert_application(registry, application)
    rebuild_canonical_stats(registry)
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()

    write_json(registry_path, registry)
    translation_registry = load_translation_registry(Path(args.translation_registry))
    translation_candidates = build_translation_candidates(registry, translation_registry)
    write_translation_json(Path(args.translation_candidates), translation_candidates)

    covered = [r["keyword"] for r in application["keyword_records"] if r["status"] == "covered_cv"]
    covered_similar = [r["keyword"] for r in application["keyword_records"] if r["status"] == "covered_similar_cv"]
    missing = application["missing_keywords"]
    print(f"Keyword registry updated: {registry_path}")
    print(f"Translation candidates updated: {args.translation_candidates}")
    print(f"Application: {application['company']} - {application['role']}")
    print(f"Covered in CV: {len(covered)}")
    print(f"Covered by similar wording: {len(covered_similar)}")
    print(f"Missing/gaps: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
