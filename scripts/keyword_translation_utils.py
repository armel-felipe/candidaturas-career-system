#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


DEFAULT_TRANSLATION_REGISTRY = Path(".opencode/skills/career-system/references/keyword_translation_registry.json")
DEFAULT_TRANSLATION_CANDIDATES = Path(".opencode/skills/career-system/references/keyword_translation_candidates.json")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).lower()


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(text)).strip("_")


def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_translation_candidate_keyword(keyword: str) -> bool:
    if not keyword:
        return False
    ascii_tokens = re.findall(r"[A-Za-z]+", keyword)
    if len(ascii_tokens) >= 2:
        return True
    return keyword.upper() == keyword and bool(re.search(r"[A-Z]", keyword)) and any(ch in keyword for ch in "&/-")


def load_translation_registry(path: Path | None = None) -> dict:
    target = path or DEFAULT_TRANSLATION_REGISTRY
    data = read_json(
        target,
        default={
            "version": 1,
            "policy": {},
            "entries": {},
        },
    )
    data.setdefault("entries", {})
    return data


def translation_entry_for(keyword: str, registry: dict) -> dict | None:
    entries = registry.get("entries", {})
    direct = entries.get(normalize_key(keyword))
    if direct:
        return direct
    for entry in entries.values():
        aliases = [entry.get("canonical_keyword", "")] + list(entry.get("aliases", []))
        # Also check en_cv_preferred for English CV matching
        en_pref = entry.get("en_cv_preferred", "")
        if en_pref:
            aliases.append(en_pref)
        if any(normalize_text(alias) == normalize_text(keyword) for alias in aliases if alias):
            return entry
    return None


def translation_variants(entry: dict | None) -> list[str]:
    if not entry:
        return []
    variants = []
    # First check for en_cv preferred (for English CVs)
    for field in ("en_cv_preferred", "pt_br_preferred",):
        value = str(entry.get(field, "")).strip()
        if value:
            variants.append(value)
    for field in ("pt_br_alternatives", "accepted_variants"):
        for value in entry.get(field, []) or []:
            text = str(value).strip()
            if text:
                variants.append(text)
    unique = []
    seen = set()
    for variant in variants:
        key = normalize_text(variant)
        if key and key not in seen:
            seen.add(key)
            unique.append(variant)
    return unique


def find_keyword_or_translation_line(lines: list[str], keyword: str, translation_registry: dict, allow_translation: bool) -> tuple[str | None, str | None]:
    keyword_norm = normalize_text(keyword)
    for line in lines:
        if keyword_norm and keyword_norm in normalize_text(line):
            return line, keyword

    if not allow_translation:
        return None, None

    entry = translation_entry_for(keyword, translation_registry)
    for variant in translation_variants(entry):
        variant_norm = normalize_text(variant)
        for line in lines:
            if variant_norm and variant_norm in normalize_text(line):
                return line, variant
    return None, None


def build_translation_candidates(keyword_registry: dict, translation_registry: dict) -> dict:
    curated_entries = translation_registry.get("entries", {})
    applications = keyword_registry.get("applications", [])
    canonical_keywords = keyword_registry.get("canonical_keywords", {})

    keyword_examples: dict[str, dict] = {}
    for application in applications:
        app_key = application.get("application_key")
        role = application.get("role")
        company = application.get("company")
        for record in application.get("keyword_records", []):
            keyword = str(record.get("canonical") or record.get("keyword") or "").strip()
            if not keyword:
                continue
            key = normalize_key(keyword)
            bucket = keyword_examples.setdefault(
                key,
                {
                    "applications": [],
                    "experience_targets": Counter(),
                    "origins": Counter(),
                },
            )
            if app_key and app_key not in bucket["applications"]:
                bucket["applications"].append(app_key)
            target = str(record.get("experience_target") or "").strip()
            if target:
                bucket["experience_targets"][target] += 1
            origin = str(record.get("origin") or "").strip()
            if origin:
                bucket["origins"][origin] += 1
            if role and company:
                label = f"{company} — {role}"
                bucket["experience_targets"][label] += 0

    candidate_keys = set(curated_entries.keys())
    candidate_keys.update(
        key for key, entry in canonical_keywords.items() if is_translation_candidate_keyword(str(entry.get("keyword", "")))
    )

    candidates = []
    for key in sorted(candidate_keys):
        canonical_entry = canonical_keywords.get(key, {})
        curated = curated_entries.get(key, {})
        keyword = str(curated.get("canonical_keyword") or canonical_entry.get("keyword") or key).strip()
        stats = {
            "times_extracted": canonical_entry.get("times_extracted", 0),
            "times_covered_cv": canonical_entry.get("times_covered_cv", 0),
            "times_covered_similar_cv": canonical_entry.get("times_covered_similar_cv", 0),
            "times_missing_cv": canonical_entry.get("times_missing_cv", 0),
            "times_gap": canonical_entry.get("times_gap", 0),
        }
        examples = keyword_examples.get(key, {})
        translation_ready = bool(curated.get("pt_br_preferred"))
        recommendation = "review"
        if translation_ready:
            recommendation = "active"
        elif stats["times_missing_cv"] >= max(1, stats["times_covered_cv"]):
            recommendation = "high_priority"

        candidates.append(
            {
                "canonical_key": key,
                "keyword": keyword,
                "translation_ready": translation_ready,
                "recommended_action": recommendation,
                "pt_br_preferred": curated.get("pt_br_preferred"),
                "pt_br_alternatives": curated.get("pt_br_alternatives", []),
                "accepted_variants": curated.get("accepted_variants", []),
                "usage_notes": curated.get("usage_notes", ""),
                "sample_application_keys": examples.get("applications", [])[:8],
                "sample_experience_targets": [
                    target for target, _count in examples.get("experience_targets", Counter()).most_common(6)
                ],
                "sample_origins": [
                    origin for origin, _count in examples.get("origins", Counter()).most_common(6)
                ],
                "stats": stats,
            }
        )

    candidates.sort(
        key=lambda item: (
            0 if item["translation_ready"] else 1,
            0 if item["recommended_action"] == "high_priority" else 1,
            -(item["stats"]["times_extracted"]),
            item["keyword"].casefold(),
        )
    )

    return {
        "version": 1,
        "generated_from_registry_at": keyword_registry.get("last_updated"),
        "curated_registry_version": translation_registry.get("version", 1),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
