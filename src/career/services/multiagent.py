from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from career.paths import CAREER_STATE, OUTPUTS, ROOT
from career.services import derived_context as derived_context_service
from career.utils import ValidationFailure, read_json, utc_now_iso, write_json, write_text
from career.workflow.state_store import WorkflowStateStore


REQUEST_DIR = CAREER_STATE / "agent_requests"
RUNBOOK_PATH = REQUEST_DIR / "multiagent_runbook.json"
LOCAL_MODEL_MAP_PATH = REQUEST_DIR / "local_model_map.json"
WORKSPACE_FORBIDDEN_PATTERNS = [
    "gen_*.py",
    "generate_*fitmap*.py",
    "create_drafi.py",
    "create_draft.py",
    "tmp_*.py",
]


@dataclass(frozen=True)
class AgentContract:
    step: str
    agent: str
    purpose: str
    allowed_files: tuple[str, ...]
    allowed_commands: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    validation_commands: tuple[str, ...]


BASE_FORBIDDEN_ACTIONS = (
    "criar scripts temporarios na raiz",
    "ler .env ou copiar tokens",
    "usar curl/API direta para Notion",
    "usar browser/web_search para LinkedIn",
    "imprimir arquivos JSON/Markdown grandes na conversa",
    "usar cat em FIT_MAP, caches do Notion, registry ATS ou referencias longas",
    "usar grep -r/rg amplo em inbox/notion, outputs, .career-state ou .opencode sem limite estrito",
    "colar diff gigante de artefato intermediario no chat",
    "entregar conclusao sem artefato persistido",
    "reaproveitar FIT_MAP antigo para vaga nova",
)


LOCAL_MODEL_TRIGGER_MAP = [
    {
        "trigger": "Avalie vaga Notion <id>",
        "canonical_entry_command": "npm run agent:evaluate-notion-local -- <id>",
        "fallback_entry_command": "npm run agent:evaluate-notion -- <id>",
        "then": [
            "read .career-state/agent_requests/fit-map_request.md",
            "read active_intake.job_description_path from the request, but summarize it briefly in chat",
            "if fit-map:status reports draft.valid_json=false, run npm run fit-map:template and regenerate the request",
            "edit .career-state/fit_map.draft.json as one complete valid JSON object",
            "npm run validate:fit-map:draft",
            "after finalize, run npm run fit-map:summary and npm run validate:fit-map:quality",
            "if validation fails, fix the draft and rerun validation before responding",
        ],
        "forbidden": [
            "start with notion:list, grep, .env, curl, browser, web_search, or direct Notion API",
            "reuse .career-state/fit_map.json when request says Current FIT_MAP.matches_active_job=false",
            "invent evidence, company, numbers, percentages, sources, deadlines, or tools",
            "use partial JSON patches that can corrupt .career-state/fit_map.draft.json",
            "ask the user to fill the draft or run the next command",
            "respond before npm run validate:fit-map:draft has run after editing",
            "print full FIT_MAP/draft JSON or large diffs in the conversation",
        ],
    },
    {
        "trigger": "Continue / retomar FIT_MAP travado",
        "canonical_entry_command": "npm run fit-map:status",
        "then": [
            "if draft.valid_json=false, run npm run fit-map:template",
            "npm run multiagent:request -- fit-map",
            "read .career-state/agent_requests/fit-map_request.md",
            "follow exactly the Operational Rules",
        ],
        "forbidden": [
            "explain the whole workflow again",
            "deliver textual analysis while draft has placeholders",
            "delegate draft filling to the user",
        ],
    },
    {
        "trigger": "Gerar CV / currículo para vaga ativa",
        "canonical_entry_command": "npm run multiagent:request -- cv",
        "then": [
            "read .career-state/agent_requests/cv_request.md",
            "generate DOCX in outputs/",
            "npm run validate:docx",
            "npm run cv:deliver -- --artifact outputs/<cv>.docx",
        ],
        "forbidden": [
            "deliver CV as chat text only",
            "skip cv:deliver when OneDrive/rclone delivery is configured",
            "clean outputs/_tmp before approval gates finish",
        ],
    },
]


