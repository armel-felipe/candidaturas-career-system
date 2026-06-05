#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


DEFAULT_OUTPUT = Path(".career-state/fit_map.json")

TOP_LEVEL_ORDER = [
    "cargo",
    "empresa",
    "modo",
    "dor_central",
    "keywords_vaga",
    "competencias_vaga",
    "keywords_para_ats",
    "mapa_ajuste",
    "objecoes",
    "nota_aderencia",
    "gaps_sem_cobertura",
    "historias_selecionadas",
    "keywords_habilidade_ats",
]

STORY_KEYS = ["principal", "secundaria", "terceira"]
ADJUSTMENT_KEYS = [
    "termo_vaga",
    "tipo_ajuste",
    "evidencia",
    "empresa_origem",
    "resultado_numero",
    "angulo_sugerido",
    "ajustes_feitos",
    "defensavel",
]
OBJECTION_KEYS = [
    "objecao",
    "classificacao",
    "origem",
    "mitigacao",
    "evidencia_real",
]
STORY_FIELD_KEYS = [
    "empresa",
    "resultado",
    "keywords_cobertas",
    "angulo",
    "ajustes",
]
ATS_KEYS = [
    "keyword",
    "prioridade",
    "experiencia_alvo",
    "bullet_sugerido",
    "origem",
]

KEYWORD_ORIGINS = {"titulo", "requisitos", "responsabilidades", "diferenciais"}
COMPETENCY_TYPES = {"hard skill", "soft skill", "ferramenta", "setor"}
ADJUSTMENT_TYPES = {"DIRETO", "REPOSICIONAMENTO", "GAP"}
OBJECTION_CLASSES = {"forte", "media", "média", "fraca"}
ATS_ORIGINS = {"já selecionada", "adicionada por densidade", "gap sem cobertura"}
ATS_BULLET_SLOTS = {"Responsável", "Utilizando", "Consegui", "Resumo", "Stack"}

COMPETENCY_TYPE_ALIASES = {
    "hard": "hard skill",
    "hard skill": "hard skill",
    "soft": "soft skill",
    "soft skill": "soft skill",
    "requisito": "hard skill",
    "requisitos": "hard skill",
    "qualificacao": "hard skill",
    "qualificacoes": "hard skill",
    "qualificação": "hard skill",
    "qualificações": "hard skill",
    "idioma": "hard skill",
    "ferramenta": "ferramenta",
    "tool": "ferramenta",
    "setor": "setor",
    "contexto": "setor",
    "context": "setor",
}

KEYWORD_ORIGIN_ALIASES = {
    "titulo": "titulo",
    "título": "titulo",
    "requisitos": "requisitos",
    "responsabilidades": "responsabilidades",
    "diferenciais": "diferenciais",
    "descricao": "responsabilidades",
    "descrição": "responsabilidades",
    "corpo": "responsabilidades",
    "job description": "responsabilidades",
    "sobre a vaga": "responsabilidades",
    "resumo da vaga": "responsabilidades",
}

OBJECTION_CLASS_ALIASES = {
    "forte": "forte",
    "media": "media",
    "média": "média",
    "fraca": "fraca",
}

ATS_ORIGIN_ALIASES = {
    "ja selecionada": "já selecionada",
    "já selecionada": "já selecionada",
    "adicionada por densidade": "adicionada por densidade",
    "gap sem cobertura": "gap sem cobertura",
}

ATS_BULLET_ALIASES = {
    "responsavel": "Responsável",
    "responsável": "Responsável",
    "utilizando": "Utilizando",
    "consegui": "Consegui",
    "resumo": "Resumo",
    "stack": "Stack",
}


def default_adjustment_steps(payload: dict) -> list[str]:
    if payload.get("tipo_ajuste") == "GAP":
        return []

    term = str(payload.get("termo_vaga") or "o requisito da vaga").strip()
    angle = str(payload.get("angulo_sugerido") or "").strip().rstrip(".")
    adjustment_type = str(payload.get("tipo_ajuste") or "").strip().upper()

    if adjustment_type == "DIRETO":
        return [f"usar evidência direta para {term} sem ampliar escopo além da experiência comprovada"]
    if angle and angle != "-":
        return [f"reposicionar a experiência destacando {angle}"]
    return [f"adaptar o vocabulário da experiência para {term} sem inventar escopo"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fold_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_whitespace(value).casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def as_string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return normalize_whitespace(str(value))


def as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "sim", "yes"}:
            return True
        if lowered in {"false", "0", "nao", "não", "no"}:
            return False
    return default


