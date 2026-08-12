#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
import re


DIMENSION_SPECS = {
    "requisitos_obrigatorios": {"peso": 4.0, "mode": "items"},
    "responsabilidades_principais": {"peso": 3.0, "mode": "items"},
    "ausencia_gaps_criticos": {"peso": 2.0, "mode": "gaps"},
    "diferenciais_desejaveis": {"peso": 1.0, "mode": "items"},
}

GAP_DISCOUNTS = {
    "forte": 1.0,
    "critico": 1.0,
    "crítico": 1.0,
    "media": 0.5,
    "médio": 0.5,
    "medio": 0.5,
    "fraca": 0.0,
    "leve": 0.0,
    "baixo": 0.0,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def round2(value: float) -> float:
    return round(value + 1e-9, 2)


def normalize_tipo(value: str) -> str:
    return str(value or "").strip().upper()


def cap_note(item: dict) -> tuple[float, list[str]]:
    original = float(item["nota"])
    capped = original
    reasons: list[str] = []

    tipo = normalize_tipo(item.get("tipo", ""))
    prova_literal = bool(item.get("prova_literal", False))

    if original >= 1.0 and tipo != "DIRETO":
        capped = min(capped, 0.5)
        reasons.append("nota_capada_por_tipo_nao_direto")
    if original >= 1.0 and not prova_literal:
        capped = min(capped, 0.5)
        reasons.append("nota_capada_por_falta_de_prova_literal")

    return capped, reasons


AUTO_GAP_RULES = [
    {
        "pattern": re.compile(r"motoristas?|ajudantes?", re.IGNORECASE),
        "gap": "Gestão direta de motoristas e ajudantes sem prova literal na base",
        "severidade": "forte",
    },
    {
        "pattern": re.compile(r"combust[ií]vel|ped[aá]gio|horas extras?", re.IGNORECASE),
        "gap": "Controle literal de custos de rota como combustível, pedágio e horas extras sem prova literal na base",
        "severidade": "media",
    },
    {
        "pattern": re.compile(r"distribui[cç][aã]o.*alimentos?|alimentos?|perec[ií]veis|cadeia fria", re.IGNORECASE),
        "gap": "Experiência específica em distribuição de alimentos/perecíveis sem prova literal na base",
        "severidade": "media",
    },
]


def infer_auto_gaps(dimensions: dict) -> list[dict]:
    auto_gaps: list[dict] = []
    seen: set[str] = set()
    for dimension_name in ("requisitos_obrigatorios", "responsabilidades_principais"):
        payload = dimensions.get(dimension_name, {})
        for item in payload.get("itens", []):
            item_text = str(item.get("item", ""))
            if bool(item.get("prova_literal", False)):
                continue
            for rule in AUTO_GAP_RULES:
                if not rule["pattern"].search(item_text):
                    continue
                marker = rule["gap"].casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                auto_gaps.append({"gap": rule["gap"], "severidade": rule["severidade"]})
    return auto_gaps


def _validate_item_list(items: list, dimension_key: str) -> None:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{dimension_key}.itens must be a non-empty array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{dimension_key}.itens[{index}] must be an object")
        if not isinstance(item.get("item"), str) or not item["item"].strip():
            raise ValueError(f"{dimension_key}.itens[{index}].item must be a non-empty string")
        nota = item.get("nota")
        if nota not in {0, 0.0, 0.5, 1, 1.0}:
            raise ValueError(f"{dimension_key}.itens[{index}].nota must be 0, 0.5, or 1")
        if "prova_literal" in item and not isinstance(item.get("prova_literal"), bool):
            raise ValueError(f"{dimension_key}.itens[{index}].prova_literal must be boolean")
        if "fonte_base" in item and not isinstance(item.get("fonte_base"), str):
            raise ValueError(f"{dimension_key}.itens[{index}].fonte_base must be string")


def score_items_dimension(payload: dict, weight: float, dimension_key: str) -> dict:
    items = deepcopy(payload.get("itens", []))
    _validate_item_list(items, dimension_key)

    item_count = len(items)
    max_item_score = weight / item_count
    sum_scores = 0.0

    for item in items:
        nota = float(item["nota"])
        item["nota_original"] = nota
        effective_note, cap_reasons = cap_note(item)
        item["nota"] = effective_note
        if cap_reasons:
            item["ajustes_regra"] = cap_reasons
        item["nota_maxima"] = round2(max_item_score)
        item["ponderacao"] = round2(effective_note * max_item_score)
        sum_scores += effective_note

    coverage = (sum_scores / item_count) * 100
    points = (sum_scores / item_count) * weight

    return {
        "peso": weight,
        "itens": items,
        "contagem_itens": item_count,
        "soma_notas": round2(sum_scores),
        "cobertura_percentual": round2(coverage),
        "pontos": round2(points),
    }


def score_gaps_dimension(payload: dict, weight: float, auto_gaps: list[dict] | None = None) -> dict:
    gaps = deepcopy(payload.get("gaps", []))
    if not isinstance(gaps, list):
        raise ValueError("ausencia_gaps_criticos.gaps must be an array")
    if auto_gaps:
        existing = {str(g.get("gap", "")).strip().casefold() for g in gaps if isinstance(g, dict)}
        for gap in auto_gaps:
            marker = gap["gap"].casefold()
            if marker not in existing:
                gaps.append(gap)
                existing.add(marker)

    total_discount = 0.0
    normalized_gaps = []
    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            raise ValueError(f"ausencia_gaps_criticos.gaps[{index}] must be an object")
        text = gap.get("gap")
        severity = str(gap.get("severidade", "")).strip().lower()
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"ausencia_gaps_criticos.gaps[{index}].gap must be a non-empty string")
        if severity not in GAP_DISCOUNTS:
            raise ValueError(
                f"ausencia_gaps_criticos.gaps[{index}].severidade must be one of: "
                + ", ".join(sorted(GAP_DISCOUNTS))
            )
        discount = GAP_DISCOUNTS[severity]
        total_discount += discount
        normalized_gaps.append(
            {
                "gap": text.strip(),
                "severidade": gap.get("severidade"),
                "desconto": round2(discount),
            }
        )

    points = max(0.0, weight - total_discount)
    coverage = (points / weight) * 100 if weight else 0.0

    return {
        "peso": weight,
        "gaps": normalized_gaps,
        "desconto_total": round2(total_discount),
        "cobertura_percentual": round2(coverage),
        "pontos": round2(points),
    }


