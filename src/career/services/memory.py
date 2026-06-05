from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.utils import read_json, write_json


REFERENCES = ROOT / ".opencode" / "skills" / "career-system" / "references"
MEMORY_DIR = CAREER_STATE / "memory"


def _keyword_registry_summary() -> dict[str, Any]:
    registry_path = REFERENCES / "keyword_ats_registry.json"
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