def as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        normalized = normalize_whitespace(item)
        if not normalized:
            continue
        marker = normalized.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(normalized)
    return result


def fail(message: str) -> None:
    raise ValueError(message)


def require_non_empty_string(value: object, field_name: str) -> str:
    normalized = as_string(value)
    if not normalized:
        fail(f"{field_name} must be a non-empty string")
    return normalized


def require_list(value: object, field_name: str) -> list:
    if not isinstance(value, list):
        fail(f"{field_name} must be an array")
    return value


def require_dict(value: object, field_name: str) -> dict:
    if not isinstance(value, dict):
        fail(f"{field_name} must be an object")
    return value


def require_choice(value: str, choices: set[str], field_name: str) -> str:
    if value not in choices:
        fail(f"{field_name} must be one of: {', '.join(sorted(choices))}")
    return value


def normalize_choice(value: object, field_name: str, choices: set[str], aliases: dict[str, str] | None = None) -> str:
    raw = require_non_empty_string(value, field_name)
    alias_map = aliases or {}
    direct = alias_map.get(raw)
    if direct is not None:
        return require_choice(direct, choices, field_name)

    folded = fold_label(raw)
    for key, canonical in alias_map.items():
        if fold_label(key) == folded:
            return require_choice(canonical, choices, field_name)
    for choice in choices:
        if fold_label(choice) == folded:
            return choice

    fail(
        f"{field_name} must be one of: {', '.join(sorted(choices))}. "
        f"Received: {raw!r}"
    )


def normalize_ats_bullet_slot(value: object, field_name: str) -> str:
    raw = require_non_empty_string(value, field_name)
    folded = fold_label(raw)
    for key, canonical in ATS_BULLET_ALIASES.items():
        key_folded = fold_label(key)
        if folded == key_folded or folded.startswith(key_folded + " "):
            return require_choice(canonical, ATS_BULLET_SLOTS, field_name)
    if re.search(r"\b(sql|python|databricks|grafana|api|vba|power bi|excel)\b", folded):
        return "Utilizando"
    if re.search(r"\b(reduziu|reduzir|escalou|escalar|atingiu|atingir|melhorou|melhorar|gerou|gerar)\b", folded):
        return "Consegui"
    if re.search(r"\b(formacao|mba|six sigma|certificacao|certificado)\b", folded):
        return "Stack"
    if len(raw.split()) > 1:
        return "Responsável"
    return normalize_choice(raw, field_name, ATS_BULLET_SLOTS, ATS_BULLET_ALIASES)


def validate_priority_sequence(entries: list[dict], field_name: str) -> None:
    priorities = [entry["prioridade"] for entry in entries]
    if len(priorities) != len(set(priorities)):
        fail(f"{field_name} contains duplicate priorities")
    expected = list(range(1, len(entries) + 1))
    if sorted(priorities) != expected:
        fail(f"{field_name} priorities must form a contiguous sequence starting at 1")


def normalize_keyword_entries(entries: object) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(require_list(entries, "keywords_vaga")):
        payload = require_dict(item, f"keywords_vaga[{index}]")
        term = require_non_empty_string(
            payload.get("termo") or payload.get("keyword"),
            f"keywords_vaga[{index}].termo",
        )
        origin = normalize_choice(
            payload.get("origem") or payload.get("origem_keyword"),
            f"keywords_vaga[{index}].origem",
            KEYWORD_ORIGINS,
            KEYWORD_ORIGIN_ALIASES,
        )
        normalized.append({"termo": term, "origem": origin})
    unique: list[dict] = []
    seen: set[str] = set()
    for item in normalized:
        marker = item["termo"].casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    return unique


def normalize_competencies(entries: object) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(require_list(entries, "competencias_vaga")):
        payload = require_dict(item, f"competencias_vaga[{index}]")
        competence = require_non_empty_string(
            payload.get("competencia") or payload.get("competency"),
            f"competencias_vaga[{index}].competencia",
        )
        kind = normalize_choice(
            payload.get("tipo") or payload.get("type"),
            f"competencias_vaga[{index}].tipo",
            COMPETENCY_TYPES,
            COMPETENCY_TYPE_ALIASES,
        )
        normalized.append({"competencia": competence, "tipo": kind})
    return normalized