def compute_score(score_payload: dict) -> dict:
    dimensions = score_payload.get("dimensoes")
    if not isinstance(dimensions, dict):
        raise ValueError("nota_aderencia.dimensoes must be an object")

    auto_gaps = infer_auto_gaps(dimensions)
    scored_dimensions = {}
    total_points = 0.0
    for key, spec in DIMENSION_SPECS.items():
        if key not in dimensions:
            raise ValueError(f"nota_aderencia.dimensoes missing: {key}")
        payload = dimensions[key]
        if not isinstance(payload, dict):
            raise ValueError(f"nota_aderencia.dimensoes.{key} must be an object")

        if spec["mode"] == "items":
            scored = score_items_dimension(payload, spec["peso"], key)
        else:
            scored = score_gaps_dimension(payload, spec["peso"], auto_gaps=auto_gaps)
        scored_dimensions[key] = scored
        total_points += scored["pontos"]

    return {
        "final": round2(total_points),
        "dimensoes": scored_dimensions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calcula deterministicamente a nota_aderencia de um FIT_MAP ou draft."
    )
    parser.add_argument("--input", required=True, help="Arquivo JSON de entrada.")
    parser.add_argument("--output", help="Se informado, sobrescreve/gera o JSON com a nota calculada.")
    args = parser.parse_args()

    input_path = Path(args.input)
    data = read_json(input_path)
    score_payload = data.get("nota_aderencia")
    if not isinstance(score_payload, dict):
        raise SystemExit("nota_aderencia must be an object with dimensoes to be scored")

    scored = compute_score(score_payload)
    data["nota_aderencia"] = scored

    if args.output:
        write_json(Path(args.output), data)
        print(f"Scored FIT_MAP written: {args.output}")
    else:
        print(json.dumps(scored, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
