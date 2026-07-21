from __future__ import annotations

from pathlib import Path
from typing import Any

from career.paths import OUTPUTS
from career.services import derived_context as derived_context_service
from career.utils import ValidationFailure, ensure, read_json, utc_now_iso, write_text


def build_from_fit_map(fit_map: dict[str, Any], *, normalized_pack: dict[str, Any] | None = None) -> str:
    """Build a cellular cover letter without consulting mutable active state."""
    cargo = str(fit_map.get("cargo") or "Cargo")
    empresa = str(fit_map.get("empresa") or "Empresa")
    stories = fit_map.get("historias_selecionadas") if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    principal = stories.get("principal") if isinstance(stories.get("principal"), dict) else {}
    result = str(principal.get("resultado") or "resultados relevantes de crescimento e execução")
    normalized_context = [str(item).strip() for item in (normalized_pack or {}).get("context_lines", []) if str(item).strip()]
    context_phrase = normalized_context[0] if normalized_context else "estratégia, dados e execução"
    return "\n".join(
        [
            "# Carta de Apresentação — Felipe Armel Dias da Silva", "",
            f"Prezada equipe da {empresa},", "",
            f"Tenho interesse na posição de {cargo}. Minha trajetória em operações, planejamento comercial e inteligência de negócios inclui {result}.", "",
            f"A combinação entre {context_phrase} na {empresa} é onde posso contribuir de forma mais direta, com escopo defensável e colaboração transversal.", "",
            "Fico à disposição para conversar. Segue meu currículo em anexo.", "",
            "Atenciosamente,", "", "Felipe Armel Dias da Silva", "",
        ]
    )


def validate_cellular_artifact(content: str, fit_map: dict[str, Any], evidence: dict[str, Any]) -> None:
    validate_cover_letter_text(content)
    cargo = str(fit_map.get("cargo") or "").strip()
    empresa = str(fit_map.get("empresa") or "").strip()
    principal = ((fit_map.get("historias_selecionadas") or {}).get("principal") or {})
    result = str(principal.get("resultado") or "").strip()
    lowered = content.casefold()
    if len(content.strip()) < 240 or "prezada equipe" not in lowered or "atenciosamente" not in lowered:
        raise ValidationFailure("cover_letter_cellular_structure_is_incomplete")
    if not cargo or cargo.casefold() not in lowered or not empresa or empresa.casefold() not in lowered:
        raise ValidationFailure("cover_letter_cellular_missing_job_identity")
    if result and result.casefold() not in lowered:
        raise ValidationFailure("cover_letter_cellular_missing_defensible_evidence")
    if not isinstance(evidence, dict) or evidence.get("application_id") not in {None, fit_map.get("application_id")}:
        raise ValidationFailure("cover_letter_cellular_evidence_is_invalid")


def build_current_cover_letter(output_path: Path | None = None) -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    pack = (
        read_json(derived_context_service.COVER_LETTER_INPUT_PACK_PATH)
        if derived_context_service.COVER_LETTER_INPUT_PACK_PATH.exists()
        else derived_context_service.build_cover_letter_input_pack(active)
    )
    job = pack.get("job_identity", {}) if isinstance(pack.get("job_identity"), dict) else {}
    empresa = str(job.get("empresa") or active.company or "Empresa")
    cargo = str(job.get("cargo") or active.role or "Cargo")
    principal = (pack.get("selected_stories") or {}).get("principal", {}) if isinstance(pack.get("selected_stories"), dict) else {}
    secundaria = (pack.get("selected_stories") or {}).get("secundaria", {}) if isinstance(pack.get("selected_stories"), dict) else {}
    company_context = pack.get("company_context", []) if isinstance(pack.get("company_context"), list) else []
    context_sentence = company_context[0] if company_context else f"a combinação entre impacto setorial e transformação digital da {empresa}"
    primary_result = str(principal.get("resultado") or "resultados relevantes de crescimento e execução")
    secondary_result = str(secundaria.get("resultado") or "melhoria de conversão e eficiência comercial")
    story_angle = str(secundaria.get("angulo") or "a conexão entre vendas, dados e execução")
    output_path = output_path or OUTPUTS / _output_name(cargo, empresa, "md")
    content = "\n".join(
        [
            "# Carta de Apresentação — Felipe Armel Dias da Silva",
            "",
            "Felipe Armel Dias da Silva",
            "",
            "linkedin.com/in/felipearmel",
            "",
            "(11) 98674-8218",
            "",
            "armelfelipe@gmail.com",
            "",
            "",
            f"Prezada equipe da {empresa},",
            "",
            f"Com mais de 20 anos de experiência em operações, planejamento comercial e inteligência de negócios, incluindo {primary_result}, gostaria de compartilhar meu interesse na posição de {cargo}.",
            "",
            f"O que me atrai na {empresa} é {context_sentence}. É exatamente na conexão entre estratégia, execução comercial, dados e crescimento que acredito poder contribuir de forma mais direta.",
            "",
            f"Minha experiência em desenvolvimento de negócios, canais, pricing e pipeline se conecta diretamente com o que a vaga exige. {secondary_result}. Esse histórico sustenta {story_angle}, com números defensáveis e execução em ambiente de alta complexidade.",
            "",
            f"Fico à disposição para conversar sobre como minha trajetória pode contribuir para a {empresa}. Segue meu currículo em anexo.",
            "",
            "",
            "Atenciosamente,",
            "",
            "Felipe Armel Dias da Silva",
            "",
        ]
    )
    validate_cover_letter_text(content)
    write_text(output_path, content)
    return {
        "status": "ok",
        "path": str(output_path),
        "created_at": utc_now_iso(),
        "job_fingerprint": active.fingerprint,
        "cargo": cargo,
        "empresa": empresa,
    }


def validate_cover_letter_text(content: str) -> None:
    lowered = content.casefold()
    forbidden = [
        "espero que estejam bem",
        "minha paixão por",
        "me impulsiona a",
        "estou ansioso para",
        "acredito que posso fazer a diferença",
    ]
    ensure(not any(term in lowered for term in forbidden), "cover_letter_contains_forbidden_tone")
    ensure("{" not in content and "}" not in content, "cover_letter_contains_placeholders")
    ensure("gestor de cs" not in lowered, "cover_letter_uses_forbidden_vivareal_claim")
    ensure("fluente" not in lowered, "cover_letter_overstates_english_level")


def _output_name(cargo: str, empresa: str, ext: str) -> str:
    return f"felipe_armel_cover_letter_{_slug(cargo)}_{_slug(empresa)}.{ext}"


def _slug(text: str) -> str:
    folded = derived_context_service._normalize(text)
    output = []
    for char in folded:
        output.append(char if char.isalnum() else "_")
    return "".join(output).strip("_") or "arquivo"
