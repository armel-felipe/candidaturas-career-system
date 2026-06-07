from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, INBOX, OUTPUTS, ROOT
from career.services import fit_map as fit_map_service
from career.services import habilidades_chave as habilidades_chave_service
from career.services import notion as notion_service
from career.services import review as review_service
from career.utils import ValidationFailure, read_json, utc_now_iso, write_json, write_text


V2_DIR = CAREER_STATE / "applications_v2"
V2_CONFIG = V2_DIR / "config.json"
V2_INDEX = V2_DIR / "index.json"
V2_LOG_DIR = V2_DIR / "_logs"
KEYWORD_REGISTRY = ROOT / ".opencode" / "skills" / "career-system" / "references" / "keyword_ats_registry.json"

DEFAULT_CONFIG = {
    "active_model": "ollama-cloud/deepseek-v4-flash",
    "active_variant": "medium",
    "max_per_run": 2,
    "score_threshold": 6.0,
    "queue_status_aliases": ["Fila Agente", "Aplicação em Análise", "Em análise", "em analise", "Analisando"],
    "reprocess_status_aliases": ["Reprocessar"],
    "running_status": "Fila Agente",
    "low_fit_status": "Aplicação em Análise",
    "success_status": "Aplicação andamento",
    "error_status": "Aplicação em Análise",
    "blocked_review_status": "Aplicação andamento",
    "no_description_status": "Sem descrição de vaga",
    "repair_max_attempts": 2,
    "analysis_runner": {
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    },
    "generation_runner": {
        "command": "hermes",
        "agent": "build",
        "timeout_minutes": 90,
    },
}

STAGE_METADATA = {
    "no_description": {"group": "intake", "status": "blocked", "terminal": True, "retryable": False, "next_action": "move_to_no_description_status"},
    "analyze_pending": {"group": "analyze", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_analyze"},
    "analyze_running": {"group": "analyze", "status": "running", "terminal": False, "retryable": True, "next_action": "await_analyze"},
    "analyze_retry_pending": {"group": "analyze", "status": "retry_pending", "terminal": False, "retryable": True, "next_action": "rerun_analyze"},
    "generate_pending": {"group": "generate", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_generate"},
    "generate_running": {"group": "generate", "status": "running", "terminal": False, "retryable": True, "next_action": "await_generate"},
    "repair_pending": {"group": "repair", "status": "pending", "terminal": False, "retryable": True, "next_action": "run_repair"},
    "repair_running": {"group": "repair", "status": "running", "terminal": False, "retryable": True, "next_action": "await_repair"},
    "blocked_review": {"group": "review", "status": "blocked", "terminal": False, "retryable": True, "next_action": "repair_review_blockers"},
    "blocked_review_exhausted": {"group": "review", "status": "blocked", "terminal": True, "retryable": False, "next_action": "manual_review_required"},
    "low_fit": {"group": "decision", "status": "completed", "terminal": True, "retryable": False, "next_action": "wait_for_reprocess_or_manual_followup"},
    "done": {"group": "finalize", "status": "completed", "terminal": True, "retryable": False, "next_action": None},
    "error": {"group": "error", "status": "failed", "terminal": True, "retryable": False, "next_action": "inspect_error_report"},
}


@dataclass
class ApplicationRecordSchema:
    max_per_run: int | None
    run_agent: bool
    dry_run: bool
    model: str | None = None
    variant: str | None = None


def _emit(message: str) -> None:
    print(f"[applications-v2] {message}", flush=True)


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "item"))
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "item"


def _notion_slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return value or "vaga_sem_nome"


def _normalize_status(value: str) -> str:
    replacements = str.maketrans(
        {"á": "a", "à": "a", "ã": "a", "â": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}
    )
    return " ".join((value or "").casefold().translate(replacements).split())


def _record_key(application: dict[str, Any]) -> str:
    record_id = application.get("record_id")
    if record_id is not None:
        return str(record_id)
    return str(application.get("page_id") or "")


def _app_dir(record_key: str) -> Path:
    return V2_DIR / record_key


def _app_paths(app_dir: Path) -> dict[str, Path]:
    return {
        "manifest": app_dir / "manifest.json",
        "state": app_dir / "state.json",
        "job_description": app_dir / "job_description.md",
        "saved_job_description": app_dir / "saved_job_description_path.txt",
        "fit_map_draft": app_dir / "fit_map.draft.json",
        "fit_map": app_dir / "fit_map.json",
        "analysis_request_json": app_dir / "analysis_request.json",
        "analysis_request_md": app_dir / "analysis_request.md",
        "generation_request_json": app_dir / "generation_request.json",
        "generation_request_md": app_dir / "generation_request.md",
        "repair_request_json": app_dir / "repair_request.json",
        "repair_request_md": app_dir / "repair_request.md",
        "fit_map_notion_payload": app_dir / "fit_map_notion_payload.json",
        "conversation_context": app_dir / "conversation_context.md",
        "cv_content": app_dir / "cv_content.json",
        "feras_formal": app_dir / "feras_formal.md",
        "habilidades_gupy": app_dir / "habilidades_gupy.md",
        "habilidades_mercado_livre": app_dir / "habilidades_mercado_livre.md",
        "cv_review_report": app_dir / "cv_review_report.json",
        "polish_review": app_dir / "polish_review.json",
        "notion_update_payload": app_dir / "notion_update_payload.json",
        "agent_run": app_dir / "agent_run.json",
        "agent_run_analyze": app_dir / "agent_run_analyze.json",
        "agent_run_generate": app_dir / "agent_run_generate.json",
        "agent_run_repair": app_dir / "agent_run_repair.json",
        "run_result": app_dir / "run_result.json",
        "error_report": app_dir / "error_report.json",
        "event_log": app_dir / "event_log.json",
    }


def _set_stage(state: dict[str, Any], stage: str) -> dict[str, Any]:
    metadata = STAGE_METADATA.get(stage, {"group": "unknown", "status": "unknown", "terminal": False, "retryable": False, "next_action": None})
    state["stage"] = stage
    state["stage_group"] = metadata["group"]
    state["stage_status"] = metadata["status"]
    state["terminal"] = metadata["terminal"]
    state["retryable"] = metadata["retryable"]
    state["next_action"] = metadata["next_action"]
    return state


def _write_default_config() -> Path:
    if not V2_CONFIG.exists():
        write_json(V2_CONFIG, DEFAULT_CONFIG)
    return V2_CONFIG


def write_default_config() -> Path:
    return _write_default_config()


def _load_config() -> dict[str, Any]:
    _write_default_config()
    payload = read_json(V2_CONFIG)
    merged = {**DEFAULT_CONFIG, **payload}
    merged["analysis_runner"] = {**DEFAULT_CONFIG["analysis_runner"], **payload.get("analysis_runner", {})}
    merged["generation_runner"] = {**DEFAULT_CONFIG["generation_runner"], **payload.get("generation_runner", {})}
    return merged