def normalize_adjustments(entries: object) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(require_list(entries, "mapa_ajuste")):
        payload_src = require_dict(item, f"mapa_ajuste[{index}]")
        adjustment_type = require_non_empty_string(
            payload_src.get("tipo_ajuste"),
            f"mapa_ajuste[{index}].tipo_ajuste",
        ).upper()
        require_choice(adjustment_type, ADJUSTMENT_TYPES, f"mapa_ajuste[{index}].tipo_ajuste")
        payload = {
            "termo_vaga": require_non_empty_string(
                payload_src.get("termo_vaga"),
                f"mapa_ajuste[{index}].termo_vaga",
            ),
            "tipo_ajuste": adjustment_type,
            "evidencia": require_non_empty_string(
                payload_src.get("evidencia"),
                f"mapa_ajuste[{index}].evidencia",
            ),
            "empresa_origem": require_non_empty_string(
                payload_src.get("empresa_origem"),
                f"mapa_ajuste[{index}].empresa_origem",
            ),
            "resultado_numero": require_non_empty_string(
                payload_src.get("resultado_numero"),
                f"mapa_ajuste[{index}].resultado_numero",
            ),
            "angulo_sugerido": require_non_empty_string(
                payload_src.get("angulo_sugerido"),
                f"mapa_ajuste[{index}].angulo_sugerido",
            ),
            "ajustes_feitos": unique_strings(
                [
                    require_non_empty_string(v, f"mapa_ajuste[{index}].ajustes_feitos[]")
                    for v in require_list(
                        payload_src.get("ajustes_feitos") if payload_src.get("ajustes_feitos") is not None else [],
                        f"mapa_ajuste[{index}].ajustes_feitos",
                    )
                ]
            ),
            "defensavel": payload_src.get("defensavel"),
        }
        if not isinstance(payload["defensavel"], bool):
            fail(f"mapa_ajuste[{index}].defensavel must be boolean")
        if payload["tipo_ajuste"] == "GAP" and payload["defensavel"]:
            fail(f"mapa_ajuste[{index}] with tipo_ajuste=GAP must have defensavel=false")
        if payload["tipo_ajuste"] != "GAP" and not payload["ajustes_feitos"]:
            payload["ajustes_feitos"] = default_adjustment_steps(payload)
        normalized.append(payload)
    return normalized


def normalize_objections(entries: object) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(require_list(entries, "objecoes")):
        payload_src = require_dict(item, f"objecoes[{index}]")
        classification = normalize_choice(
            payload_src.get("classificacao"),
            f"objecoes[{index}].classificacao",
            OBJECTION_CLASSES,
            OBJECTION_CLASS_ALIASES,
        )
        payload = {
            "objecao": require_non_empty_string(payload_src.get("objecao"), f"objecoes[{index}].objecao"),
            "classificacao": classification,
            "origem": require_non_empty_string(payload_src.get("origem"), f"objecoes[{index}].origem"),
            "mitigacao": require_non_empty_string(payload_src.get("mitigacao"), f"objecoes[{index}].mitigacao"),
            "evidencia_real": require_non_empty_string(payload_src.get("evidencia_real"), f"objecoes[{index}].evidencia_real"),
        }
        normalized.append(payload)
    if len(normalized) > 5:
        severity_rank = {"forte": 0, "media": 1, "média": 1, "fraca": 2}
        ranked = sorted(
            enumerate(normalized),
            key=lambda item: (severity_rank.get(item[1]["classificacao"], 99), item[0]),
        )
        keep_indexes = {index for index, _payload in ranked[:5]}
        normalized = [payload for index, payload in enumerate(normalized) if index in keep_indexes]
    if len(normalized) < 3:
        fail("objecoes must contain at least 3 items")
    return normalized


