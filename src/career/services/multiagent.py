from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, OUTPUTS, ROOT
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


@dataclass(frozen=True, slots=True)
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
            "npm run cv:approve -- --artifact outputs/<cv>.docx",
        ],
        "forbidden": [
            "deliver CV as chat text only",
            "skip cv:approve",
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
            ".career-state/memory/profile_facts.json",
            ".career-state/memory/application_rules.json",
            ".career-state/memory/evidence_index.json",
            ".opencode/skills/career-system/references/dicionario_palavras_chave_mercado.md",
            ".opencode/skills/career-system/references/palavras_chave_carreira.md",
            ".opencode/skills/career-system/references/autoconhecimento.md",
            ".opencode/skills/career-system/references/perfil_restricoes.md",
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
            "Gerar conteudo e DOCX de CV a partir do FIT_MAP ativo, mantendo idioma, "
            "keywords e restricoes do perfil. A entrega so pode ser considerada pronta "
            "apos validacao DOCX e cv:approve no artefato final."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/memory/profile_facts.json",
            ".career-state/memory/application_rules.json",
            ".opencode/skills/cv-generator/SKILL.md",
            ".opencode/skills/career-system/references/perfil_restricoes.md",
            "scripts/docx/generate_cv_docx.js",
        ),
        allowed_commands=(
            "npm run cv:docx",
            "npm run validate:docx",
            "npm run cv:approve -- --artifact outputs/<cv>.docx",
        ),
        expected_outputs=(
            "outputs/<cv>.docx",
            "outputs/_tmp/output_review_report.json",
            "outputs/_tmp/polish_review.json",
        ),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "aprovar CV sem npm run cv:approve",
            "limpar outputs/_tmp antes da aprovacao",
            "alterar numeros criticos",
            "entregar CV sem DOCX final em outputs/",
            "considerar warnings como blockers sem o gate indicar blocker",
            "ignorar idioma requerido pela descricao da vaga",
        ),
        validation_commands=(
            "npm run validate:docx",
            "npm run cv:approve -- --artifact outputs/<cv>.docx",
        ),
    ),
    "notion-update": AgentContract(
        step="notion-update",
        agent="notion-agent",
        purpose=(
            "Preparar dry-run de criacao/atualizacao Notion usando apenas scripts locais. "
            "Escrita real exige aprovacao explicita do usuario apos revisao do dry-run."
        ),
        allowed_files=(
            ".career-state/fit_map.json",
            ".career-state/workflow_state.json",
            "inbox/job_descriptions/<descricao>.md",
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
        expected_outputs=("dry-run validado; escrita real somente apos aprovacao explicita",),
        forbidden_actions=BASE_FORBIDDEN_ACTIONS
        + (
            "executar escrita real sem aprovacao explicita",
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
    payload = {
        "created_at": utc_now_iso(),
        "step": contract.step,
        "agent": contract.agent,
        "objective": objective or contract.purpose,
        "active_intake": active,
        "fit_map": _fit_map_summary(active),
        "allowed_files": _allowed_files_for(contract, active),
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
        "extras": extras or {},
    }
    json_path = REQUEST_DIR / f"{step}_request.json"
    md_path = REQUEST_DIR / f"{step}_request.md"
    write_json(json_path, payload)
    write_text(md_path, _request_markdown(payload))
    return {"status": "ok", "step": step, "request_json": str(json_path.relative_to(ROOT)), "request_md": str(md_path.relative_to(ROOT))}


def _request_markdown(payload: dict[str, Any]) -> str:
    active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else {}
    fit_map = payload.get("fit_map") if isinstance(payload.get("fit_map"), dict) else {}
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
        "## Allowed Files",
        *[f"- `{item}`" for item in payload["allowed_files"]],
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
    if contract.step in {"fit-map", "notion-update"} and active:
        job_description_path = active.get("job_description_path")
        if isinstance(job_description_path, str) and job_description_path.strip():
            files.insert(1, job_description_path)
    return _relative_existing(tuple(files))


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
                "Ler active_intake.job_description_path antes de editar o draft.",
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
                "Confirmar que .career-state/fit_map.json existe e pertence a vaga ativa antes de gerar CV.",
                "Gerar ou atualizar o conteudo/DOCX em outputs/; nao entregar apenas texto na conversa.",
                "Rodar npm run validate:docx no DOCX gerado.",
                "Rodar npm run cv:approve -- --artifact outputs/<cv>.docx no artefato final.",
                "Se cv:approve falhar ou approved_for_delivery=false, corrigir o artefato e reexecutar o gate.",
                "Nao limpar outputs/_tmp antes de output_review_report.json e polish_review.json estarem coerentes com o artefato final.",
            ]
        )
    elif contract.step == "notion-update":
        rules.extend(
            [
                "Resolver a origem pelo estado ativo e preferir atualizar a mesma pagina quando a vaga nasceu no Notion.",
                "Executar somente dry-run ate o usuario aprovar explicitamente a escrita real.",
                "Usar apenas scripts locais de Notion; MCP, curl, API direta e leitura de .env sao proibidos.",
                "Para achar link por ID, usar comando canônico de resolução por ID; não varrer applications_cache ou sweep com grep.",
                "Verificar se o dry-run usa a descricao correta da vaga ativa.",
                "Bloquear se houver mismatch de descricao, template vazio sem descricao local ou mojibake no texto.",
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
                "request explicit approval before Notion/Gmail writes",
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
