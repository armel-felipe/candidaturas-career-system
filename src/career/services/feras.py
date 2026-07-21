from __future__ import annotations

from pathlib import Path
from typing import Any

from career.paths import OUTPUTS
from career.services import derived_context as derived_context_service
from career.utils import ensure, read_json, utc_now_iso, write_text


def build_from_fit_map(fit_map: dict[str, Any]) -> str:
    """Build the cellular FERAS artifact from an explicit FIT_MAP payload."""
    cargo = str(fit_map.get("cargo") or "Cargo")
    empresa = str(fit_map.get("empresa") or "Empresa")
    stories = fit_map.get("historias_selecionadas") if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    principal = stories.get("principal") if isinstance(stories.get("principal"), dict) else {}
    keywords = [str(item).strip() for item in fit_map.get("keywords_para_ats", []) if str(item).strip()]
    omitted = keywords[5:8] or ["nenhuma relevante omitida no recorte atual"]
    result = str(principal.get("resultado") or "resultados defensáveis de crescimento e eficiência")
    return "\n".join(
        [
            f"# FERAS — {cargo} — {empresa}", "", "## FERAS estruturado",
            "- F: Engenharia química e estratégia aplicada a operações e negócios.",
            f"- E: {result}",
            "- R: Conexão entre dados, execução e crescimento em ambientes complexos.",
            f"- A: Contribuir para a agenda prioritária da {empresa}.",
            "- S: Ampliar impacto com execução consistente e evidência defensável.", "",
            "## Pitch fluido para fala/leitura",
            f"Minha trajetória conecta operações, dados e execução; em especial, {result}. Busco a posição de {cargo} para ampliar esse impacto na {empresa}.", "",
            "## Keywords incorporadas naturalmente", *[f"- {item}" for item in keywords[:5]], "",
            "## Keywords relevantes não usadas", *[f"- {item}" for item in omitted], "",
        ]
    )


def build_current_feras(output_path: Path | None = None) -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    pack = (
        read_json(derived_context_service.FERAS_INPUT_PACK_PATH)
        if derived_context_service.FERAS_INPUT_PACK_PATH.exists()
        else derived_context_service.build_feras_input_pack(active)
    )
    job = pack.get("job_identity", {}) if isinstance(pack.get("job_identity"), dict) else {}
    cargo = str(job.get("cargo") or active.role or "Cargo")
    empresa = str(job.get("empresa") or active.company or "Empresa")
    stories = pack.get("selected_stories", {}) if isinstance(pack.get("selected_stories"), dict) else {}
    principal = stories.get("principal", {}) if isinstance(stories.get("principal"), dict) else {}
    secundaria = stories.get("secundaria", {}) if isinstance(stories.get("secundaria"), dict) else {}
    terciaria = stories.get("terciaria", {}) if isinstance(stories.get("terciaria"), dict) else {}
    keywords = [str(item).strip() for item in (pack.get("keywords_para_ats") or []) if str(item).strip()]
    keywords_used = keywords[:5]
    keywords_omitted = keywords[5:8]

    f_block = "Sou engenheiro químico com MBA em Corporate Strategy e construí minha carreira em operações, planejamento comercial e inteligência de negócios."
    e_block = str(
        principal.get("contexto")
        or "Minha experiência mais aderente combina crescimento, canais, pricing e operação com interface próxima entre negócio, produto e dados."
    )
    r_parts = [
        str(principal.get("resultado") or "").strip(),
        str(secundaria.get("resultado") or "").strip(),
    ]
    r_block = ". ".join(part for part in r_parts if part) or "Entreguei resultados defensáveis de crescimento, eficiência e execução em ambientes complexos."
    a_block = (
        f"Hoje busco um contexto como o da {empresa}, na posição de {cargo}, para conectar estratégia comercial, execução e dados em uma agenda real de crescimento."
    )
    s_source = str(terciaria.get("angulo") or secundaria.get("angulo") or "").strip()
    s_block = (
        f"Meu próximo passo é ampliar impacto em uma cadeira desse porte, combinando construção de negócio com escala e consistência para sustentar minha família com independência financeira. {s_source}".strip()
    )
    if s_block.endswith("."):
        pass
    elif s_source:
        s_block += "."

    fluent = " ".join([f_block, e_block, r_block, a_block, s_block]).strip()
    content = "\n".join(
        [
            f"# FERAS — {cargo} — {empresa}",
            "",
            "## FERAS estruturado",
            f"- F: {f_block}",
            f"- E: {e_block}",
            f"- R: {r_block}",
            f"- A: {a_block}",
            f"- S: {s_block}",
            "",
            "## Pitch fluido para fala/leitura",
            fluent,
            "",
            "## Keywords incorporadas naturalmente",
            *[f"- {item}" for item in keywords_used],
            "",
            "## Keywords relevantes não usadas",
            *([f"- {item}" for item in keywords_omitted] if keywords_omitted else ["- nenhuma relevante omitida no recorte atual"]),
            "",
        ]
    )
    validate_feras_text(content)
    output_path = output_path or OUTPUTS / _output_name(cargo, empresa)
    write_text(output_path, content)
    return {
        "status": "ok",
        "path": str(output_path),
        "created_at": utc_now_iso(),
        "job_fingerprint": active.fingerprint,
        "cargo": cargo,
        "empresa": empresa,
        "keywords_used": keywords_used,
        "keywords_omitted": keywords_omitted,
    }


def validate_feras_text(content: str) -> None:
    lowered = content.casefold()
    forbidden = [
        "minha paixão por",
        "me impulsiona a",
        "sou o profissional ideal",
        "{",
        "}",
    ]
    ensure(not any(term in lowered for term in forbidden), "feras_contains_forbidden_tone_or_placeholders")
    ensure("## feras estruturado" in lowered, "feras_missing_structured_block")
    ensure("## pitch fluido para fala/leitura" in lowered, "feras_missing_fluent_block")
    ensure("## keywords incorporadas naturalmente" in lowered, "feras_missing_keywords_used_block")
    ensure("## keywords relevantes não usadas" in lowered, "feras_missing_keywords_omitted_block")
    ensure("fluente" not in lowered, "feras_overstates_english_level")


def _output_name(cargo: str, empresa: str) -> str:
    return f"felipe_armel_feras_{_slug(cargo)}_{_slug(empresa)}.md"


def _slug(text: str) -> str:
    folded = derived_context_service._normalize(text)
    chars = [char if char.isalnum() else "_" for char in folded]
    return "".join(chars).strip("_") or "arquivo"