def _load_queue(token: str, database_id: str) -> list[dict[str, Any]]:
    payload = notion_service.list_database_applications(token, database_id)
    return payload.get("applications", [])


def _is_reprocess_requested(application: dict[str, Any], config: dict[str, Any]) -> bool:
    aliases = {_normalize_status(item) for item in config.get("reprocess_status_aliases", [])}
    return _normalize_status(str(application.get("status") or "")) in aliases


def _eligible(applications: list[dict[str, Any]], config: dict[str, Any], max_per_run: int | None) -> list[dict[str, Any]]:
    queue_aliases = {_normalize_status(item) for item in config.get("queue_status_aliases", [])}
    reprocess_aliases = {_normalize_status(item) for item in config.get("reprocess_status_aliases", [])}
    selected = []
    for application in applications:
        if application.get("is_archived"):
            continue
        status = _normalize_status(str(application.get("status") or ""))
        if status not in queue_aliases and status not in reprocess_aliases:
            continue
        selected.append(application)

    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        status = _normalize_status(str(item.get("status") or ""))
        priority = 0 if status in reprocess_aliases else 1
        try:
            numeric_record = -int(item.get("record_id") or 0)
        except (TypeError, ValueError):
            numeric_record = 0
        return (priority, numeric_record, str(item.get("page_id") or ""))

    selected.sort(key=sort_key)
    return selected if max_per_run is None else selected[:max_per_run]


def detect_job_language(text: str) -> str:
    normalized = " " + " ".join((text or "").casefold().split()) + " "
    english_markers = [
        " about the role ",
        " about the job ",
        " responsibilities ",
        " requirements ",
        " qualifications ",
        " what you'll ",
        " you will ",
        " we're looking ",
        " cross-functional ",
        " stakeholders ",
        " business operations ",
        " supply chain ",
        " customer success ",
    ]
    portuguese_markers = [
        " sobre a vaga ",
        " responsabilidades ",
        " requisitos ",
        " qualificações ",
        " qualificacoes ",
        " o que buscamos ",
        " buscamos ",
        " você ",
        " voce ",
        " atuação ",
        " atuacao ",
        " experiência ",
        " experiencia ",
    ]
    english_score = sum(normalized.count(marker) for marker in english_markers)
    portuguese_score = sum(normalized.count(marker) for marker in portuguese_markers)
    if english_score > portuguese_score:
        return "en"
    return "pt-BR"


