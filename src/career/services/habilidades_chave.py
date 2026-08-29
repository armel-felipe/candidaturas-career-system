from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.utils import ValidationFailure, read_json
from career.services.positioning_pack import artifact_claim_text, artifact_provenance, validate_positioning_pack


def build_from_fit_map(fit_map: dict[str, Any], *, normalized_pack: dict[str, Any] | None = None) -> str:
    """Build a compact, application-cellular skills handover from FIT_MAP."""
    cargo = str(fit_map.get("cargo") or "Cargo")
    empresa = str(fit_map.get("empresa") or "Empresa")
    entries = fit_map.get("keywords_habilidade_ats")
    if not isinstance(entries, list):
        entries = fit_map.get("keywords_para_ats", [])
    skills = []
    for item in entries:
        value = item.get("keyword") if isinstance(item, dict) else item
        value = str(value or "").strip()
        if value and value not in skills:
            skills.append(value)
    if not skills:
        skills = ["Operações", "Planejamento", "Dados"]
    keyword_pack = (normalized_pack or {}).get("job_keywords") or {}
    normalized_keywords = [str(item).strip() for item in keyword_pack.get("top_focus_terms", []) if str(item).strip()]
    evidence_line = ", ".join(normalized_keywords[:3]) or "contexto normalizado da vaga"
    content = "\n".join(
        [f"# Habilidades-chave — {cargo} — {empresa}", "", "## Habilidades priorizadas"]
        + [f"- {skill}" for skill in skills[:15]]
        + ["", "## Evidência", f"- Seleção derivada do FIT_MAP aprovado e do contexto: {evidence_line}.", ""]
    )
    positioning = (normalized_pack or {}).get("positioning_pack")
    if isinstance(positioning, dict):
        content += "\n## Estratégia de posicionamento\n- " + artifact_claim_text(positioning) + "\n"
    return content


def build_from_positioning_pack(pack: dict[str, Any]) -> dict[str, Any]:
    validated = validate_positioning_pack(pack)
    capabilities = [
        str(capability).strip()
        for story in validated["stories"]
        for capability in (story.get("capabilities") or [])
        if str(capability).strip()
    ]
    content = "\n".join(
        [
            "Habilidades derivadas do posicionamento:",
            *[f"- {item}" for item in dict.fromkeys(capabilities)],
            f"- Claim: {artifact_claim_text(validated)}",
        ]
    )
    return {"content": content, "provenance": artifact_provenance(validated)}


def validate_cellular_artifact(content: str, fit_map: dict[str, Any] | None = None, evidence: dict[str, Any] | None = None) -> None:
    """Apply the local skills policy to the compact cellular output."""
    if not isinstance(content, str) or not content.strip():
        raise ValidationFailure("habilidades cellular artifact is empty")
    if "# Habilidades-chave" not in content or "## Habilidades priorizadas" not in content:
        raise ValidationFailure("habilidades cellular artifact misses required sections")
    if "[" in content or "]" in content:
        raise ValidationFailure("habilidades cellular artifact contains placeholders")
    skills = []
    in_prioritized = False
    for line in content.splitlines():
        if line.strip() == "## Habilidades priorizadas":
            in_prioritized = True
            continue
        if line.startswith("## "):
            in_prioritized = False
        if in_prioritized and line.startswith("- "):
            skills.append(line[2:].strip())
    prioritized = skills[:15]
    if len(prioritized) < 2 or len(set(prioritized)) != len(prioritized):
        raise ValidationFailure("habilidades cellular artifact lacks distinct prioritized skills")
    if fit_map is not None:
        entries = fit_map.get("keywords_habilidade_ats") or fit_map.get("keywords_para_ats") or []
        allowed = {
            str(item.get("keyword") if isinstance(item, dict) else item).strip().casefold()
            for item in entries
        }
        if allowed and any(skill.casefold() not in allowed for skill in prioritized):
            raise ValidationFailure("habilidades cellular artifact contains unsupported skill")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValidationFailure("habilidades cellular evidence is invalid")


GUPY_CATALOG = ROOT / ".agents" / "skills" / "career-system" / "references" / "habilidades_gupy.json"
MERCADO_LIVRE_CATALOG = ROOT / ".agents" / "skills" / "habilidades-chave" / "references" / "habilidades_mercado_livre.json"
REQUIRED_REFERENCES = [
    ROOT / ".agents" / "skills" / "career-system" / "references" / "dicionario_palavras_chave_mercado.md",
    ROOT / ".agents" / "skills" / "career-system" / "references" / "palavras_chave_carreira.md",
    ROOT / ".agents" / "skills" / "career-system" / "references" / "autoconhecimento.md",
    ROOT / ".agents" / "skills" / "career-system" / "references" / "perfil_restricoes.md",
    ROOT / ".agents" / "skills" / "habilidades-chave" / "references" / "story-building-template.md",
]


