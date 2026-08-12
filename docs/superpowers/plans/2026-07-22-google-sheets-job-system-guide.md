# Google Sheets Job System Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a complete, Windows-first and harness-driven guide that lets a non-technical person build and operate a local job-application system backed by personal Google Sheets.

**Architecture:** A portable Markdown guide plus copyable templates and prompts live under one dedicated directory. `perfil/autoconhecimento.md` is the factual contract; the local project stores evidence and artifacts; Google Sheets is the operational index; a local browser session is the optional LinkedIn saved-job source.

**Tech Stack:** Markdown, PowerShell, Git, Node.js LTS, Python 3.11+, Google Sheets API with user OAuth, Google Cloud Console, Playwright, personal Google account.

## Global Constraints

- Target Windows 11 with PowerShell; non-Windows setup is out of scope.
- The chosen AI harness installs and validates each step for a non-technical reader.
- Support ChatGPT Work, Codex, Claude Code, and Gemini via a universal prompt plus adaptations.
- Use OAuth installed-app credentials for a personal Google account; never a service account by default.
- Never commit OAuth tokens, client secrets, browser cookies, CV contents, or sensitive data.
- Never automate application submission, email sending, CAPTCHA bypass, or LinkedIn login circumvention.
- Put long descriptions, FIT_MAPs, CVs, and letters in local files; Sheets stores metadata, summaries, and paths.
- Place all guide deliverables in `docs/guia-replicacao-google-sheets/`.

---

### Task 1: Scaffold the guide and profile contract

