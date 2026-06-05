#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OPENCODE_SKILLS = ROOT / ".opencode" / "skills"

FORBIDDEN_PATHS = [
    "skills",
    ".claude",
    ".agents",
    "CLAUDE.md",
    "local_state",
    "install_agent_heartbeat_60min.bat",
    "resume_agent_heartbeat_60min.bat",
    "stop_active_agent_run.bat",
    "pause_agent_heartbeat_60min.bat",
    "run_agent_heartbeat_once.bat",
    "scripts/install_applications_heartbeat_task.ps1",
    "scripts/install_git_hook.ps1",
    "scripts/docx/convert_pdf.ps1",
    "scripts/install_skills.ps1",
    "scripts/extract_skills.ps1",
    "scripts/install_opencode_skills.ps1",
]

REQUIRED_SKILLS = [
    "application-keyword-table",
    "career-fit-analysis",
    "career-system",
    "cover-letter",
    "cv-generator",
    "feras-pitch",
    "general-cv-optimizer",
    "habilidades-chave",
    "intake-orchestrator",
    "networking-message",
    "notion-transactions",
    "output-reviewer",
]

FORBIDDEN_ROOT_FILE_PATTERNS = [
    ".extract_notion.py",
    "fetch_notion.py",
    "fetch_notion_v2.py",
    "fetch_record_*.py",
    "gen_*.py",
    "generate_*fitmap*.py",
    "create_drafi.py",
    "create_draft.py",
    "tmp_*.py",
    "query_record.py",
    "query_*_notion.py",
]

SCAN_ROOTS = [
    "AGENTS.md",
    "COMO_USAR.md",
    ".continue",
    ".opencode",
    ".vscode",
    "scripts",
    "sessions",
    "inbox",
]

IGNORED_PARTS = {
    "node_modules",
    "outputs",
    ".git",
    "__pycache__",
}

FORBIDDEN_TEXT = [
    "CLAUDE.md",
    "/mnt/skills",
    "local_state/",
    "local_state\\",
    "install_skills.ps1",
    "extract_skills.ps1",
    "install_opencode_skills.ps1",
    "opencode:skills",
]

REQUIRED_AGENT_GUARD_SNIPPETS = [
    "read_env",
    "curl_notion_api",
    "create_fetch_or_query_script",
]

DOC_EXPECTATIONS = {
    ".opencode/skills/career-fit-analysis/SKILL.md": [
        "### Primeiras 5 ações obrigatórias",
        'python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo_com_texto_bruto_da_vaga>',
        "depois de carregar esta skill, a proxima resposta deve executar uma acao concreta",
        "em respostas como `continue`, retomar do ultimo passo nao executado",
        "Regra dura de reposicionamento:",
        "`REPOSICIONAMENTO` nunca vira `DIRETO` por causa de narrativa forte",
        "Nao fiz exatamente X, mas fiz Y, que transfere parcialmente para X porque Z.",
        "npm run fit-map:status",
        "npm run fit-map:check:extract",
        "antes de preencher `.career-state/fit_map.draft.json`, nao escrever subtotais nem nota final na conversa",
    ],
    "AGENTS.md": [
        "depois de ler a skill pedida, executar a proxima acao concreta",
        "em respostas como `continue`, retomar do ultimo passo nao executado",
        'python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo>',
        "npm run validate:fit-map:draft",
        "depois de salvar a vaga e ler as referencias obrigatorias, deve ir direto para `npm run fit-map:template`",
        "npm run fit-map:status",
        "npm run fit-map:check:extract",
        "python scripts/diagnose_session_stall.py <session.md>",
        "antes de preencher `.career-state/fit_map.draft.json`, não escrever subtotais nem nota final na conversa",
        "presumir arquivos intermediários brutos por convenção de nome sem que tenham sido criados no runtime",
        "python scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/fit_map.json --registry .opencode/skills/career-system/references/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json",
        "qualquer bloco \"Revisão concluída\" sem `cv:approve` ou `cv:deliver` executado sobre o artefato final é inválido",
    ],
    ".opencode/skills/career-system/SKILL.md": [
        "python scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/fit_map.json --registry .opencode/skills/career-system/references/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json",
        "aprovar CV em DOCX sem executar o gate objetivo `scripts/review_output.py` sobre o artefato final em `outputs/`",
        "tratar inspeção do script gerador como substituto da revisão do DOCX final",
        "npm run fit-map:status",
        "npm run fit-map:check:extract",
        "python scripts/diagnose_session_stall.py <session.md>",
        "O workflow estruturado registra a vaga ativa por fingerprint da descrição salva",
    ],
    "COMO_USAR.md": [
        'python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo_texto_vaga>',
        "## 8.2 Checklist anti-loop para modelos locais",
        "O caminho oficial do projeto começa em `AGENTS.md`.",
        "npm run validate:fit-map:draft",
        "depois de salvar a vaga e ler as referencias obrigatorias, o agente vai direto para `npm run fit-map:template`",
        "npm run fit-map:status",
        "python scripts/diagnose_session_stall.py <session.md>",
        "antes de preencher `.career-state/fit_map.draft.json`, o agente nao escreve subtotais nem nota final na conversa",
        "nao tentar abrir arquivo bruto presumido por nome, como `*_raw.txt`",
    ],
}