def normalize_story(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        fail("historias_selecionadas entries must be objects or null")
    payload = {
        "empresa": require_non_empty_string(value.get("empresa"), "historias_selecionadas.*.empresa"),
        "resultado": require_non_empty_string(value.get("resultado"), "historias_selecionadas.*.resultado"),
        "keywords_cobertas": unique_strings(
            [require_non_empty_string(v, "historias_selecionadas.*.keywords_cobertas[]") for v in require_list(value.get("keywords_cobertas"), "historias_selecionadas.*.keywords_cobertas")]
        ),
        "angulo": require_non_empty_string(value.get("angulo"), "historias_selecionadas.*.angulo"),
        "ajustes": unique_strings(
            [require_non_empty_string(v, "historias_selecionadas.*.ajustes[]") for v in require_list(value.get("ajustes"), "historias_selecionadas.*.ajustes")]
        ),
    }
    if not payload["keywords_cobertas"]:
        fail("historias_selecionadas.*.keywords_cobertas must contain at least one item")
    return payload


def normalize_stories(stories: object) -> dict:
    source = require_dict(stories, "historias_selecionadas")
    normalized = {key: normalize_story(source.get(key)) for key in STORY_KEYS}
    if any(value is None for value in normalized.values()):
        fail("historias_selecionadas must define principal, secundaria and terceira")
    return normalized


def normalize_ats_keywords(entries: object) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(require_list(entries, "keywords_habilidade_ats")):
        payload = require_dict(item, f"keywords_habilidade_ats[{index}]")
        keyword = require_non_empty_string(payload.get("keyword"), f"keywords_habilidade_ats[{index}].keyword")
        marker = keyword.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        priority = payload.get("prioridade")
        if not isinstance(priority, int):
            fail(f"keywords_habilidade_ats[{index}].prioridade must be an integer")
        if priority < 1:
            fail(f"keywords_habilidade_ats[{index}].prioridade must be >= 1")
        origin = normalize_choice(
            payload.get("origem"),
            f"keywords_habilidade_ats[{index}].origem",
            ATS_ORIGINS,
            ATS_ORIGIN_ALIASES,
        )
        bullet_slot = normalize_ats_bullet_slot(
            payload.get("bullet_sugerido"),
            f"keywords_habilidade_ats[{index}].bullet_sugerido",
        )
        normalized.append(
            {
                "keyword": keyword,
                "prioridade": priority,
                "experiencia_alvo": require_non_empty_string(
                    payload.get("experiencia_alvo"),
                    f"keywords_habilidade_ats[{index}].experiencia_alvo",
                ),
                "bullet_sugerido": bullet_slot,
                "origem": origin,
            }
        )

    def sort_key(item: dict) -> tuple[int, str]:
        priority = item["prioridade"] if isinstance(item["prioridade"], int) else 10**6
        return priority, item["keyword"].casefold()

    normalized = sorted(normalized, key=sort_key)
    if len(normalized) != 15:
        fail("keywords_habilidade_ats must contain exactly 15 items")
    validate_priority_sequence(normalized, "keywords_habilidade_ats")
    return normalized


def normalize_score_item(value: object) -> dict | None:
    payload = require_dict(value, "nota_aderencia item")
    item = require_non_empty_string(payload.get("item"), "nota_aderencia item.item")
    nota = value.get("nota")
    if nota in {0, 0.0, 0.5, 1, 1.0}:
        normalized_note = float(nota)
    else:
        try:
            numeric_note = float(nota)
        except (TypeError, ValueError):
            fail("nota_aderencia item.nota must be 0, 0.5, or 1")
        if numeric_note <= 0:
            normalized_note = 0.0
        elif numeric_note >= 1:
            normalized_note = 1.0
        else:
            normalized_note = 0.5
    tipo = require_non_empty_string(payload.get("tipo"), "nota_aderencia item.tipo").upper()
    require_choice(tipo, ADJUSTMENT_TYPES, "nota_aderencia item.tipo")
    prova_literal = payload.get("prova_literal")
    if not isinstance(prova_literal, bool):
        fail("nota_aderencia item.prova_literal must be boolean")
    payload = {
        "item": item,
        "tipo": tipo,
        "evidencia": require_non_empty_string(value.get("evidencia"), "nota_aderencia item.evidencia"),
        "resultado": require_non_empty_string(value.get("resultado"), "nota_aderencia item.resultado"),
        "nota": normalized_note,
        "prova_literal": prova_literal,
        "fonte_base": require_non_empty_string(value.get("fonte_base"), "nota_aderencia item.fonte_base"),
    }
    if payload["nota"] == 1.0 and (payload["tipo"] != "DIRETO" or not payload["prova_literal"]):
        payload["nota"] = 0.5
    return payload


def normalize_score_gap(value: object) -> dict | None:
    payload = require_dict(value, "nota_aderencia gap")
    gap = require_non_empty_string(payload.get("gap"), "nota_aderencia gap.gap")
    severity = require_non_empty_string(payload.get("severidade"), "nota_aderencia gap.severidade").lower()
    require_choice(severity, {"forte", "media", "média", "fraca", "leve"}, "nota_aderencia gap.severidade")
    return {
        "gap": gap,
        "severidade": severity,
    }


def normalize_score(payload: object) -> object:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        fail("nota_aderencia must be an object")

    dimensions = payload.get("dimensoes")
    if not isinstance(dimensions, dict):
        fail("nota_aderencia.dimensoes must be an object")

    normalized_dimensions = {}
    item_dimensions = [
        "requisitos_obrigatorios",
        "responsabilidades_principais",
        "diferenciais_desejaveis",
    ]
    for key in item_dimensions:
        source = dimensions.get(key, {})
        require_dict(source, f"nota_aderencia.dimensoes.{key}")
        items = [item for item in (normalize_score_item(v) for v in as_list(source.get("itens"))) if item]
        if not items:
            fail(f"nota_aderencia.dimensoes.{key}.itens must contain at least one item")
        normalized_dimensions[key] = {"itens": items}

    gap_source = dimensions.get("ausencia_gaps_criticos", {})
    require_dict(gap_source, "nota_aderencia.dimensoes.ausencia_gaps_criticos")
    gaps = [gap for gap in (normalize_score_gap(v) for v in as_list(gap_source.get("gaps"))) if gap]
    normalized_dimensions["ausencia_gaps_criticos"] = {"gaps": gaps}

    final_value = payload.get("final")
    if not isinstance(final_value, (int, float)):
        final_value = None
    return {
        "final": final_value,
        "dimensoes": normalized_dimensions,
    }


def derive_keywords_for_ats(data: dict) -> list[str]:
    direct_keywords = [item["keyword"] for item in data["keywords_habilidade_ats"] if item["keyword"]]
    if direct_keywords:
        return unique_strings(direct_keywords)
    fallback = [item["termo"] for item in data["keywords_vaga"] if item["termo"]]
    return unique_strings(fallback)


def canonical_fit_map(draft: dict) -> dict:
    if not isinstance(draft, dict):
        fail("Draft root must be an object")
    meta = draft.get("_meta", {}) if isinstance(draft.get("_meta"), dict) else {}
    metadata = draft.get("metadata", {}) if isinstance(draft.get("metadata"), dict) else {}
    cargo_val = draft.get("cargo") or meta.get("vaga") or meta.get("role") or metadata.get("role") or metadata.get("title") or draft.get("role") or draft.get("title") or draft.get("vaga") or ""
    empresa_val = draft.get("empresa") or meta.get("empresa") or meta.get("company") or metadata.get("company") or metadata.get("empresa") or draft.get("company") or ""
    modo_val = draft.get("modo") or meta.get("modo") or metadata.get("modo") or "vaga_especifica"
    dor_val = draft.get("dor_central") or meta.get("dor_central") or metadata.get("dor_central") or ""
    data: dict = {
        "cargo": require_non_empty_string(cargo_val, "cargo"),
        "empresa": require_non_empty_string(empresa_val, "empresa"),
        "modo": require_non_empty_string(modo_val, "modo"),
        "dor_central": require_non_empty_string(dor_val, "dor_central"),
        "keywords_vaga": normalize_keyword_entries(draft.get("keywords_vaga")),
        "competencias_vaga": normalize_competencies(draft.get("competencias_vaga")),
        "keywords_para_ats": [],
        "mapa_ajuste": normalize_adjustments(draft.get("mapa_ajuste")),
        "objecoes": normalize_objections(draft.get("objecoes")),
        "nota_aderencia": normalize_score(draft.get("nota_aderencia")),
        "gaps_sem_cobertura": unique_strings([as_string(v) for v in as_list(draft.get("gaps_sem_cobertura"))]),
        "historias_selecionadas": normalize_stories(draft.get("historias_selecionadas")),
        "keywords_habilidade_ats": normalize_ats_keywords(draft.get("keywords_habilidade_ats")),
    }
    data["keywords_para_ats"] = derive_keywords_for_ats(data)
    if len(data["mapa_ajuste"]) < 3:
        fail("mapa_ajuste must contain at least 3 entries")
    if not data["gaps_sem_cobertura"]:
        fail("gaps_sem_cobertura must contain at least one item")
    return {key: data[key] for key in TOP_LEVEL_ORDER}


def draft_template() -> dict:
    return {
        "cargo": "[preencher cargo da vaga]",
        "empresa": "[preencher empresa da vaga]",
        "modo": "Modo 1 - vaga especifica",
        "dor_central": "[1-2 frases com o problema central que a empresa quer resolver]",
        "keywords_vaga": [
            {
                "termo": "[keyword literal da vaga]",
                "origem": "titulo | requisitos | responsabilidades | diferenciais"
            }
        ],
        "competencias_vaga": [
            {
                "competencia": "[competencia exigida pela vaga]",
                "tipo": "hard skill | soft skill | ferramenta | setor"
            }
        ],
        "mapa_ajuste": [
            {
                "termo_vaga": "[termo da vaga]",
                "tipo_ajuste": "DIRETO | REPOSICIONAMENTO | GAP",
                "evidencia": "[empresa + historia real da base]",
                "empresa_origem": "[empresa de origem ou '-' se GAP]",
                "resultado_numero": "[numero defensavel ou '-' se GAP]",
                "angulo_sugerido": "[como posicionar essa experiencia]",
                "ajustes_feitos": [
                    "[ajuste narrativo explicito; manter vazio apenas se GAP]"
                ],
                "defensavel": True
            }
        ],
        "objecoes": [
            {
                "objecao": "[o que o recrutador vai pensar]",
                "classificacao": "forte | media | fraca",
                "origem": "[por que essa objecao surge]",
                "mitigacao": "[como mitigar sem inventar]",
                "evidencia_real": "[historia + numero da base]"
            }
        ],
        "nota_aderencia": {
            "final": None,
            "dimensoes": {
                "requisitos_obrigatorios": {
                    "itens": [
                        {
                            "item": "[texto do item da vaga]",
                            "tipo": "DIRETO | REPOSICIONAMENTO | GAP",
                            "evidencia": "[empresa + historia]",
                            "resultado": "[numero defensavel]",
                            "nota": 0.5,
                            "prova_literal": False,
                            "fonte_base": "[arquivo:linhas]"
                        }
                    ]
                },
                "responsabilidades_principais": {
                    "itens": [
                        {
                            "item": "[texto da responsabilidade]",
                            "tipo": "DIRETO | REPOSICIONAMENTO | GAP",
                            "evidencia": "[empresa + historia]",
                            "resultado": "[numero defensavel]",
                            "nota": 0.5,
                            "prova_literal": False,
                            "fonte_base": "[arquivo:linhas]"
                        }
                    ]
                },
                "ausencia_gaps_criticos": {
                    "gaps": [
                        {
                            "gap": "[gap real]",
                            "severidade": "forte | media | fraca | leve"
                        }
                    ]
                },
                "diferenciais_desejaveis": {
                    "itens": [
                        {
                            "item": "[texto do diferencial]",
                            "tipo": "DIRETO | REPOSICIONAMENTO | GAP",
                            "evidencia": "[empresa + historia]",
                            "resultado": "[numero defensavel]",
                            "nota": 0.5,
                            "prova_literal": False,
                            "fonte_base": "[arquivo:linhas]"
                        }
                    ]
                },
            },
        },
        "gaps_sem_cobertura": [
            "[gap real sem cobertura defensavel]"
        ],
        "historias_selecionadas": {
            key: {
                "empresa": "[empresa da historia]",
                "resultado": "[resultado principal validado]",
                "keywords_cobertas": [
                    "[keyword coberta]"
                ],
                "angulo": "[angulo narrativo]",
                "ajustes": [
                    "[ajuste aplicado]"
                ]
            }
            for key in STORY_KEYS
        },
        "keywords_habilidade_ats": [
            {
                "keyword": "[keyword exata para ATS]",
                "prioridade": 1,
                "experiencia_alvo": "[empresa + cargo]",
                "bullet_sugerido": "Responsável | Utilizando | Consegui | Resumo | Stack",
                "origem": "já selecionada | adicionada por densidade | gap sem cobertura"
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Canoniza um draft analitico em um FIT_MAP padronizado."
    )
    parser.add_argument("--draft", help="Arquivo JSON intermediario produzido pelo modelo.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Destino do FIT_MAP final.")
    parser.add_argument(
        "--template",
        action="store_true",
        help="Escreve um template de draft no caminho de --output e sai.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    if args.template:
        write_json(output_path, draft_template())
        print(f"Draft template written: {output_path}")
        return 0

    if not args.draft:
        print("--draft is required unless --template is used.")
        return 1

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft file not found: {draft_path}")
        return 1
    draft = read_json(draft_path)
    fit_map = canonical_fit_map(draft)
    write_json(output_path, fit_map)

    print(f"FIT_MAP written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