**Files:**
- Create: `docs/guia-replicacao-google-sheets/README.md`
- Create: `docs/guia-replicacao-google-sheets/templates/autoconhecimento.md`
- Create: `docs/guia-replicacao-google-sheets/templates/.gitignore`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-22-google-sheets-job-system-design.md`.
- Produces: profile template referenced by all later prompts.

- [ ] **Step 1: Create the reader entry point**

Write headings `O que este guia constrói`, `Resultado final`, `Antes de começar`, `Roteiro de implantação`, `Como operar no dia a dia`, `Segurança e limites`, `Diagnóstico e retomada`, and `Arquivos deste kit`.

- [ ] **Step 2: Create the factual-profile template**

Include sections `Identidade e posicionamento`, `Alvos e restrições`, `Experiências verificadas`, `Competências defensáveis`, `Banco de histórias`, `Formação e credenciais`, `Lacunas e limites de alegação`, and `Preferências de linguagem`. Each experience requires period, context, personal action, result with unit/period, and evidence. State: `if a metric is unknown, write não mensurado; do not estimate it`.

- [ ] **Step 3: Create the security ignore template**

Use exactly:

```gitignore
.env
credentials.json
token.json
tokens/
playwright/.auth/
browser-profile/
outputs/
```

- [ ] **Step 4: Verify profile requirements**

Run `rg -n "não mensurado|Evidência|Lacunas e limites" docs/guia-replicacao-google-sheets/templates/autoconhecimento.md`.

Expected: one or more matches for every term.

- [ ] **Step 5: Commit**

Run `git add docs/guia-replicacao-google-sheets && git commit -m "docs: scaffold Google Sheets job system guide"`.

### Task 2: Define Sheets schema and OAuth setup

**Files:**
- Create: `docs/guia-replicacao-google-sheets/google-sheets.md`
- Create: `docs/guia-replicacao-google-sheets/templates/candidaturas.csv`
- Create: `docs/guia-replicacao-google-sheets/templates/listas.csv`

**Interfaces:**
- Consumes: profile template from Task 1.
- Produces: exact tracker schema and controlled values referenced by installation and operation prompts.

- [ ] **Step 1: Document the Candidaturas data contract**

Document, in this order, each column’s type, owner and rationale: `id_candidatura`, `criada_em`, `atualizada_em`, `empresa`, `cargo`, `url_vaga`, `fonte`, `localidade`, `regime_trabalho`, `descricao_arquivo`, `descricao_hash`, `idioma_vaga`, `fit_score`, `fit_resumo`, `gaps_declarados`, `decisao`, `etapa`, `proxima_acao`, `prazo`, `cv_arquivo`, `carta_arquivo`, `pasta_artefatos`, `observacoes_humanas`, `ultimo_erro`.

- [ ] **Step 2: Document supplementary tabs**

Specify `Listas` for validation values, `Config` for non-secret configuration only, `Métricas` for formulas derived from `Candidaturas`, and `Logs` with `timestamp`, `id_candidatura`, `acao`, `resultado`, `detalhe_curto`, `run_id`.

- [ ] **Step 3: Create CSV templates**

Make `candidaturas.csv` contain only the exact header above. Make `listas.csv` contain columns `fonte`, `regime_trabalho`, `idioma_vaga`, `decisao`, `etapa` and values `linkedin_salva`, `linkedin_direta`, `indicacao`, `site_empresa`, `outro`; `remoto`, `hibrido`, `presencial`, `nao_informado`; `pt-BR`, `en`, `outro`; `prosseguir`, `pausar`, `descartar`; and approved pipeline stages.

- [ ] **Step 4: Write OAuth instructions**

Guide the harness through Google Cloud project creation, enabling Sheets and Drive APIs, creating Desktop OAuth credentials, saving credentials to an ignored local path, browser authorization, test workbook creation, and safe read/write verification. Explicitly prohibit pasting secrets into chat or Git.

- [ ] **Step 5: Verify required headers**

Run:

```powershell
$required = 'id_candidatura','descricao_hash','observacoes_humanas','ultimo_erro'
$header = (Get-Content docs/guia-replicacao-google-sheets/templates/candidaturas.csv -First 1).Split(',')
$required | ForEach-Object { if ($_ -notin $header) { throw "Missing column: $_" } }
Write-Output 'PASS: required tracker columns exist'
```

Expected: `PASS: required tracker columns exist`.

- [ ] **Step 6: Commit**

Run `git add docs/guia-replicacao-google-sheets && git commit -m "docs: add Google Sheets data contract"`.

### Task 3: Write Windows installation and harness prompts

**Files:**
- Create: `docs/guia-replicacao-google-sheets/instalacao-windows.md`
- Create: `docs/guia-replicacao-google-sheets/prompts/prompt-mestre-instalacao.md`
- Create: `docs/guia-replicacao-google-sheets/prompts/adaptacoes-por-harness.md`

**Interfaces:**
- Consumes: templates and OAuth contract from Tasks 1–2.
- Produces: installation flow compatible with the target AI harnesses.

- [ ] **Step 1: Document Windows prerequisites**

Include `winget`, Git, Node LTS, Python 3.11+, a supported browser, and terminal/VS Code. Pair every installation command with `git --version`, `node --version`, `python --version`, or `npx playwright --version`; the harness must stop and report remediation when a check fails.

- [ ] **Step 2: Write universal prompt**

Tell the harness to ask once before external account creation, create `%USERPROFILE%\Documents\SistemaCandidaturas`, initialize Git, create `perfil`, `inbox`, `state`, `outputs`, `logs`, `scripts`, copy templates, set `.gitignore`, install dependencies, configure OAuth, create/test the sheet, and summarize proof without revealing secrets. Forbid destructive commands, fabricated career facts, submissions and email sending.

- [ ] **Step 3: Add four harness adaptations**

Add short sections for ChatGPT Work, Codex, Claude Code and Gemini. Require the universal prompt first. State that a harness without terminal or persistent local browser capability can create files and prompts, but the LinkedIn extractor must run later in a local coding harness.

- [ ] **Step 4: Verify coverage**

Run `rg -n "ChatGPT Work|Codex|Claude Code|Gemini|SistemaCandidaturas" docs/guia-replicacao-google-sheets/prompts`.

Expected: matches for every harness and project directory.

- [ ] **Step 5: Commit**

Run `git add docs/guia-replicacao-google-sheets && git commit -m "docs: add harness-led Windows installation"`.

### Task 4: Document LinkedIn intake and application pipeline

**Files:**
- Create: `docs/guia-replicacao-google-sheets/linkedin-e-pipeline.md`
- Create: `docs/guia-replicacao-google-sheets/prompts/operacao-diaria.md`

**Interfaces:**
- Consumes: local project, OAuth connection, and tracker schema from Tasks 1–3.
- Produces: safe saved-job flow and operational prompts.

- [ ] **Step 1: Specify saved-job intake**

Require a user-authenticated local LinkedIn browser session. The harness lists saved jobs with title, company, URL and observed date; creates tracker rows; saves the selected vacancy to `inbox/job_descriptions/<id>.md`; calculates a hash; and only then analyzes. For expired login, CAPTCHA, inaccessible page, or short description, stop and request manual login or pasted source text; never bypass controls.

- [ ] **Step 2: Specify artifact flow**

Write the sequence: intake → evidence-based fit map → human decision → tailored CV → factual/ATS review → optional letter/pitch/skills → Sheets update → manual submission. Store artifacts under the application ID and never move `etapa` to `aplicada` automatically.

- [ ] **Step 3: Create operation prompts**

Supply prompts titled `Importar vagas salvas`, `Analisar uma vaga`, `Gerar CV`, `Revisar antes de aplicar`, and `Retomar após falha`. Every prompt reads the profile, validates state, updates only harness-owned fields, appends a log row, and reports next action.

- [ ] **Step 4: Verify safety language**

Run `rg -n "CAPTCHA|burlar|manual|aplicada" docs/guia-replicacao-google-sheets/linkedin-e-pipeline.md`.

Expected: constraints for LinkedIn and human submission.

- [ ] **Step 5: Commit**

Run `git add docs/guia-replicacao-google-sheets && git commit -m "docs: add LinkedIn intake and candidate pipeline"`.

### Task 5: Add recovery, reader validation, and final review

**Files:**
- Modify: `docs/guia-replicacao-google-sheets/README.md`
- Create: `docs/guia-replicacao-google-sheets/validacao-e-recuperacao.md`
- Create: `docs/guia-replicacao-google-sheets/checklist-final.md`

**Interfaces:**
- Consumes: all guide files from Tasks 1–4.
- Produces: a self-contained kit a fresh reader can validate and recover.

- [ ] **Step 1: Add non-destructive recovery procedures**

Cover missing Windows dependency, OAuth failure, Sheets permission failure, malformed tracker row, stale LinkedIn login, missing job description, lost local state, and review failure. Each procedure states preserved files, a safe action, and its verification result.

- [ ] **Step 2: Write final acceptance checklist**

Check profile has no invented metrics; Git tracks no secrets; test sheet accepts a row; validation lists work; a job exists locally; fit records gaps; a CV uses verified experience only; logs record an operation; submission remains manual; and a failed step can resume.

- [ ] **Step 3: Cross-link README in normal first-run order**

Link profile → installation → Sheets → test → LinkedIn or pasted intake → analysis → artifacts → review.

- [ ] **Step 4: Run integrity check**

Run:

```powershell
rg -n "TODO|TBD|<preencher>|\[a definir\]" docs/guia-replicacao-google-sheets
if ($LASTEXITCODE -eq 1) { Write-Output 'PASS: no placeholders' } else { throw 'Placeholders found' }
```

Expected: `PASS: no placeholders`.

- [ ] **Step 5: Reader test**

Give a fresh agent only the finished kit and ask: where verified accomplishments go; which data must stay outside Sheets; how personal Google authorization works; what occurs when LinkedIn requires login; and whether the system can submit an application. Correct any answer not derivable from the guide.

- [ ] **Step 6: Commit**

Run `git add docs/guia-replicacao-google-sheets && git commit -m "docs: complete Google Sheets job system guide"`.