CONTRACTS: dict[str, AgentContract] = {
    "fit-map": AgentContract(
        step="fit-map",
        agent="fit-map-agent",
        purpose=(
            "Preencher somente .career-state/fit_map.draft.json para a vaga ativa, "
            "editando o arquivo no filesystem. Nao pedir que o usuario preencha "
            "o draft e nao imprimir o template bruto como resposta."
        ),
        allowed_files=(
            ".career-state/workflow_state.json",
            ".career-state/fit_map.draft.json",
            ".career-state/derived/job_extract.json",
            ".career-state/derived/job_sections.json",
            ".career-state/derived/job_keywords.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/candidate_evidence_pack.json",
            ".career-state/derived/fit_map_seed.json",
            ".career-state/derived/manifest.json",
            ".career-state/memory/profile_facts.json",
            ".career-state/memory/application_rules.json",
            ".career-state/memory/evidence_index.json",
        ),
        allowed_commands=(
            "npm run agent:guard",
            "npm run fit-map:status",
            "npm run fit-map:guard",
            "npm run fit-map:template",
            "npm run fit-map:draft-summary",
            "npm run fit-map:summary",
            "npm run fit-map:check:extract",
            "npm run fit-map:check:map-evidence",
            "npm run fit-map:check:score-draft",
            "npm run fit-map:check:complete-draft",
            "npm run validate:fit-map:draft",
            "npm run validate:fit-map:quality",
        ),
        expected_outputs=(".career-state/fit_map.draft.json",),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "rodar fit-map:finalize",
            "editar .career-state/fit_map.json",
            "escrever nota final na conversa antes do gate",
            "pedir que o usuario preencha o draft",
            "imprimir o template bruto do draft como substituto da edicao",
            "sugerir nano/editor ao usuario para substituir placeholders",
        ),
        validation_commands=(
            "npm run validate:fit-map:draft",
            "npm run fit-map:guard",
        ),
    ),
    "cv": AgentContract(
        step="cv",
        agent="cv-agent",
        purpose=(
            "Gerar cv_content persistido e DOCX de CV a partir do FIT_MAP ativo, mantendo idioma, "
            "keywords e restricoes do perfil. A entrega so pode ser considerada pronta "
            "apos validacao DOCX e cv:deliver no artefato final quando OneDrive/rclone estiver configurado."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/derived/cv_input_pack.json",
            ".career-state/derived/cv_content_seed.json",
            ".career-state/cv_content.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/manifest.json",
            ".career-state/memory/profile_facts.json",
            ".career-state/memory/application_rules.json",
            ".opencode/skills/cv-generator/SKILL.md",
            "scripts/docx/generate_custom_cv.js",
        ),
        allowed_commands=(
            "npm run context:assert-active",
            "npm run cv:build-content",
            "npm run cv:validate-content",
            "npm run cv:docx",
            "npm run validate:docx",
            "npm run cv:approve -- --artifact outputs/<cv>.docx",
            "npm run cv:deliver -- --artifact outputs/<cv>.docx",
        ),
        expected_outputs=(
            "outputs/<cv>.docx",
            "outputs/_tmp/output_review_report.json",
            "outputs/_tmp/polish_review.json",
        ),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "entregar CV sem npm run cv:deliver quando OneDrive/rclone estiver configurado",
            "limpar outputs/_tmp antes da aprovacao",
            "alterar numeros criticos",
            "entregar CV sem DOCX final em outputs/",
            "considerar warnings como blockers sem o gate indicar blocker",
            "ignorar idioma requerido pela descricao da vaga",
        ),
        validation_commands=(
            "npm run cv:validate-content",
            "npm run validate:docx",
            "npm run cv:deliver -- --artifact outputs/<cv>.docx",
        ),
    ),
    "cover-letter": AgentContract(
        step="cover-letter",
        agent="cover-letter-agent",
        purpose=(
            "Gerar carta de apresentacao a partir de pack compacto persistido, sem reler "
            "referencias longas no caminho feliz. O artefato deve nascer em arquivo local antes de qualquer entrega."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/derived/cover_letter_input_pack.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/cover-letter/SKILL.md",
        ),
        allowed_commands=(
            "npm run cover-letter:build",
            "python3 scripts/cover_letter_to_pdf.py --input <arquivo.md> --output <arquivo.pdf>",
            "npm run deliver:artifact -- --file outputs/<arquivo.pdf>",
        ),
        expected_outputs=(
            "outputs/<cover_letter>.md",
            "outputs/<cover_letter>.pdf",
        ),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "entregar carta apenas na conversa",
            "reabrir referencias longas sem necessidade objetiva",
            "usar tom genérico ou claims nao defensaveis",
            "prosseguir para entrega sem arquivo local persistido",
        ),
        validation_commands=("npm run cover-letter:build",),
    ),
    "feras": AgentContract(
        step="feras",
        agent="feras-agent",
        purpose=(
            "Gerar FERAS estruturado e pitch fluido a partir de pack compacto persistido, "
            "mantendo consistencia com FIT_MAP e sem recarregar referencias longas no caminho feliz."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/derived/feras_input_pack.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/feras-pitch/SKILL.md",
        ),
        allowed_commands=("npm run feras:build",),
        expected_outputs=("outputs/<feras>.md",),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "entregar feras apenas na conversa sem artefato local",
            "usar tom de coach ou claims nao defensaveis",
            "reabrir referencias longas sem necessidade objetiva",
        ),
        validation_commands=("npm run feras:build",),
    ),
    "habilidades": AgentContract(
        step="habilidades",
        agent="habilidades-agent",
        purpose=(
            "Gerar habilidades Gupy e Mercado Livre a partir do pack compacto da vaga ativa, "
            "respeitando os catalogos permitidos e persistindo os dois artefatos."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/derived/habilidades_input_pack.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/habilidades-chave/SKILL.md",
        ),
        allowed_commands=(
            "npm run habilidades:check",
            "npm run habilidades:validate:gupy -- outputs/<habilidades_gupy>.md",
            "npm run habilidades:validate:mercado-livre -- outputs/<habilidades_mercado_livre>.md",
        ),
        expected_outputs=(
            "outputs/<habilidades_gupy>.md",
            "outputs/<habilidades_mercado_livre>.md",
        ),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "misturar catalogos Gupy e Mercado Livre",
            "inventar habilidade fora do catalogo ativo",
            "entregar listas apenas na conversa",
        ),
        validation_commands=(
            "npm run habilidades:validate:gupy -- outputs/<habilidades_gupy>.md",
            "npm run habilidades:validate:mercado-livre -- outputs/<habilidades_mercado_livre>.md",
        ),
    ),
    "notion-update": AgentContract(
        step="notion-update",
        agent="notion-agent",
        purpose=(
            "Preparar dry-run de criacao/atualizacao Notion usando apenas scripts locais. "
            "Escrita real depende da policy do harness: Gmail sempre manual; "
            "Notion pode autoexecutar quando o pedido explicito do usuario ja autoriza a escrita."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/derived/active_context.json",
            ".career-state/derived/job_extract.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/notion-transactions/SKILL.md",
        ),
        allowed_commands=(
            "npm run notion:update-record-current -- <id_unico> --dry-run",
            "npm run notion:link-record -- <id_unico>",
            "npm run notion:record-summary -- <id_unico>",
            "npm run notion:create-current -- --dry-run",
            "python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url \"<url>\" --dry-run",
            "python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company \"<empresa>\" --role \"<cargo>\" --source-url \"<url>\" --dry-run",
        ),
        expected_outputs=("dry-run validado; escrita real conforme policy do harness",),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "executar escrita real sem pedido explicito do usuario ou fora da policy do harness",
            "usar MCP de Notion",
            "usar --allow-mismatch",
            "consultar .env ou copiar NOTION_TOKEN",
            "criar duplicata quando a vaga nasceu no Notion",
            "aceitar texto com mojibake como pronto",
        ),
        validation_commands=("npm run agent:guard",),
    ),
    "email-draft": AgentContract(
        step="email-draft",
        agent="email-agent",
        purpose=(
            "Preparar preview revisado de email e criar draft Gmail somente apos aprovacao "
            "explicita do usuario. Nunca enviar email automaticamente."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".opencode/skills/self-email-draft/SKILL.md",
            "outputs/<anexo>",
        ),
        allowed_commands=(
            "python3 scripts/review_email_text.py --subject \"<assunto>\" --body \"<corpo>\"",
            "python3 scripts/create_gmail_draft.py --to \"<email>\" --subject \"<assunto>\" --body \"<corpo>\" --dry-run",
            "python3 scripts/create_gmail_draft.py --to \"<email>\" --subject \"<assunto>\" --body \"<corpo>\" --attach \"<arquivo>\"",
        ),
        expected_outputs=("preview revisado", "draft Gmail apenas apos aprovacao"),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "enviar email automaticamente",
            "perguntar email remetente",
            "criar draft real sem aprovacao explicita",
            "pular review_email_text.py antes do preview",
            "anexar arquivo inexistente",
            "vazar termos internos do pipeline no corpo do email",
        ),
        validation_commands=("python3 scripts/review_email_text.py --subject \"<assunto>\" --body \"<corpo>\"",),
    ),
    "linkedin": AgentContract(
        step="linkedin",
        agent="linkedin-agent",
        purpose=(
            "Extrair e persistir descricao de vaga/post LinkedIn via scripts locais autenticados. "
            "Nunca analisar URL diretamente sem salvar a descricao e registrar active_intake."
        ),
        allowed_files=(
            ".career-state/linkedin_job_extract.json",
            ".career-state/linkedin_post_extract.json",
            "inbox/job_descriptions/<descricao>.md",
            "inbox/linkedin_posts/<post>.md",
            ".opencode/skills/linkedin-job-extractor/SKILL.md",
            "LINKEDIN_AUTH_RUNBOOK.md",
        ),
        allowed_commands=(
            "npm run intake:linkedin-job -- --url \"<url>\"",
            "npm run intake:linkedin-post -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
            "npm run linkedin:extract:authenticated -- --url \"<url>\"",
            "npm run linkedin:post:extract:authenticated -- --url \"<url>\" --company \"<empresa>\" --role \"<cargo>\"",
            "npm run linkedin:auth",
        ),
        expected_outputs=("inbox/job_descriptions/<descricao>.md", ".career-state/workflow_state.json"),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "usar web_search/browser generico",
            "automatizar login/senha",
            "analisar URL sem salvar descricao",
            "usar navegador generico para contornar sessao expirada",
            "prosseguir para FIT_MAP sem active_intake",
            "inventar descricao quando a extracao falhar",
        ),
        validation_commands=("npm run agent:guard",),
    ),
}