ITEM_RE = re.compile(
    r"(?ms)^\s*(\d+)\.\s+Habilidade:\s*(?P<habilidade>.+?)\s*^Cargo:\s*(?P<cargo>.+?)\s*^Empresa:\s*(?P<empresa>.+?)\s*^História\s*\((?P<count>\d+)\s+caracteres\):\s*(?P<historia>.*?)(?=^\s*\d+\.\s+Habilidade:|\Z)"
)
SOURCE_RE = re.compile(r"\(Fonte:\s*autoconhecimento\.md:linhas\s+\d+-\d+(?:,\s*\d+)*\)")


def _catalog_path(mode: str) -> Path:
    if mode == "gupy":
        return GUPY_CATALOG
    if mode == "mercado_livre":
        return MERCADO_LIVRE_CATALOG
    raise ValidationFailure("mode must be one of: gupy, mercado_livre")


def _load_catalog(mode: str) -> list[str]:
    payload = read_json(_catalog_path(mode))
    habilidades = payload.get("habilidades")
    if not isinstance(habilidades, list) or not all(isinstance(item, str) for item in habilidades):
        raise ValidationFailure(f"Invalid habilidades catalog for mode {mode}.")
    return habilidades


def check_environment(fit_map_path: Path = CAREER_STATE / "fit_map.json") -> dict[str, Any]:
    missing = [str(path.relative_to(ROOT)) for path in [fit_map_path, GUPY_CATALOG, MERCADO_LIVRE_CATALOG, *REQUIRED_REFERENCES] if not path.exists()]
    if missing:
        raise ValidationFailure("habilidades-chave prerequisites missing:\n- " + "\n- ".join(missing))
    fit_map = read_json(fit_map_path)
    for field in ["cargo", "empresa", "keywords_para_ats", "historias_selecionadas"]:
        if field not in fit_map:
            raise ValidationFailure(f"FIT_MAP missing required field for habilidades-chave: {field}")
    return {
        "status": "ok",
        "fit_map": str(fit_map_path),
        "cargo": fit_map.get("cargo"),
        "empresa": fit_map.get("empresa"),
        "gupy_catalog_items": len(_load_catalog("gupy")),
        "mercado_livre_catalog_items": len(_load_catalog("mercado_livre")),
    }


def _extract_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for match in ITEM_RE.finditer(text):
        historia = " ".join(match.group("historia").strip().split())
        items.append(
            {
                "habilidade": match.group("habilidade").strip(),
                "cargo": match.group("cargo").strip(),
                "empresa": match.group("empresa").strip(),
                "declared_count": int(match.group("count")),
                "historia": historia,
                "actual_count": len(historia),
            }
        )
    return items


def validate_artifact(
    artifact: Path,
    mode: str,
    expected_count: int | None = None,
    fit_map_path: Path = CAREER_STATE / "fit_map.json",
) -> dict[str, Any]:
    check_environment(fit_map_path)
    if not artifact.exists():
        raise ValidationFailure(f"Artifact not found: {artifact}")
    text = artifact.read_text(encoding="utf-8")
    catalog = set(_load_catalog(mode))
    expected = expected_count if expected_count is not None else 10
    items = _extract_items(text)
    failures: list[str] = []
    if len(items) != expected:
        failures.append(f"expected {expected} habilidade items, found {len(items)}")
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        habilidade = item["habilidade"]
        if habilidade not in catalog:
            failures.append(f"item {index}: habilidade outside {mode} catalog: {habilidade}")
        if habilidade in seen:
            failures.append(f"item {index}: duplicated habilidade: {habilidade}")
        seen.add(habilidade)
        actual_count = item["actual_count"]
        declared_count = item["declared_count"]
        if actual_count != declared_count:
            failures.append(f"item {index}: declared {declared_count} chars but actual count is {actual_count}")
        if actual_count < 500 or actual_count > 700:
            failures.append(f"item {index}: historia must have 500-700 chars, got {actual_count}")
        if not SOURCE_RE.search(item["historia"]):
            failures.append(f"item {index}: missing source citation '(Fonte: autoconhecimento.md:linhas X-Y)'")
        if not item["cargo"] or not item["empresa"]:
            failures.append(f"item {index}: cargo and empresa are required")
    if failures:
        raise ValidationFailure("habilidades-chave artifact validation failed:\n- " + "\n- ".join(failures))
    return {
        "status": "ok",
        "artifact": str(artifact),
        "mode": mode,
        "expected_count": expected,
        "items": len(items),
    }