SAVE_JOB_DOCS = [
    "AGENTS.md",
    "COMO_USAR.md",
]


def iter_files(path: Path):
    if path.is_file():
        yield path
        return
    if not path.exists():
        return
    for child in path.rglob("*"):
        if child.is_dir():
            continue
        if any(part in IGNORED_PARTS for part in child.relative_to(ROOT).parts):
            continue
        yield child


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def main() -> int:
    failures: list[str] = []

    if not OPENCODE_SKILLS.is_dir():
        failures.append("Missing canonical skill root: .opencode/skills")

    for name in REQUIRED_SKILLS:
        skill_path = OPENCODE_SKILLS / name / "SKILL.md"
        if not skill_path.is_file():
            failures.append(f"Missing required skill file: {skill_path.relative_to(ROOT)}")

    for rel in ["scripts/diagnose_session_stall.py"]:
        if not (ROOT / rel).is_file():
            failures.append(f"Missing required operational script: {rel}")

    for rel in ["src/career/services/multiagent.py"]:
        if not (ROOT / rel).is_file():
            failures.append(f"Missing required multiagent service: {rel}")

    agent_guard = ROOT / "src/career/services/agent_guard.py"
    if not agent_guard.is_file():
        failures.append("Missing required operational service: src/career/services/agent_guard.py")
    else:
        text = read_text(agent_guard)
        for snippet in REQUIRED_AGENT_GUARD_SNIPPETS:
            if snippet not in text:
                failures.append(f"Missing agent guard snippet {snippet!r} in src/career/services/agent_guard.py")

    for rel in FORBIDDEN_PATHS:
        if (ROOT / rel).exists():
            failures.append(f"Forbidden legacy path exists: {rel}")

    for pattern in FORBIDDEN_ROOT_FILE_PATTERNS:
        for path in ROOT.glob(pattern):
            failures.append(
                f"Forbidden root-level temporary Notion/API script exists: {path.relative_to(ROOT)}. "
                "Use npm run intake:* or scripts/notion_sync.py instead."
            )

    for search_root in [ROOT, ROOT / "scripts"]:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*"):
            if path.is_dir():
                continue
            if any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix.casefold() in {".bat", ".ps1"}:
                failures.append(f"Forbidden Windows script exists: {path.relative_to(ROOT)}")

    for scan_root in SCAN_ROOTS:
        for path in iter_files(ROOT / scan_root):
            if path == Path(__file__).resolve():
                continue
            text = read_text(path)
            if not text:
                continue
            rel_path = path.relative_to(ROOT)
            for needle in FORBIDDEN_TEXT:
                if needle in text:
                    failures.append(f"Forbidden text {needle!r} found in {rel_path}")

    for rel, required_snippets in DOC_EXPECTATIONS.items():
        path = ROOT / rel
        if not path.is_file():
            failures.append(f"Missing required documentation file: {rel}")
            continue
        text = read_text(path)
        comparable_text = text.replace("python3 scripts/", "python scripts/")
        for snippet in required_snippets:
            if snippet not in comparable_text:
                failures.append(f"Missing required guidance {snippet!r} in {rel}")

    for rel in SAVE_JOB_DOCS:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = read_text(path)
        if "--fit-map .career-state/fit_map.json --text-file" in text and '--company "<empresa>" --role "<cargo>"' not in text:
            failures.append(
                f"Ambiguous save_job_description guidance in {rel}: found --fit-map example without the pre-FIT_MAP --company/--role example."
            )

    if failures:
        print("Project structure validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Project structure validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