def _relative_existing(paths: tuple[str, ...]) -> list[str]:
    existing: list[str] = []
    for item in paths:
        if "<" in item:
            existing.append(item)
            continue
        path = ROOT / item
        existing.append(item if path.exists() else f"{item} (missing_ok)")
    return existing


def _active_intake() -> dict[str, Any] | None:
    payload = WorkflowStateStore().load()
    active = payload.get("active_intake")
    return active if isinstance(active, dict) else None


def _fit_map_summary(active: dict[str, Any] | None = None) -> dict[str, Any]:
    fit_map_path = CAREER_STATE / "fit_map.json"
    if not fit_map_path.exists():
        return {"exists": False}
    payload = read_json(fit_map_path)
    active_fingerprint = active.get("fingerprint") if isinstance(active, dict) else None
    state = WorkflowStateStore().load()
    task_fingerprints = state.get("fingerprints") if isinstance(state.get("fingerprints"), dict) else {}
    fit_map_task = None
    for task_name in ("fit_map.validate", "fit_map.score", "fit_map.build"):
        task_payload = task_fingerprints.get(task_name)
        if isinstance(task_payload, dict):
            fit_map_task = task_payload
            break
    fit_map_fingerprint = fit_map_task.get("active_job_fingerprint") if isinstance(fit_map_task, dict) else None
    matches_active_job = bool(active_fingerprint and fit_map_fingerprint == active_fingerprint)
    return {
        "exists": True,
        "cargo": payload.get("cargo"),
        "empresa": payload.get("empresa"),
        "nota_final": (payload.get("nota_aderencia") or {}).get("final")
        if isinstance(payload.get("nota_aderencia"), dict)
        else None,
        "active_job_fingerprint": active_fingerprint,
        "fit_map_job_fingerprint": fit_map_fingerprint,
        "matches_active_job": matches_active_job,
    }