def _write_package(application: dict[str, Any], *, reset: bool = False) -> tuple[Path, dict[str, Path]]:
    record_key = _record_key(application)
    app_dir = _app_dir(record_key)
    if reset and app_dir.exists():
        shutil.rmtree(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    paths = _app_paths(app_dir)
    description = str(application.get("description") or "").strip()
    company = str(application.get("company") or "empresa")
    role = str(application.get("role") or application.get("title") or "cargo")
    job_language = detect_job_language(description) if description else None
    required_cv_language = "en" if job_language == "en" else "pt-BR"
    required_cv_filename_suffix = "_en" if required_cv_language == "en" else ""
    write_text(paths["job_description"], description + ("\n" if description else ""))
    if description:
        saved_job_description = _write_canonical_job_description(description, company=company, role=role)
        write_text(paths["saved_job_description"], str(saved_job_description))
    write_json(
        paths["manifest"],
        {
            "record_key": record_key,
            "record_id": application.get("record_id"),
            "page_id": application.get("page_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
            "status": application.get("status"),
            "job_description_chars": len(description),
            "job_description_language": job_language,
            "required_cv_language": required_cv_language,
            "required_cv_filename_suffix": required_cv_filename_suffix,
            "saved_job_description_path": str(paths["saved_job_description"]) if paths["saved_job_description"].exists() else None,
            "updated_at": utc_now_iso(),
        },
    )
    if not paths["fit_map_draft"].exists():
        write_json(paths["fit_map_draft"], fit_map_service.legacy_build_fit_map.draft_template())
    return app_dir, paths


def _read_state(paths: dict[str, Path], record_key: str, application: dict[str, Any]) -> dict[str, Any]:
    if paths["state"].exists():
        payload = read_json(paths["state"])
        if isinstance(payload, dict):
            if payload.get("stage"):
                _set_stage(payload, str(payload["stage"]))
            return payload
    return _set_stage({
        "record_key": record_key,
        "score": None,
        "status": application.get("status"),
        "review_status": "pending",
        "polish_status": "pending",
        "output_docx": None,
        "notion_status": application.get("status"),
        "last_error": None,
        "retry_count_analyze": 0,
        "repair_attempt_count": 0,
        "updated_at": utc_now_iso(),
    }, "analyze_pending")


def _saved_job_descriptions_dir() -> Path:
    path = INBOX / "job_descriptions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_canonical_job_description(text: str, *, company: str, role: str) -> Path:
    output_dir = _saved_job_descriptions_dir()
    output_path = output_dir / f"{_notion_slug(company or 'empresa')}_{_notion_slug(role or 'cargo')}.md"
    write_text(output_path, text if text.endswith("\n") else text + "\n")
    return output_path


def _sync_saved_job_description(paths: dict[str, Path], *, company: str, role: str) -> Path | None:
    if not paths["job_description"].exists():
        return None
    text = paths["job_description"].read_text(encoding="utf-8")
    if not text.strip():
        return None
    output_path = _write_canonical_job_description(text, company=company, role=role)
    write_text(paths["saved_job_description"], str(output_path))
    return output_path


def _load_saved_job_description_path(paths: dict[str, Path]) -> Path | None:
    if not paths["saved_job_description"].exists():
        return None
    candidate = Path(paths["saved_job_description"].read_text(encoding="utf-8").strip())
    return candidate if str(candidate).strip() and candidate.exists() else None


def _write_state(paths: dict[str, Path], payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    write_json(paths["state"], payload)


def _append_event(paths: dict[str, Path], event_type: str, **data: Any) -> None:
    payload = read_json(paths["event_log"]) if paths["event_log"].exists() else {"events": []}
    payload.setdefault("events", []).append(
        {
            "at": utc_now_iso(),
            "type": event_type,
            "data": data,
        }
    )
    write_json(paths["event_log"], payload)


def _fit_score(path: Path) -> float | None:
    if not path.exists():
        return None
    payload = read_json(path)
    score = payload.get("nota_aderencia", {}).get("final")
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "item"))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _slug(ascii_only)


def _expected_cv_docx_path(paths: dict[str, Path]) -> Path:
    manifest = read_json(paths["manifest"])
    role = str(manifest.get("role") or manifest.get("title") or "vaga")
    company = str(manifest.get("company") or "empresa")
    if paths["fit_map"].exists():
        fit_map = read_json(paths["fit_map"])
        role = str(fit_map.get("cargo") or role)
        company = str(fit_map.get("empresa") or company)
    output_name = f"felipe_armel_cv_{_ascii_slug(role)}_{_ascii_slug(company)}{manifest.get('required_cv_filename_suffix') or ''}.docx"
    return OUTPUTS / output_name


def _is_review_approved(paths: dict[str, Path]) -> bool:
    artifact = _expected_cv_docx_path(paths)
    if not artifact.exists():
        return False
    if not paths["cv_review_report"].exists() or not paths["polish_review"].exists():
        return False
    review_report = read_json(paths["cv_review_report"])
    polish_report = read_json(paths["polish_review"])
    return bool(review_report.get("approved_for_delivery")) and not bool(polish_report.get("approval_blockers"))


def _review_gate_state(paths: dict[str, Path]) -> str:
    artifact = _expected_cv_docx_path(paths)
    if _is_review_approved(paths):
        return "approved"
    if artifact.exists() or paths["cv_review_report"].exists() or paths["polish_review"].exists():
        return "blocked"
    return "pending"


def _persist_job_description_into_fit_map(paths: dict[str, Path]) -> None:
    if not paths["fit_map"].exists() or not paths["job_description"].exists():
        return
    fit_map = read_json(paths["fit_map"])
    if not isinstance(fit_map, dict):
        return
    job_description = paths["job_description"].read_text(encoding="utf-8").strip()
    if not job_description:
        return
    if str(fit_map.get("descricao_vaga") or "").strip() != job_description:
        fit_map["descricao_vaga"] = job_description
        write_json(paths["fit_map"], fit_map)


def _derive_stage(paths: dict[str, Path], config: dict[str, Any]) -> tuple[str, float | None]:
    job_text = paths["job_description"].read_text(encoding="utf-8") if paths["job_description"].exists() else ""
    if not job_text.strip():
        return "no_description", None
    score = _fit_score(paths["fit_map"])
    if score is None:
        return "analyze_pending", None
    if score < float(config["score_threshold"]):
        return "low_fit", score
    review_state = _review_gate_state(paths)
    if review_state == "approved":
        return "done", score
    if review_state == "blocked":
        return "blocked_review", score
    return "generate_pending", score


def _analysis_request(application: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "stage": "analyze",
        "goal": "Editar o fit_map.draft.json desta candidatura e salvar um draft completo e validável.",
        "candidate": {
            "record_id": application.get("record_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
        },
        "inputs": {
            "job_description_path": str(paths["job_description"].relative_to(ROOT)),
        },
        "outputs": {
            "fit_map_draft_path": str(paths["fit_map_draft"].relative_to(ROOT)),
            "allowed_files": [str(paths["fit_map_draft"].relative_to(ROOT))],
        },
        "instructions": [
            "Abra e edite o template existente em fit_map.draft.json.",
            "Salve o arquivo no path exato informado.",
            "Não execute pipeline completo.",
            "Não gere CV, não atualize Notion e não rode validações locais.",
            "Antes de encerrar, confira que o arquivo foi gravado.",
        ],
        "draft_template": fit_map_service.legacy_build_fit_map.draft_template(),
    }


def _analysis_retry_request(application: dict[str, Any], paths: dict[str, Path], validation_error: str) -> dict[str, Any]:
    payload = _analysis_request(application, paths)
    payload["goal"] = "Editar o fit_map.draft.json template existente e salvar um draft completo, sem placeholders."
    payload["instructions"] = [
        "O template existe e continua incompleto; edite o arquivo existente agora.",
        "Substitua todos os placeholders por conteúdo real da vaga e da base.",
        "Não deixe campos com colchetes, enums genéricos ou texto de exemplo.",
        "Salve o arquivo no path exato do fit_map.draft.json antes de encerrar.",
        "Não execute pipeline completo.",
        f"Erro atual de validação: {validation_error}",
    ]
    payload["previous_validation_error"] = validation_error
    return payload


def _generation_request(application: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    manifest = read_json(paths["manifest"])
    fit_map = read_json(paths["fit_map"])
    top8_keywords = [
        {
            "priority": item.get("prioridade"),
            "keyword": item.get("keyword"),
            "experience_target": item.get("experiencia_alvo"),
            "suggested_bullet_slot": item.get("bullet_sugerido"),
        }
        for item in sorted(
            [entry for entry in fit_map.get("keywords_habilidade_ats", []) if isinstance(entry, dict)],
            key=lambda item: int(item.get("prioridade") or 999),
        )[:8]
    ]
    return {
        "stage": "generate",
        "goal": "Gerar somente os artefatos textuais da candidatura a partir do FIT_MAP já aprovado localmente.",
        "candidate": {
            "record_id": application.get("record_id"),
            "title": application.get("title"),
            "company": application.get("company"),
            "role": application.get("role"),
        },
        "fit_map_path": str(paths["fit_map"].relative_to(ROOT)),
        "fit_map_snapshot": {
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "dor_central": fit_map.get("dor_central"),
            "keywords_para_ats": fit_map.get("keywords_para_ats"),
            "objecoes": fit_map.get("objecoes"),
            "historias_selecionadas": fit_map.get("historias_selecionadas"),
            "nota_final": fit_map.get("nota_aderencia", {}).get("final"),
        },
        "required_output": {
            "cv_content_path": str(paths["cv_content"].relative_to(ROOT)),
            "feras_formal_path": str(paths["feras_formal"].relative_to(ROOT)),
            "habilidades_gupy_path": str(paths["habilidades_gupy"].relative_to(ROOT)),
            "habilidades_mercado_livre_path": str(paths["habilidades_mercado_livre"].relative_to(ROOT)),
        },
        "cv_content_contract": {
            "summary": "string",
            "mode": "concise",
            "bullet_count_per_experience": 3,
            "ats_keyword_coverage": [
                {
                    "keyword": "string",
                    "experience_index": "integer (0-based)",
                    "experience_role": "string",
                    "bullet_index": "integer (0-based)",
                    "coverage_mode": "exact | similar | declared_gap",
                    "defensible_evidence": "string",
                }
            ],
            "experiences": [
                {
                    "role": "string",
                    "company": "string",
                    "period": "string",
                    "bullets": [{"text": "string"}],
                }
            ],
            "education": ["string"],
            "languages": ["string"],
        },
        "top8_keywords_must_cover": top8_keywords,
        "instructions": [
            "Leia primeiro o FIT_MAP e a descrição da vaga nos caminhos informados.",
            "Gere somente os artefatos textuais pedidos.",
            "Não renderize DOCX, não rode reviewers e não atualize Notion.",
            f"Use idioma visível {manifest.get('required_cv_language')}.",
            "Mantenha tom factual, direto e defensável.",
            "Para BSP, use somente o ano de conclusão 2017.",
            "Modo padrão obrigatório: concise. Use exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
            "Se você inferir que modo expandido seria melhor, não gere expandido automaticamente; registre a recomendação e peça validação do usuário. Sem confirmação explícita, mantenha concise.",
            "O cv_content.json deve trazer no mínimo 4 e no máximo 8 experiências, mesmo quando o impulso inicial do modelo for sintetizar demais.",
            "Nunca junte experiências, cargos, promoções, fases ou escopos em uma única entrada; se faltar espaço, selecione experiências separadas por aderência.",
            "Títulos compostos como 'Head e Diretor', 'Head + Diretor' ou 'S&OP | Expedição | Supply Chain' são inválidos em cv_content.json.",
            "As 8 keywords-habilidade ATS prioritárias precisam ser alocadas em experiências e bullets defensáveis do cv_content.json; não deixar isso implícito.",
            "Se uma keyword top 8 não puder ser sustentada por fato real, registrar coverage_mode=declared_gap em ats_keyword_coverage em vez de forçar wording artificial.",
            "Evite usar o resumo como muleta para cobrir ATS; a cobertura principal deve estar distribuída nas experiências.",
            "Antes de encerrar, confira que todos os arquivos exigidos foram gravados.",
        ],
    }


def _write_request(paths: dict[str, Path], stage: str, payload: dict[str, Any]) -> None:
    if stage == "analyze":
        json_path = paths["analysis_request_json"]
        md_path = paths["analysis_request_md"]
        output_ref = str(paths["fit_map_draft"].relative_to(ROOT))
    else:
        json_path = paths["generation_request_json"]
        md_path = paths["generation_request_md"]
        output_ref = json.dumps(payload.get("required_output", {}), ensure_ascii=False, indent=2)
    write_json(json_path, payload)
    write_text(
        md_path,
        "\n".join(
            [
                f"# Application V2 Stage: {stage}",
                "",
                f"- Leia `{json_path.relative_to(ROOT)}`.",
                "- Atualize apenas os arquivos permitidos desta etapa.",
                "- Não execute o pipeline inteiro.",
                "",
                "## Objetivo",
                payload["goal"],
                "",
                "## Saída esperada",
                output_ref,
            ]
        )
        + "\n",
    )
    _append_event(
        paths,
        f"{stage}_request_written",
        request_json=str(json_path.relative_to(ROOT)),
        request_md=str(md_path.relative_to(ROOT)),
    )


def _write_context(application: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> None:
    output_docx = state.get("output_docx") or str(_expected_cv_docx_path(paths).relative_to(ROOT))
    write_text(
        paths["conversation_context"],
        "\n".join(
            [
                f"# {application.get('title') or application.get('role') or 'Candidatura'}",
                "",
                f"- ID: {_record_key(application)}",
                f"- Etapa: {state.get('stage')}",
                f"- Status serviço: {state.get('service_status') or state.get('stage')}",
                f"- Score: {state.get('score') if state.get('score') is not None else 'pendente'}",
                f"- Draft: {paths['fit_map_draft'].relative_to(ROOT)}",
                f"- FIT_MAP: {paths['fit_map'].relative_to(ROOT)}",
                f"- CV content: {paths['cv_content'].relative_to(ROOT)}",
                f"- Output DOCX esperado: {output_docx}",
                f"- Job description: {paths['job_description'].relative_to(ROOT)}",
            ]
        )
        + "\n",
    )
    _append_event(paths, "context_written", stage=state.get("stage"), score=state.get("score"))


def _run_agent(stage: str, application: dict[str, Any], paths: dict[str, Path], config: dict[str, Any], options: HeartbeatV2Options) -> None:
    runner_key = "analysis_runner" if stage == "analyze" else "generation_runner"
    runner = config[runner_key]
    command_name = str(runner.get("command") or "opencode")
    resolved = shutil.which(command_name) or shutil.which("opencode.cmd") or command_name
    if stage == "analyze":
        request_md = paths["analysis_request_md"]
    elif stage == "repair":
        request_md = paths["repair_request_md"]
    else:
        request_md = paths["generation_request_md"]
    model = options.model or str(config.get("active_model") or "").strip()
    variant = options.variant or str(config.get("active_variant") or "").strip()
    if stage == "analyze":
        instruction = "Leia o request anexado e grave apenas o fit_map.draft.json."
    elif stage == "repair":
        instruction = "Leia o request anexado e repare somente os artefatos textuais permitidos."
    else:
        instruction = "Leia o request anexado e grave somente os artefatos textuais pedidos."

    if Path(resolved).name == "hermes" or command_name == "hermes":
        request_rel = request_md.relative_to(ROOT)
        prompt = f"Leia o arquivo {request_rel}. {instruction}"
        command = [resolved, "--accept-hooks"]
        if model:
            command.extend(["--model", model])
        command.extend(["-z", prompt])
    else:
        command = [
            resolved,
            "run",
            "--agent",
            str(runner.get("agent") or "build"),
            "--file",
            str(request_md),
            "--title",
            f"{stage.title()} candidatura v2 {_record_key(application)}",
        ]
        if model:
            command.extend(["--model", model])
        if variant:
            command.extend(["--variant", variant])
        command.append(instruction)
    _emit("command: " + " ".join(f'"{part}"' if " " in part else part for part in command))
    _append_event(paths, "agent_started", stage=stage, command=command)
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=int(runner.get("timeout_minutes") or 90) * 60,
    )
    payload = {
        "stage": stage,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "finished_at": utc_now_iso(),
    }
    write_json(paths["agent_run"], payload)
    write_json(paths[f"agent_run_{stage}"], payload)
    _append_event(
        paths,
        "agent_finished",
        stage=stage,
        returncode=result.returncode,
        stdout_preview=result.stdout[:4000],
        stderr_preview=result.stderr[:2000],
    )
    if result.stdout.strip():
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    elif result.stderr.strip():
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        raise SystemExit(f"OpenCode {stage} failed for application {_record_key(application)}")


def _normalize_fit_map_draft_file(path: Path) -> None:
    payload = read_json(path)
    if not isinstance(payload, dict):
        return
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    nested = payload.get("fit_map_draft")
    if isinstance(nested, dict):
        if "metadata" in nested:
            metadata = nested.pop("metadata")
            if isinstance(metadata, dict):
                nested.setdefault("cargo", metadata.get("cargo") or metadata.get("titulo"))
                nested.setdefault("empresa", metadata.get("empresa"))
        payload = nested
        meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else meta
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else metadata
    payload.setdefault("cargo", meta.get("vaga") or meta.get("role") or metadata.get("role") or metadata.get("title"))
    payload.setdefault("empresa", meta.get("empresa") or meta.get("company") or metadata.get("company") or metadata.get("empresa"))
    if str(payload.get("modo") or "").strip().casefold() == "draft":
        payload["modo"] = "Modo 1 - vaga especifica"
    ats_entries = payload.get("keywords_habilidade_ats")
    if isinstance(ats_entries, list):
        for index, item in enumerate(ats_entries, start=1):
            if not isinstance(item, dict):
                continue
            if item.get("experiencia") and not item.get("experiencia_alvo"):
                item["experiencia_alvo"] = item.get("experiencia")
            if item.get("prioridade") is None:
                item["prioridade"] = index
    write_json(path, payload)


def _register_fit_map_keywords(fit_map_path: Path) -> None:
    command = [sys.executable, "scripts/register_keywords.py", "--fit-map", str(fit_map_path)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(
            "FIT_MAP keyword registration failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )


def _postprocess_analyze(paths: dict[str, Path]) -> float:
    if not paths["fit_map_draft"].exists():
        raise SystemExit(f"Stage analyze did not produce {paths['fit_map_draft']}")
    _append_event(paths, "postprocess_started", stage="analyze")
    _normalize_fit_map_draft_file(paths["fit_map_draft"])
    fit_map_service.validate_draft(paths["fit_map_draft"])
    fit_map_service.build_fit_map(paths["fit_map_draft"], paths["fit_map"])
    fit_map_service.score_fit_map(paths["fit_map"])
    fit_map_service.validate_fit_map(paths["fit_map"])
    _persist_job_description_into_fit_map(paths)
    _register_fit_map_keywords(paths["fit_map"])
    score = _fit_score(paths["fit_map"]) or 0.0
    _append_event(paths, "postprocess_finished", stage="analyze", score=score, fit_map=str(paths["fit_map"].relative_to(ROOT)))
    return float(score)


def _run_analyze_with_retry(application: dict[str, Any], paths: dict[str, Path], config: dict[str, Any], options: HeartbeatV2Options, state: dict[str, Any]) -> float:
    _write_request(paths, "analyze", _analysis_request(application, paths))
    _write_context(application, paths, state)
    _run_agent("analyze", application, paths, config, options)
    try:
        return _postprocess_analyze(paths)
    except (SystemExit, ValidationFailure) as exc:
        validation_error = str(exc)
        _append_event(paths, "analyze_retry_requested", message=validation_error)
        state["retry_count_analyze"] = int(state.get("retry_count_analyze") or 0) + 1
        _set_stage(state, "analyze_retry_pending")
        state["last_error"] = validation_error
        _write_state(paths, state)
        _write_request(paths, "analyze", _analysis_retry_request(application, paths, validation_error))
        _write_context(application, paths, state)
        _run_agent("analyze", application, paths, config, options)
        return _postprocess_analyze(paths)


def _render_cv_docx(paths: dict[str, Path]) -> Path:
    artifact = _expected_cv_docx_path(paths)
    command = [
        "node",
        str((ROOT / "scripts" / "docx" / "generate_general_cv_docx.js").resolve()),
        str(paths["cv_content"].resolve()),
        artifact.name,
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(f"DOCX generation failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return artifact


def _validate_cv_content_contract(paths: dict[str, Path]) -> None:
    payload = read_json(paths["cv_content"])
    if not isinstance(payload, dict):
        raise ValidationFailure("cv_content.json must be a JSON object.")
    experiences = payload.get("experiences")
    if not isinstance(experiences, list):
        raise ValidationFailure("cv_content.json must contain an experiences list.")
    if len(experiences) < 4 or len(experiences) > 8:
        raise ValidationFailure(
            f"cv_content.json must contain between 4 and 8 experiences; received {len(experiences)}."
        )
    mode = str(payload.get("mode") or "concise").strip().casefold()
    if mode not in {"concise", "expanded"}:
        raise ValidationFailure("cv_content.json mode must be concise or expanded.")
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
    for index, experience in enumerate(experiences, start=1):
        if not isinstance(experience, dict):
            raise ValidationFailure(f"experiences[{index}] must be an object.")
        role = str(experience.get("role") or "").casefold()
        period = str(experience.get("period") or "").casefold()
        company = str(experience.get("company") or "").casefold()
        haystack = f"{role} {company}"
        if any(marker in haystack for marker in consolidated_markers):
            raise ValidationFailure(
                f"experiences[{index}] appears to consolidate multiple roles; keep each role as a separate experience."
            )
        if "ifood" in company and "2018" in period and "2024" in period:
            raise ValidationFailure(
                f"experiences[{index}] appears to use the aggregated iFood period; split Head and Director roles."
            )
        if "trifil" in company and "2006" in period and "2014" in period:
            raise ValidationFailure(
                f"experiences[{index}] appears to use the aggregated Trifil period; select separate Trifil roles."
            )
        bullets = experience.get("bullets")
        if not isinstance(bullets, list) or not bullets:
            raise ValidationFailure(f"experiences[{index}] must contain at least one bullet.")
        if mode == "concise" and len(bullets) != 3:
            raise ValidationFailure(
                f"experiences[{index}] must contain exactly 3 bullets in concise mode; received {len(bullets)}."
            )
    coverage = payload.get("ats_keyword_coverage")
    if not isinstance(coverage, list):
        raise ValidationFailure("cv_content.json must include ats_keyword_coverage for the top 8 ATS keywords.")
    fit_map = read_json(paths["fit_map"])
    required_keywords = [
        str(item.get("keyword")).strip()
        for item in sorted(
            [entry for entry in fit_map.get("keywords_habilidade_ats", []) if isinstance(entry, dict)],
            key=lambda item: int(item.get("prioridade") or 999),
        )[:8]
        if str(item.get("keyword") or "").strip()
    ]
    coverage_by_keyword: dict[str, dict[str, Any]] = {}
    for item in coverage:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        if keyword and keyword not in coverage_by_keyword:
            coverage_by_keyword[keyword] = item
    missing = [keyword for keyword in required_keywords if keyword not in coverage_by_keyword]
    if missing:
        raise ValidationFailure(
            "cv_content.json is missing ats_keyword_coverage entries for top 8 keywords: " + ", ".join(missing)
        )
    invalid_mappings = []
    for keyword in required_keywords:
        item = coverage_by_keyword[keyword]
        try:
            exp_index = int(item.get("experience_index"))
            bullet_index = int(item.get("bullet_index"))
        except (TypeError, ValueError):
            invalid_mappings.append(f"{keyword} -> invalid experience_index/bullet_index")
            continue
        if exp_index < 0 or exp_index >= len(experiences):
            invalid_mappings.append(f"{keyword} -> experience_index out of range ({exp_index})")
            continue
        bullets = experiences[exp_index].get("bullets") or []
        if bullet_index < 0 or bullet_index >= len(bullets):
            invalid_mappings.append(f"{keyword} -> bullet_index out of range ({bullet_index})")
            continue
        coverage_mode = str(item.get("coverage_mode") or "").strip()
        if coverage_mode not in {"exact", "similar", "declared_gap"}:
            invalid_mappings.append(f"{keyword} -> invalid coverage_mode {coverage_mode!r}")
            continue
        if coverage_mode != "declared_gap" and not str(item.get("defensible_evidence") or "").strip():
            invalid_mappings.append(f"{keyword} -> defensible_evidence missing")
    if invalid_mappings:
        raise ValidationFailure("cv_content.json has invalid ats_keyword_coverage mappings:\n- " + "\n- ".join(invalid_mappings))


def _write_repair_request(paths: dict[str, Path], state: dict[str, Any], review_report: dict, polish_report: dict) -> None:
    top8 = review_report.get("top8_keywords", []) if isinstance(review_report, dict) else []
    missing_top8 = [
        {
            "keyword": item.get("keyword"),
            "experience_target": item.get("experience_target"),
            "coverage_note": item.get("coverage_note"),
        }
        for item in top8
        if item.get("coverage_class") == "missing_unexplained"
    ]
    payload = {
        "stage": "repair",
        "goal": "Corrigir apenas os artefatos textuais bloqueados pelo gate local, sem reiniciar o pipeline inteiro.",
        "inputs": {
            "fit_map_path": str(paths["fit_map"].relative_to(ROOT)),
            "cv_content_path": str(paths["cv_content"].relative_to(ROOT)),
            "review_report_path": str(paths["cv_review_report"].relative_to(ROOT)),
            "polish_report_path": str(paths["polish_review"].relative_to(ROOT)),
        },
        "allowed_outputs": [
            str(paths["cv_content"].relative_to(ROOT)),
            str(paths["feras_formal"].relative_to(ROOT)),
            str(paths["habilidades_gupy"].relative_to(ROOT)),
            str(paths["habilidades_mercado_livre"].relative_to(ROOT)),
        ],
        "blocking_review_ids": [item.get("id") for item in review_report.get("blockers", [])],
        "missing_unexplained_top8": missing_top8,
        "repair_rules": [
            "Resolver primeiro as keywords top 8 ausentes, colocando cada uma em uma experiência defensável do cv_content.json.",
            "Nunca forçar keyword sem evidência factual; quando não houver sustentação real, manter como gap declarado no mapeamento.",
            "Manter entre 4 e 8 experiências no cv_content.json.",
            "Manter modo concise com exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
            "Se a correção parecer pedir modo expandido, bloquear e pedir validação do usuário antes de alterar o modo.",
            "Atualizar ats_keyword_coverage para refletir exatamente onde cada keyword top 8 ficou coberta.",
            "Não renderizar DOCX, não rodar reviewers e não atualizar Notion nesta etapa.",
        ],
        "state_snapshot": {
            "stage": state.get("stage"),
            "service_status": state.get("service_status") or state.get("stage"),
            "score": state.get("score"),
            "last_error": state.get("last_error"),
            "review_status": state.get("review_status"),
            "polish_status": state.get("polish_status"),
            "repair_attempt_count": state.get("repair_attempt_count"),
        },
        "polish_blockers": polish_report.get("approval_blockers", []),
    }
    write_json(paths["repair_request_json"], payload)
    write_text(
        paths["repair_request_md"],
        "\n".join(
            [
                "# Application V2 Stage: repair",
                "",
                f"- Leia `{paths['repair_request_json'].relative_to(ROOT)}`.",
                "- Corrija apenas os artefatos textuais permitidos.",
                "- O foco principal é cobrir as keywords top 8 faltantes em experiências defensáveis.",
                "- Mantenha 4 a 8 experiências no cv_content.json.",
                "- Mantenha modo concise com exatamente 3 bullets por experiência, salvo pedido explícito do usuário por modo expandido/bullet points.",
                "- Se a correção parecer pedir modo expandido, peça validação do usuário antes de alterar o modo.",
            ]
        )
        + "\n",
    )
    _append_event(
        paths,
        "repair_request_written",
        request_json=str(paths["repair_request_json"].relative_to(ROOT)),
        request_md=str(paths["repair_request_md"].relative_to(ROOT)),
        missing_top8=[item.get("keyword") for item in missing_top8],
    )


def _postprocess_generate(paths: dict[str, Path]) -> dict[str, Any]:
    required = [paths["cv_content"], paths["feras_formal"], paths["habilidades_gupy"], paths["habilidades_mercado_livre"]]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Stage generate did not produce required artifacts: " + ", ".join(missing))
    _append_event(paths, "postprocess_started", stage="generate")
    _validate_cv_content_contract(paths)
    habilidades_chave_service.validate_artifact(paths["habilidades_gupy"], mode="gupy", expected_count=10, fit_map_path=paths["fit_map"])
    habilidades_chave_service.validate_artifact(paths["habilidades_mercado_livre"], mode="mercado_livre", expected_count=10, fit_map_path=paths["fit_map"])
    artifact = _render_cv_docx(paths)
    try:
        report = review_service.approve_cv(
            artifact=artifact,
            fit_map_path=paths["fit_map"],
            registry_path=KEYWORD_REGISTRY,
            report_path=paths["cv_review_report"],
            polish_report_path=paths["polish_review"],
        )
        _append_event(
            paths,
            "postprocess_finished",
            stage="generate",
            output_docx=str(artifact.relative_to(ROOT)),
            review_approved=bool(report.get("approved_for_delivery")),
        )
        return {
            "stage": "done",
            "output_docx": str(artifact.relative_to(ROOT)),
            "review_status": "approved",
            "polish_status": "approved",
        }
    except SystemExit as exc:
        review_report = read_json(paths["cv_review_report"]) if paths["cv_review_report"].exists() else {}
        polish_report = read_json(paths["polish_review"]) if paths["polish_review"].exists() else {}
        _append_event(
            paths,
            "postprocess_finished",
            stage="generate",
            output_docx=str(artifact.relative_to(ROOT)),
            review_approved=False,
            review_blockers=[item.get("id") for item in review_report.get("blockers", [])],
            polish_blockers=polish_report.get("approval_blockers", []),
        )
        return {
            "stage": "blocked_review",
            "output_docx": str(artifact.relative_to(ROOT)),
            "review_status": "blocked",
            "polish_status": "blocked" if polish_report.get("approval_blockers") else "pending",
            "message": str(exc),
            "review_report": review_report,
            "polish_report": polish_report,
        }


def _update_notion_status(application: dict[str, Any], status: str, *, dry_run: bool) -> dict | None:
    token, database_id = notion_service.notion_config()
    if application.get("page_id"):
        return notion_service.update_status(token, database_id, str(application["page_id"]), status, dry_run=dry_run)
    return None


def _set_service_status(state: dict[str, Any], value: str | None = None) -> dict[str, Any]:
    state["service_status"] = value or state.get("stage")
    return state


def _fit_map_for_notion(
    paths: dict[str, Path],
    state: dict[str, Any],
    *,
    review_report: dict | None = None,
    polish_report: dict | None = None,
) -> Path:
    fit_map = read_json(paths["fit_map"])
    report = review_report if isinstance(review_report, dict) else (read_json(paths["cv_review_report"]) if paths["cv_review_report"].exists() else {})
    polish = polish_report if isinstance(polish_report, dict) else (read_json(paths["polish_review"]) if paths["polish_review"].exists() else {})
    top8 = report.get("top8_keywords", []) if isinstance(report, dict) else []
    missing_top8 = [str(item.get("keyword")) for item in top8 if item.get("coverage_class") == "missing_unexplained"]
    fit_map["service_status"] = state.get("service_status") or state.get("stage")
    fit_map["service_stage"] = state.get("stage")
    fit_map["service_stage_status"] = state.get("stage_status")
    fit_map["service_next_action"] = state.get("next_action")
    fit_map["service_review_blockers"] = [item.get("id") for item in report.get("blockers", [])] if isinstance(report, dict) else []
    fit_map["service_missing_top8"] = missing_top8
    fit_map["service_repair_attempt_count"] = int(state.get("repair_attempt_count") or 0)
    fit_map["service_polish_blockers"] = polish.get("approval_blockers", []) if isinstance(polish, dict) else []
    fit_map["service_summary"] = (
        f"status_servico={fit_map['service_status']} | "
        f"score={state.get('score')} | "
        f"blockers={', '.join(fit_map['service_review_blockers']) if fit_map['service_review_blockers'] else 'none'} | "
        f"missing_top8={', '.join(missing_top8) if missing_top8 else 'none'}"
    )
    write_json(paths["fit_map_notion_payload"], fit_map)
    return paths["fit_map_notion_payload"]


def _update_notion_from_fit_map(application: dict[str, Any], paths: dict[str, Path], status: str, *, dry_run: bool) -> dict | None:
    token, database_id = notion_service.notion_config()
    record_id = application.get("record_id")
    if record_id is None:
        return None
    fit_map = read_json(paths["fit_map"])
    saved_job_description = _sync_saved_job_description(
        paths,
        company=str(fit_map.get("empresa") or application.get("company") or "empresa"),
        role=str(fit_map.get("cargo") or application.get("role") or application.get("title") or "cargo"),
    )
    if saved_job_description is None:
        saved_job_description = _load_saved_job_description_path(paths)
    return notion_service.update_from_fit_map_record(
        token,
        database_id,
        int(record_id),
        paths["fit_map_notion_payload"] if paths["fit_map_notion_payload"].exists() else paths["fit_map"],
        saved_job_description,
        status=status,
        dry_run=dry_run,
    )


def _publish_notion_service_state(
    application: dict[str, Any],
    paths: dict[str, Path],
    state: dict[str, Any],
    *,
    status: str,
    review_report: dict | None = None,
    polish_report: dict | None = None,
) -> dict | None:
    _fit_map_for_notion(paths, state, review_report=review_report, polish_report=polish_report)
    payload = _update_notion_from_fit_map(application, paths, status, dry_run=False)
    if payload is not None:
        write_json(paths["notion_update_payload"], payload)
    state["notion_status"] = status
    _append_event(paths, "notion_status_updated", status=status, service_status=state.get("service_status"))
    return payload


def _write_index(entries: list[dict[str, Any]]) -> None:
    existing = read_json(V2_INDEX) if V2_INDEX.exists() else {"version": 1, "applications": []}
    by_key = {str(item.get("record_key")): item for item in existing.get("applications", [])}
    for entry in entries:
        by_key[str(entry["record_key"])] = entry
    write_json(
        V2_INDEX,
        {
            "version": 1,
            "updated_at": utc_now_iso(),
            "applications": sorted(by_key.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True),
        },
    )


def _result_payload(application: dict[str, Any], paths: dict[str, Path], state: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_key": _record_key(application),
        "record_id": application.get("record_id"),
        "title": application.get("title"),
        "company": application.get("company"),
        "role": application.get("role"),
        "status": state["stage"],
        "service_status": state.get("service_status") or state.get("stage"),
        "stage_group": state.get("stage_group"),
        "stage_status": state.get("stage_status"),
        "retryable": state.get("retryable"),
        "score": state.get("score"),
        "application_dir": str(paths["manifest"].parent.relative_to(ROOT)),
        "conversation_context": str(paths["conversation_context"].relative_to(ROOT)),
        "output_docx": state.get("output_docx"),
        "updated_at": utc_now_iso(),
    }


def _run_repair_cycle(
    application: dict[str, Any],
    paths: dict[str, Path],
    config: dict[str, Any],
    options: HeartbeatV2Options,
    state: dict[str, Any],
    initial_result: dict[str, Any],
) -> dict[str, Any]:
    max_attempts = int(config.get("repair_max_attempts") or 0)
    latest_result = initial_result
    review_report = latest_result.get("review_report", {}) if isinstance(latest_result.get("review_report"), dict) else {}
    polish_report = latest_result.get("polish_report", {}) if isinstance(latest_result.get("polish_report"), dict) else {}

    while state.get("stage") == "blocked_review" and int(state.get("repair_attempt_count") or 0) < max_attempts:
        state["repair_attempt_count"] = int(state.get("repair_attempt_count") or 0) + 1
        _write_repair_request(paths, state, review_report, polish_report)
        _set_stage(state, "repair_pending")
        _set_service_status(state, "repair_pending")
        _write_state(paths, state)
        _write_context(application, paths, state)
        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )

        _set_stage(state, "repair_running")
        _set_service_status(state, "repair_running")
        _write_state(paths, state)
        _write_context(application, paths, state)
        _run_agent("repair", application, paths, config, options)

        latest_result = _postprocess_generate(paths)
        _set_stage(state, str(latest_result["stage"]))
        _set_service_status(state, str(latest_result["stage"]))
        state["output_docx"] = latest_result.get("output_docx")
        state["review_status"] = latest_result.get("review_status", state.get("review_status"))
        state["polish_status"] = latest_result.get("polish_status", state.get("polish_status"))
        state["last_error"] = latest_result.get("message") if state["stage"] != "done" else None
        review_report = latest_result.get("review_report", {}) if isinstance(latest_result.get("review_report"), dict) else {}
        polish_report = latest_result.get("polish_report", {}) if isinstance(latest_result.get("polish_report"), dict) else {}

        if state["stage"] == "done":
            _publish_notion_service_state(
                application,
                paths,
                state,
                status=str(config["success_status"]),
                review_report=review_report,
                polish_report=polish_report,
            )
            return latest_result

        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )

    if state.get("stage") == "blocked_review":
        _set_stage(state, "blocked_review_exhausted")
        _set_service_status(state, "blocked_review_exhausted")
        _publish_notion_service_state(
            application,
            paths,
            state,
            status=str(config["blocked_review_status"]),
            review_report=review_report,
            polish_report=polish_report,
        )
    return latest_result


def run_heartbeat(options: HeartbeatV2Options) -> dict[str, Any]:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    V2_LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = utc_now_iso()
    config = _load_config()
    token, database_id = notion_service.notion_config()
    applications = _load_queue(token, database_id)
    effective_max = options.max_per_run if options.max_per_run is not None else int(config["max_per_run"])
    selected = _eligible(applications, config, effective_max)
    _emit(f"selected {len(selected)} application(s) directly from Notion")
    if selected:
        ordered = ", ".join(f"{_record_key(item)}:{item.get('status')}" for item in selected)
        _emit(f"selection order -> {ordered}")
    results: list[dict[str, Any]] = []
    for index, application in enumerate(selected, start=1):
        record_key = _record_key(application)
        _emit(f"queue item {index}/{len(selected)} -> {record_key}: {application.get('title') or application.get('role')}")
        app_dir, paths = _write_package(application, reset=_is_reprocess_requested(application, config))
        if _is_reprocess_requested(application, config):
            _append_event(paths, "package_reset_for_reprocess", record_id=application.get("record_id"))
        _append_event(
            paths,
            "package_prepared",
            record_id=application.get("record_id"),
            title=application.get("title"),
            status=application.get("status"),
            description_chars=application.get("description_chars"),
        )
        state = _read_state(paths, record_key, application)
        stage, score = _derive_stage(paths, config)
        _set_stage(state, stage)
        _set_service_status(state)
        state["score"] = score
        state["status"] = application.get("status")
        state["notion_status"] = application.get("status")
        _write_state(paths, state)
        if stage == "analyze_pending":
            _write_request(paths, "analyze", _analysis_request(application, paths))
        elif stage == "generate_pending":
            _write_request(paths, "generate", _generation_request(application, paths))
        _write_context(application, paths, state)
        try:
            if stage == "no_description":
                if not options.dry_run:
                    _update_notion_status(application, str(config["no_description_status"]), dry_run=False)
                    _append_event(paths, "notion_status_updated", status=str(config["no_description_status"]))
                state["notion_status"] = str(config["no_description_status"])
                _write_state(paths, state)
            elif options.run_agent and not options.dry_run:
                _update_notion_status(application, str(config["running_status"]), dry_run=False)
                state["notion_status"] = str(config["running_status"])
                _append_event(paths, "notion_status_updated", status=str(config["running_status"]))
                if stage == "analyze_pending":
                    _set_stage(state, "analyze_running")
                    _set_service_status(state)
                    _write_state(paths, state)
                    _write_context(application, paths, state)
                    score = _run_analyze_with_retry(application, paths, config, options, state)
                    state["score"] = score
                    state["last_error"] = None
                    if score < float(config["score_threshold"]):
                        _set_stage(state, "low_fit")
                        _set_service_status(state)
                        _publish_notion_service_state(application, paths, state, status=str(config["low_fit_status"]))
                    else:
                        _set_stage(state, "generate_pending")
                        _set_service_status(state)
                if state["stage"] == "generate_pending":
                    _set_stage(state, "generate_running")
                    _set_service_status(state)
                    _write_state(paths, state)
                    _write_request(paths, "generate", _generation_request(application, paths))
                    _write_context(application, paths, state)
                    _run_agent("generate", application, paths, config, options)
                    generate_result = _postprocess_generate(paths)
                    _set_stage(state, str(generate_result["stage"]))
                    _set_service_status(state)
                    state["output_docx"] = generate_result.get("output_docx")
                    state["review_status"] = generate_result.get("review_status", state.get("review_status"))
                    state["polish_status"] = generate_result.get("polish_status", state.get("polish_status"))
                    state["last_error"] = generate_result.get("message") if state["stage"] == "blocked_review" else None
                    if state["stage"] == "done":
                        _publish_notion_service_state(application, paths, state, status=str(config["success_status"]))
                    elif state["stage"] == "blocked_review":
                        _write_repair_request(
                            paths,
                            state,
                            generate_result.get("review_report", {}) if isinstance(generate_result.get("review_report"), dict) else {},
                            generate_result.get("polish_report", {}) if isinstance(generate_result.get("polish_report"), dict) else {},
                        )
                        _publish_notion_service_state(
                            application,
                            paths,
                            state,
                            status=str(config["blocked_review_status"]),
                            review_report=generate_result.get("review_report", {}) if isinstance(generate_result.get("review_report"), dict) else {},
                            polish_report=generate_result.get("polish_report", {}) if isinstance(generate_result.get("polish_report"), dict) else {},
                        )
                        generate_result = _run_repair_cycle(application, paths, config, options, state, generate_result)
                        if state["stage"] == "done":
                            _set_service_status(state, "done")
                        elif state["stage"] == "blocked_review_exhausted":
                            state["last_error"] = state.get("last_error") or generate_result.get("message")
                _write_state(paths, state)
                _write_context(application, paths, state)
            result = _result_payload(application, paths, state)
            write_json(paths["run_result"], result)
            _append_event(paths, "run_result_written", result=result)
            results.append(result)
            _write_index([result])
            _emit(
                f"result {record_key} -> status={result['status']}; "
                f"score={result['score']}; output={result.get('output_docx') or '-'}"
            )
            _emit(f"completed queue item {index}/{len(selected)}")
        except BaseException as exc:
            _set_stage(state, "error")
            state["last_error"] = str(exc)
            if not options.dry_run and application.get("page_id"):
                try:
                    _update_notion_status(application, str(config["error_status"]), dry_run=False)
                    state["notion_status"] = str(config["error_status"])
                    _append_event(paths, "notion_status_updated", status=str(config["error_status"]))
                except BaseException as notion_exc:
                    _append_event(paths, "notion_status_update_failed", status=str(config["error_status"]), message=str(notion_exc))
            _write_state(paths, state)
            error = {
                "record_key": record_key,
                "record_id": application.get("record_id"),
                "status": "error",
                "message": str(exc),
                "application_dir": str(app_dir.relative_to(ROOT)),
                "updated_at": utc_now_iso(),
            }
            write_json(paths["error_report"], error)
            _append_event(paths, "error", message=str(exc))
            results.append(error)
            _write_index([error])
            _emit(f"result {record_key} -> status=error; message={str(exc)}")
    summary = {
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "dry_run": options.dry_run,
        "run_agent": options.run_agent,
        "max_per_run": effective_max,
        "selected": len(selected),
        "results": results,
        "index": str(V2_INDEX.relative_to(ROOT)),
    }
    log_path = V2_LOG_DIR / (started_at.replace(":", "").replace("+", "Z") + ".json")
    write_json(log_path, summary)
    summary["log"] = str(log_path.relative_to(ROOT))
    return summary
