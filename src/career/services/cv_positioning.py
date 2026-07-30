from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, TypedDict

from career.paths import ROOT
from career.utils import ValidationFailure, read_json, sha256_file


CATALOG_PATH = ROOT / ".agents/skills/career-system/references/catalogo_resultados_chave.json"

_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em", "na",
    "nas", "no", "nos", "o", "os", "para", "por", "um", "uma", "que", "responsavel",
}


class Positioning(TypedDict):
    catalog_entry_id: int
    area: str
    caso: str
    score: int
    matched_signals: list[str]
    catalog_sha256: str


def normalize_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1 and token not in _STOPWORDS
    }


def load_catalog(path: Path | None = None) -> list[dict[str, Any]]:
    catalog_path = Path(path or CATALOG_PATH)
    try:
        payload = read_json(catalog_path)
    except Exception as exc:
        raise ValidationFailure(f"positioning_catalog_invalid: {catalog_path}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValidationFailure("positioning_catalog_invalid: expected non-empty list")
    ids: set[int] = set()
    required = ("id", "area", "indice", "casos", "resultado_chave")
    for entry in payload:
        if not isinstance(entry, dict) or any(key not in entry for key in required):
            raise ValidationFailure("positioning_catalog_invalid: required fields")
        entry_id = entry["id"]
        indice = entry["indice"]
        if (
            isinstance(entry_id, bool)
            or not isinstance(entry_id, int)
            or entry_id <= 0
            or entry_id in ids
            or isinstance(indice, bool)
            or not isinstance(indice, int)
            or indice <= 0
        ):
            raise ValidationFailure("positioning_catalog_invalid: ids or indice")
        if any(not isinstance(entry[key], str) or not entry[key].strip() for key in ("area", "casos", "resultado_chave")):
            raise ValidationFailure("positioning_catalog_invalid: empty text")
        ids.add(entry_id)
    return payload


def _strings(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_strings(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_strings(item) for item in value.values())
    return str(value or "")


def _keywords(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return " ".join(str(item.get("keyword") or "") for item in value if isinstance(item, dict))


def _context_signals(fit_map: dict[str, Any], job_description: str) -> list[tuple[str, str, int]]:
    return [
        ("cargo", str(fit_map.get("cargo") or ""), 5),
        ("dor_central", str(fit_map.get("dor_central") or ""), 4),
        ("keywords_ats", _keywords(fit_map.get("keywords_habilidade_ats")), 3),
        ("keywords_vaga", _strings(fit_map.get("keywords_vaga")), 2),
        ("competencias_vaga", _strings(fit_map.get("competencias_vaga")), 2),
        (
            "historias_objecoes",
            _strings({key: fit_map.get(key) for key in ("historias_selecionadas", "objecoes")}),
            1,
        ),
        ("descricao_vaga", job_description, 1),
    ]


def _score_entry(entry: dict[str, Any], signals: list[tuple[str, str, int]]) -> tuple[int, int, list[str]]:
    primary_tokens = normalize_tokens(f"{entry['area']} {entry['casos']}")
    result_tokens = normalize_tokens(str(entry["resultado_chave"]))
    primary_score = 0
    result_score = 0
    matched_signals: list[str] = []
    for label, text, weight in signals:
        tokens = normalize_tokens(text)
        primary_matches = tokens & primary_tokens
        if primary_matches:
            primary_score += len(primary_matches) * weight
            matched_signals.extend(f"{label}: {token}" for token in sorted(primary_matches))
        result_score += len(tokens & result_tokens)
    return primary_score, result_score, matched_signals


def select_positioning(
    fit_map: dict[str, Any], job_description: str, *, catalog_path: Path | None = None
) -> Positioning | None:
    path = Path(catalog_path or CATALOG_PATH)
    signals = _context_signals(fit_map, job_description)
    scored = [(*_score_entry(entry, signals), entry) for entry in load_catalog(path)]
    viable = [item for item in scored if item[0] > 0]
    if not viable:
        return None
    primary_score, _result_score, matched_signals, entry = sorted(
        viable, key=lambda item: (-item[0], -item[1], int(item[3]["id"]))
    )[0]
    return {
        "catalog_entry_id": int(entry["id"]),
        "area": str(entry["area"]),
        "caso": str(entry["casos"]),
        "score": primary_score,
        "matched_signals": matched_signals,
        "catalog_sha256": sha256_file(path),
    }