def write_request(step: str, *, objective: str | None = None, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = CONTRACTS.get(step)
    if not contract:
        raise ValidationFailure(f"Unknown multiagent step: {step}")
    active = _active_intake()
    _prepare_compact_inputs_for_step(step, active)
    request_id = uuid.uuid4().hex
    request_extras = dict(extras or {})
    if step in {"notion-update", "email-draft"}:
        request_extras["pending_action_path"] = f".career-state/pending_actions/{request_id}.json"
    payload = {
        "request_id": request_id,
        "created_at": utc_now_iso(),
        "step": contract.step,
        "agent": contract.agent,
        "objective": objective or contract.purpose,
        "active_intake": active,
        "fit_map": _fit_map_summary(active),
        "allowed_files": _allowed_files_for(contract, active),
        "fallback_reference_files": _fallback_reference_files_for(contract),
        "derived_context": _derived_context_payload(contract),
        "allowed_commands": list(contract.allowed_commands),
        "expected_outputs": list(contract.expected_outputs),
        "forbidden_actions": list(contract.forbidden_actions),
        "validation_commands": list(contract.validation_commands),
        "operational_rules": _operational_rules(contract),
        "completion_contract": {
            "status_values": ["completed", "blocked"],
            "must_report": [
                "status",
                "files_written",
                "commands_executed",
                "validation_result",
                "blocker_reason",
            ],
        },
        "extras": request_extras,
    }
    json_path = REQUEST_DIR / f"{step}_request.json"
    md_path = REQUEST_DIR / f"{step}_request.md"
    write_json(json_path, payload)
    markdown = _request_markdown(payload)
    write_text(md_path, markdown)
    run_dir = REQUEST_DIR / "runs" / request_id
    write_json(run_dir / "request.json", payload)
    write_text(run_dir / "request.md", markdown)
    return {
        "status": "ok",
        "step": step,
        "request_id": request_id,
        "request_json": str(json_path.relative_to(ROOT)),
        "request_md": str(md_path.relative_to(ROOT)),
        "versioned_request_json": str((run_dir / "request.json").relative_to(ROOT)),
        "versioned_request_md": str((run_dir / "request.md").relative_to(ROOT)),
    }


def validate_request(step: str) -> dict[str, Any]:
    request_path = REQUEST_DIR / f"{step}_request.json"
    if not request_path.exists():
        return {
            "status": "blocked",
            "reason": "request_missing",
            "request_json": str(request_path.relative_to(ROOT)),
        }
    payload = read_json(request_path)
    allowed_files = payload.get("allowed_files", []) if isinstance(payload.get("allowed_files"), list) else []
    fallback_files = payload.get("fallback_reference_files", []) if isinstance(payload.get("fallback_reference_files"), list) else []
    fit_map = payload.get("fit_map", {}) if isinstance(payload.get("fit_map"), dict) else {}
    oversized: list[str] = []
    forbidden_long_refs: list[str] = []
    missing: list[str] = []
    for item in allowed_files:
        if not isinstance(item, str) or "<" in item or item.endswith("(missing_ok)"):
            continue
        path = ROOT / item
        if not path.exists():
            missing.append(item)
            continue
        if path.stat().st_size > 50_000:
            oversized.append(item)
        if step == "fit-map" and "/references/" in item and "/career-system/" in item:
            forbidden_long_refs.append(item)
    stale_fit_map = step in {"cv", "notion-update"} and (
        not fit_map.get("exists") or not fit_map.get("matches_active_job")
    )
    return {
        "status": "blocked" if missing or oversized or forbidden_long_refs or stale_fit_map else "ok",
        "step": step,
        "request_json": str(request_path.relative_to(ROOT)),
        "allowed_files_count": len(allowed_files),
        "fallback_reference_files_count": len(fallback_files),
        "missing_files": missing,
        "oversized_allowed_files": oversized,
        "forbidden_long_refs_in_allowed_files": forbidden_long_refs,
        "stale_fit_map_for_active_job": stale_fit_map,
    }


def _request_markdown(payload: dict[str, Any]) -> str:
    active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else {}
    fit_map = payload.get("fit_map") if isinstance(payload.get("fit_map"), dict) else {}
    derived = payload.get("derived_context") if isinstance(payload.get("derived_context"), dict) else {}
    extras = payload.get("extras") if isinstance(payload.get("extras"), dict) else {}
    lines = [
        f"# {payload['agent']} — {payload['step']}",
        "",
        f"Created: {payload['created_at']}",
        "",
        "## Objective",
        payload["objective"],
        "",
        "## Active Context",
        f"- source_type: `{active.get('source_type') or 'none'}`",
        f"- source_id: `{active.get('source_id') or 'none'}`",
        f"- company: `{active.get('company') or 'none'}`",
        f"- role: `{active.get('role') or 'none'}`",
        f"- job_description_path: `{active.get('job_description_path') or 'none'}`",
        f"- next_required_step: `{active.get('next_required_step') or 'none'}`",
        "",
        "## Current FIT_MAP",
        f"- exists: `{fit_map.get('exists')}`",
        f"- cargo: `{fit_map.get('cargo') or 'none'}`",
        f"- empresa: `{fit_map.get('empresa') or 'none'}`",
        f"- nota_final: `{fit_map.get('nota_final') if fit_map.get('nota_final') is not None else 'none'}`",
        f"- matches_active_job: `{fit_map.get('matches_active_job')}`",
        f"- warning: `{'do_not_reuse_stale_fit_map' if fit_map.get('exists') and not fit_map.get('matches_active_job') else 'none'}`",
        "",
        "## Derived Context",
        f"- status: `{derived.get('status') or 'none'}`",
        f"- fingerprint: `{derived.get('fingerprint') or 'none'}`",
        f"- missing_outputs: `{', '.join(derived.get('missing_outputs', [])) if derived.get('missing_outputs') else 'none'}`",
        "",
        "## Extras",
        *([f"- `{key}`: `{value}`" for key, value in extras.items()] or ["- `none`"]),
        "",
        "## Allowed Files",
        *[f"- `{item}`" for item in payload["allowed_files"]],
        "",
        "## Fallback Reference Files",
        *[f"- `{item}`" for item in payload.get("fallback_reference_files", [])],
        "",
        "## Allowed Commands",
        *[f"- `{item}`" for item in payload["allowed_commands"]],
        "",
        "## Expected Outputs",
        *[f"- `{item}`" for item in payload["expected_outputs"]],
        "",
        "## Operational Rules",
        *[f"- {item}" for item in payload.get("operational_rules", [])],
        "",
        "## Forbidden Actions",
        *[f"- `{item}`" for item in payload["forbidden_actions"]],
        "",
        "## Completion Contract",
        "Return status, files_written, commands_executed, validation_result, and blocker_reason.",
        "",
    ]
    return "\n".join(lines)


def _allowed_files_for(contract: AgentContract, active: dict[str, Any] | None) -> list[str]:
    files = list(contract.allowed_files)
    if contract.step == "fit-map":
        files = derived_context_service.fit_map_compact_files()
    elif contract.step == "cv":
        files = derived_context_service.cv_compact_files() + [
            ".opencode/skills/cv-generator/SKILL.md",
            "scripts/docx/generate_custom_cv.js",
        ]
    elif contract.step == "cover-letter":
        files = [
            ".career-state/fit_map.json",
            ".career-state/derived/cover_letter_input_pack.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/cover-letter/SKILL.md",
        ]
    elif contract.step == "feras":
        files = [
            ".career-state/fit_map.json",
            ".career-state/derived/feras_input_pack.json",
            ".career-state/derived/reference_digest.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/feras-pitch/SKILL.md",
        ]
    elif contract.step == "habilidades":
        files = [
            ".career-state/fit_map.json",
            ".career-state/derived/habilidades_input_pack.json",
            ".career-state/derived/manifest.json",
            ".opencode/skills/habilidades-chave/SKILL.md",
        ]
    if contract.step in {"fit-map", "notion-update"} and active:
        job_description_path = active.get("job_description_path")
        if isinstance(job_description_path, str) and job_description_path.strip():
            files.insert(2 if contract.step == "fit-map" else 1, job_description_path)
    return _relative_existing(tuple(files))


def _fallback_reference_files_for(contract: AgentContract) -> list[str]:
    if contract.step == "fit-map":
        return _relative_existing(tuple(derived_context_service.fit_map_fallback_reference_files()))
    return []


def _derived_context_payload(contract: AgentContract) -> dict[str, Any] | None:
    if contract.step not in {"fit-map", "cv", "cover-letter", "feras", "habilidades", "notion-update"}:
        return None
    try:
        return derived_context_service.derived_summary()
    except ValidationFailure:
        return {"status": "blocked", "missing_outputs": ["derived_context_unavailable"]}


def _prepare_compact_inputs_for_step(step: str, active: dict[str, Any] | None) -> None:
    if step in {"fit-map", "notion-update", "cover-letter", "feras", "habilidades"} and active:
        derived_context_service.build_all_for_fit_map()
    elif step == "cv":
        derived_context_service.build_all_for_fit_map()


def _operational_rules(contract: AgentContract) -> list[str]:
    rules = [
        "Ler este request antes de qualquer arquivo longo.",
        "Operar somente nos arquivos e comandos permitidos.",
        "Se bloquear, devolver blocker_reason objetivo em vez de improvisar fallback.",
        "Trabalhar por ponteiros: persistir artefatos em arquivo e responder apenas com resumo curto, caminhos e status.",
        "Nunca imprimir FIT_MAP, draft, registry, cache Notion, descrição longa ou diff gigante na conversa.",
        "Ao validar, reportar somente passed/failed, contagens, paths e erros objetivos; não colar payload validado.",
        "Para JSON, preferir projeções pequenas ou leitura segmentada; não usar cat em artefatos grandes.",
    ]
    if contract.step == "fit-map":
        rules.extend(
            [
                "Caminho feliz: ler primeiro os arquivos compactos em .career-state/derived/ e usar active_intake.job_description_path apenas como fallback.",
                "Ler active_intake.job_description_path antes de editar o draft somente se os arquivos derivados nao forem suficientes.",
                "Usar reference_digest, candidate_evidence_pack e fit_map_seed como contexto primario.",
                "Arquivos de referencia longa ficam em Fallback Reference Files; abrir apenas se evidence_pack ou digest nao resolverem uma lacuna objetiva.",
                "Se Current FIT_MAP.matches_active_job for false, tratar .career-state/fit_map.json como antigo e nao reutilizar.",
                "Se fit-map:status indicar draft.valid_json=false, rodar npm run fit-map:template antes de editar.",
                "Se .career-state/fit_map.draft.json tiver placeholders, a proxima acao e editar o arquivo.",
                "Preferir substituir o JSON inteiro por um objeto completo e valido; nao aplicar patches parciais que quebrem a estrutura.",
                "Leitura do draft sem edicao nao conta como progresso.",
                "Usar somente evidencias e numeros encontrados nas referencias permitidas; se nao houver prova, declarar GAP.",
                "Nao inventar empresa_origem, resultado_numero, fonte_base, percentuais, prazos ou experiencias.",
                "Nao usar '---', texto generico ou placeholders fracos para passar pelo gate.",
                "Nao pedir ao usuario para abrir editor, preencher campos ou substituir marcadores.",
                "Nao colar o JSON bruto do template na conversa.",
                "Nao colar o FIT_MAP/draft completo nem diffs longos na conversa; usar o arquivo como fonte de verdade.",
                "Depois de qualquer edicao, rodar npm run validate:fit-map:draft antes de responder.",
                "Se a validacao falhar, corrigir o arquivo e reexecutar; nao entregar proximos passos ao usuario.",
            ]
        )
    elif contract.step == "cv":
        rules.extend(
            [
                "Usar .career-state/derived/cv_input_pack.json como contexto primario; nao reabrir referencias longas no caminho feliz.",
                "Gerar .career-state/cv_content.json antes do DOCX e validar se ele pertence a vaga ativa.",
                "Confirmar que .career-state/fit_map.json existe e pertence a vaga ativa antes de gerar CV.",
                "Rodar npm run context:assert-active antes do DOCX; se acusar stale, regenerar artefatos em vez de reaproveitar estado residual.",
                "Rodar npm run cv:build-content e npm run cv:validate-content antes do DOCX.",
                "Gerar ou atualizar o conteudo/DOCX em outputs/; nao entregar apenas texto na conversa.",
                "Rodar npm run validate:docx no DOCX gerado.",
                "Rodar npm run cv:deliver -- --artifact outputs/<cv>.docx no artefato final quando OneDrive/rclone estiver configurado.",
                "Se cv:deliver falhar por reprovação do gate, corrigir o artefato e reexecutar; se falhar só por rclone, declarar arquivo local aprovado e entrega remota bloqueada.",
                "Nao limpar outputs/_tmp antes de output_review_report.json e polish_review.json estarem coerentes com o artefato final.",
            ]
        )
    elif contract.step == "cover-letter":
        rules.extend(
            [
                "Usar .career-state/derived/cover_letter_input_pack.json como contexto primario; nao reler referencias longas no caminho feliz.",
                "Persistir primeiro a carta em Markdown e depois converter/entregar o PDF se a etapa pedir.",
                "Bloquear se o pack estiver faltando, se houver placeholders ou se o texto usar claims nao defensaveis.",
                "Responder com caminho, status e validacao objetiva; nao colar a carta completa na conversa como substituto do arquivo.",
            ]
        )
    elif contract.step == "feras":
        rules.extend(
            [
                "Usar .career-state/derived/feras_input_pack.json como contexto primario; nao reler referencias longas no caminho feliz.",
                "Persistir o FERAS em arquivo local antes de qualquer exibicao longa na conversa.",
                "A entrega precisa conter FERAS estruturado, pitch fluido e auditoria de keywords usadas/omitidas.",
                "Bloquear se houver placeholders, claims nao defensaveis ou tom promocional.",
            ]
        )
    elif contract.step == "habilidades":
        rules.extend(
            [
                "Usar .career-state/derived/habilidades_input_pack.json como contexto primario.",
                "Gerar arquivos separados para Gupy e Mercado Livre.",
                "Validar cada arquivo contra seu catalogo e contagem esperada.",
                "Nunca converter texto de um catalogo para parecer item do outro.",
            ]
        )
    elif contract.step == "notion-update":
        rules.extend(
            [
                "Usar .career-state/derived/job_extract.json e o FIT_MAP ativo como contexto primario para o dry-run.",
                "Resolver a origem pelo estado ativo e preferir atualizar a mesma pagina quando a vaga nasceu no Notion.",
                "Executar o dry-run primeiro e gravar a pending action canonica.",
                "Se a policy notion_write=explicit_request e o usuario pediu explicitamente criar/atualizar/salvar no Notion, o harness pode executar a escrita real sem segunda confirmacao.",
                "Se o pedido for de previa, preview ou dry-run, manter apenas o dry-run e nao disparar a escrita real.",
                "Usar apenas scripts locais de Notion; MCP, curl, API direta e leitura de .env sao proibidos.",
                "Para achar link por ID, usar comando canônico de resolução por ID; não varrer applications_cache ou sweep com grep.",
                "Verificar se o dry-run usa a descricao correta da vaga ativa.",
                "Bloquear se houver mismatch de descricao, template vazio sem descricao local ou mojibake no texto.",
                "Gravar em extras.pending_action_path um JSON kind=notion com a command list canonica aprovada pelo dry-run.",
            ]
        )
    elif contract.step == "email-draft":
        rules.extend(
            [
                "Preparar assunto, corpo completo e lista de anexos antes de qualquer draft real.",
                "Rodar review_email_text.py antes do preview e antes de criar draft real.",
                "Usar dry-run para validar o draft antes da aprovacao do usuario.",
                "Criar draft real somente depois de aprovacao explicita do usuario.",
                "Nunca enviar email automaticamente e nunca perguntar remetente; usar a conta Gmail autenticada.",
                "Bloquear se qualquer anexo esperado nao existir.",
                "Gravar em extras.pending_action_path um JSON kind=gmail_draft com to, subject, body e attachments.",
            ]
        )
    elif contract.step == "linkedin":
        rules.extend(
            [
                "Classificar a URL como vaga ou post antes de escolher o comando.",
                "Usar intake:linkedin-job ou intake:linkedin-post quando a extracao alimentar analise/FIT_MAP.",
                "Se a sessao estiver expirada, rodar ou solicitar npm run linkedin:auth; nao usar browser/web_search generico.",
                "Confirmar que a descricao foi persistida em inbox/job_descriptions/ ou inbox/linkedin_posts/.",
                "Confirmar active_intake e allowed_next_action com npm run agent:guard quando a extracao for para analise.",
                "Nao analisar a URL diretamente e nao inventar dados ausentes.",
            ]
        )
    return rules


def write_runbook() -> dict[str, Any]:
    payload = {
        "created_at": utc_now_iso(),
        "maestro": {
            "role": "deterministic_orchestrator",
            "responsibilities": [
                "decide next step from workflow state",
                "write compact requests",
                "run validation gates",
                "block fallback and temporary scripts",
                "respect project write policy: Gmail manual; Notion may autoexecute on explicit write requests",
            ],
        },
        "steps": [
            {"order": index + 1, "step": step, "agent": contract.agent, "purpose": contract.purpose}
            for index, (step, contract) in enumerate(CONTRACTS.items())
        ],
    }
    write_json(RUNBOOK_PATH, payload)
    return {"status": "ok", "runbook": str(RUNBOOK_PATH.relative_to(ROOT)), "steps": [item["step"] for item in payload["steps"]]}


def write_local_model_map() -> dict[str, Any]:
    payload = {
        "created_at": utc_now_iso(),
        "purpose": "Compact trigger-to-command map for smaller/local models driving this project.",
        "first_rule": "Choose the trigger that matches the user request, run the canonical entry command, then follow the generated request markdown.",
        "trigger_map": LOCAL_MODEL_TRIGGER_MAP,
        "always": [
            "Prefer npm commands from package.json over ad hoc scripts.",
            "Read compact request files before long references.",
            "Work by file paths and short summaries; do not paste full artifacts into the conversation.",
            "Use targeted reads or jq-style projections for JSON; never cat FIT_MAPs, Notion caches, registries, or long references.",
            "After editing a required artifact, run the validation command before responding.",
            "If validation fails, fix the artifact and rerun validation before responding.",
            "Return blocked only with objective blocker_reason.",
        ],
    }
    md_path = LOCAL_MODEL_MAP_PATH.with_suffix(".md")
    write_json(LOCAL_MODEL_MAP_PATH, payload)
    write_text(md_path, _local_model_map_markdown(payload))
    return {
        "status": "ok",
        "map_json": str(LOCAL_MODEL_MAP_PATH.relative_to(ROOT)),
        "map_md": str(md_path.relative_to(ROOT)),
        "triggers": [item["trigger"] for item in LOCAL_MODEL_TRIGGER_MAP],
    }


def _local_model_map_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Local Model Operating Map",
        "",
        f"Created: {payload['created_at']}",
        "",
        "## Purpose",
        payload["purpose"],
        "",
        "## First Rule",
        payload["first_rule"],
        "",
        "## Always",
        *[f"- {item}" for item in payload["always"]],
        "",
        "## Trigger Map",
    ]
    for item in payload["trigger_map"]:
        lines.extend(
            [
                "",
                f"### {item['trigger']}",
                f"- canonical_entry_command: `{item['canonical_entry_command']}`",
            ]
        )
        if item.get("fallback_entry_command"):
            lines.append(f"- fallback_entry_command: `{item['fallback_entry_command']}`")
        lines.extend(["", "Then:"])
        lines.extend(f"- {step}" for step in item["then"])
        lines.extend(["", "Forbidden:"])
        lines.extend(f"- {step}" for step in item["forbidden"])
    lines.append("")
    return "\n".join(lines)


def validate_workspace_clean() -> dict[str, Any]:
    found: list[str] = []
    for pattern in WORKSPACE_FORBIDDEN_PATTERNS:
        found.extend(str(path.relative_to(ROOT)) for path in ROOT.glob(pattern) if path.is_file())
    if found:
        return {
            "status": "blocked",
            "reason": "forbidden_root_temporary_agent_files",
            "forbidden_files": sorted(found),
            "allowed_action": "delete_or_move_files_then_rerun_validate_workspace_clean",
        }
    return {"status": "ok", "forbidden_files": []}


def maestro(step: str | None = None, *, objective: str | None = None, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    clean = validate_workspace_clean()
    if clean.get("status") != "ok":
        return clean
    runbook = write_runbook()
    if step:
        request = write_request(step, objective=objective, extras=extras)
        return {"status": "ok", "runbook": runbook, "request": request}
    requests = [write_request(step_name) for step_name in CONTRACTS]
    return {"status": "ok", "runbook": runbook, "requests": requests}
