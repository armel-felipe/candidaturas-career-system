from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GENERAL_CV_CLUSTERS = {
    "operacoes_supply_logistica": "Operações / Supply Chain / Logística",
    "planejamento_sop_capacity": "Planejamento / S&OP / Capacity Planning",
    "transformacao_eficiencia": "Transformação / Eficiência / Melhoria Contínua",
    "cx_saas_operations": "CX / SaaS Operations",
    "product_revenue_business_ops": "Product / Revenue / Business Operations",
}

DEFAULT_MODE = "concise"
DEFAULT_BULLET_COUNT = 3
DEFAULT_DOMINANT_CLUSTER = "operacoes_supply_logistica"
EXPANDED_DEFAULT_BULLET_COUNT = 8
MIN_EXPANDED_BULLETS = 4
MAX_EXPANDED_BULLETS = 8
NARRATIVE_BULLET_MIN_CHARS = 270
NARRATIVE_BULLET_MAX_CHARS = 330


class GeneralCvValidationError(SystemExit):
    pass


@dataclass(frozen=True)
class GeneralCvRequest:
    mode: str = DEFAULT_MODE
    bullet_count: int = DEFAULT_BULLET_COUNT
    dominant_cluster: str | None = None


def normalize_cluster(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    if not token:
        return None
    if token in GENERAL_CV_CLUSTERS:
        return token
    lowered = token.casefold()
    for key, label in GENERAL_CV_CLUSTERS.items():
        if lowered == label.casefold():
            return key
    aliases = {
        "operacoes": "operacoes_supply_logistica",
        "operações": "operacoes_supply_logistica",
        "supply": "operacoes_supply_logistica",
        "logistica": "operacoes_supply_logistica",
        "logística": "operacoes_supply_logistica",
        "planejamento": "planejamento_sop_capacity",
        "sop": "planejamento_sop_capacity",
        "s&op": "planejamento_sop_capacity",
        "capacity": "planejamento_sop_capacity",
        "transformacao": "transformacao_eficiencia",
        "transformação": "transformacao_eficiencia",
        "eficiencia": "transformacao_eficiencia",
        "eficiência": "transformacao_eficiencia",
        "melhoria": "transformacao_eficiencia",
        "cx": "cx_saas_operations",
        "saas": "cx_saas_operations",
        "customer": "cx_saas_operations",
        "product": "product_revenue_business_ops",
        "revenue": "product_revenue_business_ops",
        "business": "product_revenue_business_ops",
    }
    return aliases.get(lowered)


def validate_request(mode: str | None, bullet_count: int | None, dominant_cluster: str | None) -> GeneralCvRequest:
    requested_mode = (mode or DEFAULT_MODE).strip().lower()
    if requested_mode == "auto":
        requested_mode = DEFAULT_MODE
    if requested_mode not in {"expanded", "concise"}:
        raise GeneralCvValidationError("mode must be one of: auto, expanded, concise")

    cluster_key = normalize_cluster(dominant_cluster)
    if dominant_cluster and not cluster_key:
        raise GeneralCvValidationError(
            "dominant_cluster must be one of: " + ", ".join(GENERAL_CV_CLUSTERS)
        )

    if requested_mode == "concise":
        cluster_key = cluster_key or DEFAULT_DOMINANT_CLUSTER
        return GeneralCvRequest(mode="concise", bullet_count=3, dominant_cluster=cluster_key)

    count = bullet_count if bullet_count is not None else EXPANDED_DEFAULT_BULLET_COUNT
    if count < MIN_EXPANDED_BULLETS or count > MAX_EXPANDED_BULLETS:
        raise GeneralCvValidationError(
            f"bullet_count for CV geral expandido must be between {MIN_EXPANDED_BULLETS} and {MAX_EXPANDED_BULLETS}"
        )
    return GeneralCvRequest(mode="expanded", bullet_count=count, dominant_cluster=cluster_key)


def strategy_payload(request: GeneralCvRequest) -> dict[str, Any]:
    if request.mode == "concise":
        clusters = [request.dominant_cluster]
        secondary_clusters: list[str] = []
    else:
        clusters = list(GENERAL_CV_CLUSTERS)
        secondary_clusters = [
            key for key in GENERAL_CV_CLUSTERS if key != (request.dominant_cluster or "operacoes_supply_logistica")
        ]
    dominant = request.dominant_cluster or DEFAULT_DOMINANT_CLUSTER
    return {
        "kind": "general_cv_strategy",
        "mode": request.mode,
        "dominant_cluster": dominant,
        "dominant_cluster_label": GENERAL_CV_CLUSTERS[dominant],
        "secondary_clusters": secondary_clusters,
        "clusters": {key: GENERAL_CV_CLUSTERS[key] for key in clusters if key},
        "bullet_count_per_experience": request.bullet_count,
        "bullet_policy": {
            "default_mode": DEFAULT_MODE,
            "concise_default": DEFAULT_BULLET_COUNT,
            "expanded_default": EXPANDED_DEFAULT_BULLET_COUNT,
            "expanded_min": MIN_EXPANDED_BULLETS,
            "expanded_max": MAX_EXPANDED_BULLETS,
            "narrative_bullet_min_chars": NARRATIVE_BULLET_MIN_CHARS,
            "narrative_bullet_max_chars": NARRATIVE_BULLET_MAX_CHARS,
            "concise_bullets_per_experience": 3,
            "no_experience_consolidation": True,
        },
        "keywords_covered_by_cluster": {key: [] for key in clusters if key},
        "status": "mode_rules_ready",
    }


def write_strategy(payload: dict[str, Any], output: Path, report: Path | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(strategy_markdown(payload), encoding="utf-8")


def strategy_markdown(payload: dict[str, Any]) -> str:
    clusters = payload.get("clusters", {})
    secondary = payload.get("secondary_clusters", [])
    lines = [
        "# Estratégia CV geral",
        "",
        f"- Modo usado: {payload.get('mode')}",
        f"- Cluster dominante: {payload.get('dominant_cluster_label')}",
        f"- Bullets por experiência: {payload.get('bullet_count_per_experience')}",
        "- Regra de experiências: não consolidar cargos; selecionar experiências separadas por aderência",
        f"- Clusters secundários: {', '.join(GENERAL_CV_CLUSTERS.get(key, key) for key in secondary) or 'nenhum'}",
        "",
        "## Clusters cobertos",
    ]
    for key, label in clusters.items():
        lines.append(f"- {label} (`{key}`)")
    lines.extend(["", "## Keywords cobertas por cluster"])
    for key, keywords in payload.get("keywords_covered_by_cluster", {}).items():
        label = GENERAL_CV_CLUSTERS.get(key, key)
        value = ", ".join(keywords) if keywords else "a preencher pela rotina de estratégia"
        lines.append(f"- {label}: {value}")
    return "\n".join(lines) + "\n"


def validate_content(payload: dict[str, Any]) -> dict[str, Any]:
    mode = payload.get("mode", DEFAULT_MODE)
    bullet_count = payload.get("bullet_count_per_experience")
    dominant_cluster = payload.get("dominant_cluster")
    request = validate_request(mode, bullet_count, dominant_cluster)
    allowed_clusters = {request.dominant_cluster} if request.mode == "concise" else set(GENERAL_CV_CLUSTERS)

    failures: list[str] = []
    consolidated_markers = [
        "head e diretor",
        "head + diretor",
        "head and director",
        "head & director",
        "s&op | expedicao",
        "s&op | expedição",
        "s&op + expedicao",
        "s&op + expedição",
    ]
    for exp_index, experience in enumerate(payload.get("experiences", []), start=1):
        role = str(experience.get("role", "")).casefold()
        company = str(experience.get("company", "")).casefold()
        period = str(experience.get("period", "")).casefold()
        haystack = f"{role} {company}"
        if any(marker in haystack for marker in consolidated_markers):
            failures.append(f"experiences[{exp_index}] appears to consolidate multiple roles; split roles into separate experiences")
        if "ifood" in company and "2018" in period and "2024" in period:
            failures.append(f"experiences[{exp_index}] uses aggregated iFood period; split Head and Director roles")
        if "trifil" in company and "2006" in period and "2014" in period:
            failures.append(f"experiences[{exp_index}] uses aggregated Trifil period; select separate Trifil roles")
        bullets = experience.get("bullets", [])
        if request.mode == "concise" and len(bullets) != 3:
            failures.append(f"experiences[{exp_index}] must have exactly 3 bullets in concise mode")
        if request.mode == "expanded" and len(bullets) < MIN_EXPANDED_BULLETS:
            failures.append(f"experiences[{exp_index}] has fewer than {MIN_EXPANDED_BULLETS} expanded bullets")
        for bullet_index, bullet in enumerate(bullets, start=1):
            text = str(bullet.get("text", "")).strip()
            cluster = normalize_cluster(str(bullet.get("cluster", "")).strip())
            evidence = str(bullet.get("evidence", "")).strip()
            if request.mode == "expanded" and not (NARRATIVE_BULLET_MIN_CHARS <= len(text) <= NARRATIVE_BULLET_MAX_CHARS):
                failures.append(
                    f"experiences[{exp_index}].bullets[{bullet_index}] must have "
                    f"{NARRATIVE_BULLET_MIN_CHARS}-{NARRATIVE_BULLET_MAX_CHARS} chars, got {len(text)}"
                )
            if not cluster or cluster not in allowed_clusters:
                failures.append(f"experiences[{exp_index}].bullets[{bullet_index}] uses disallowed or unknown cluster")
            if not evidence:
                failures.append(f"experiences[{exp_index}].bullets[{bullet_index}] has no defensible evidence")
    if failures:
        raise GeneralCvValidationError("General CV content validation failed:\n- " + "\n- ".join(failures))
    return {"status": "ok", "mode": request.mode, "bullet_count": request.bullet_count}
