# Agent Blockade Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restaurar o intake e o runbook para que os dois agentes possam gerar requests scoped e atravessar os gates sem perder a identidade da candidatura.

**Architecture:** O intake continuará usando SQLite como autoridade. Quando o fingerprint atual já tiver uma revisão histórica, uma nova revisão de ativação será criada para tornar esse conteúdo o revision corrente, preservando a revisão anterior. O runbook normalizará contratos legados antes da serialização.

**Tech Stack:** Python 3, SQLite, unittest/pytest, npm scripts.

**Spec:** `docs/roadmap.md` — itens `RUNTIME-015`, `RUNTIME-016`, `RUNTIME-017` e `HARNESS-017`.

## Global Constraints

- Toda execução de candidatura usa `application_id` explícito.
- Revisões históricas não serão apagadas nem sobrescritas.
- O runbook deve continuar compatível com os contratos legados em `src/career/services/agent_contracts.py`.
- Nenhum artefato de candidatura ou arquivo não relacionado será resetado.

---

### Task 1: Reintake deve reativar fingerprint histórico

**Files:**
- Modify: `tests/test_intake_gate_receipt.py`
- Modify: `src/career/services/application_context.py`

**Interfaces:**
- Consumes: `persist_intake(..., application_id/record_id, fingerprint, database)`.
- Produces: revisão corrente com `fingerprint` igual ao conteúdo recém-persistido e gate `job_description_saved` válido.

- [x] **Step 1: Write the failing test**

Adicionar um cenário com uma revisão antiga do fingerprint A, uma revisão mais nova do fingerprint B e um novo intake do conteúdo A; afirmar que `ApplicationRepository.resolve(...).fingerprint == A` e que o receipt de `job_description_saved` usa A.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest -q tests/test_intake_gate_receipt.py -k reintake`

Expected: FAIL com `application fingerprint mismatch for recorded gate receipt`.

- [x] **Step 3: Write minimal implementation**

Na transação de `persist_intake`, detectar que o fingerprint recebido existe em revisão histórica, mas não é a revisão corrente; inserir uma nova revisão de ativação apontando para o novo `job_description_id`, sem apagar a revisão anterior. Se o fingerprint já for corrente, manter a operação idempotente.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest -q tests/test_intake_gate_receipt.py -k reintake`

Expected: PASS.

### Task 2: Runbook deve normalizar contratos

**Files:**
- Create: `tests/test_multiagent_runbook.py`
- Modify: `src/career/services/multiagent.py`

**Interfaces:**
- Consumes: `CONTRACTS` legado, um dicionário por etapa.
- Produces: `multiagent_runbook.json` com `step`, `agent` e `purpose` para cada contrato.

- [x] **Step 1: Write the failing test**

Testar `write_runbook()` e afirmar que o retorno é `status=ok`, contém oito passos e que cada passo tem strings `step`, `agent` e `purpose`.

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest -q tests/test_multiagent_runbook.py`

Expected: FAIL com `AttributeError: 'dict' object has no attribute 'agent'`.

- [x] **Step 3: Write minimal implementation**

Usar a mesma normalização de `write_request()` dentro de `write_runbook()` antes de ler `agent` e `purpose`, sem alterar o contrato público de `CONTRACTS`.

- [x] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest -q tests/test_multiagent_runbook.py && npm run multiagent:runbook`

Expected: testes PASS e comando retorna `status=ok`.

### Task 3: Regression and operational verification

**Files:**
- Modify: `docs/roadmap.md`

- [x] **Step 1: Run focused tests**

Run: `PYTHONPATH=src pytest -q tests/test_intake_gate_receipt.py tests/test_multiagent_runbook.py tests/test_agent_contracts.py`

- [x] **Step 2: Run project gates**

Run: `npm run validate:structure && npm run validate:workspace-clean`

- [x] **Step 3: Re-test the real scoped state**

Run: `npm run agent:guard -- --application-id notion_578 --fingerprint 12a96610fb1bc884808acef2edfc3e2f71b34fdd9200a8cbd26033fa8880725d`.

Expected: guard allowed and next action `fill_fit_map_draft`.

- [x] **Step 4: Update roadmap evidence**

Mark `RUNTIME-015` and `HARNESS-017` as `DONE` only after the focused tests, runbook command and guard return success; record the exact test counts and date.

### Task 4: Resolve the local Hermes launcher

**Files:**
- Modify: `tests/test_runtime_mounts.py`
- Modify: `src/career/services/agent_runner.py`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: runner config with `kind=hermes`, command `hermes`, and workspace root.
- Produces: command path resolved to `/opt/hermes/bin/hermes`, PATH Hermes, or `<root>/hermes-src/hermes` in that precedence order.

- [x] **Step 1: Write the failing test**

Create an executable `hermes-src/hermes` under a temporary root, mock PATH and the container binary as unavailable, and assert that `build_command()` uses the workspace binary.

- [x] **Step 2: Run test to verify it fails**

Run: `./scripts/python.sh -m pytest -q tests/test_runtime_mounts.py -k local_workspace`

Expected: FAIL because the command remains `hermes`.

- [x] **Step 3: Write minimal implementation**

Add `<root>/hermes-src/hermes` as the final explicit candidate before returning the unresolved command name, preserving the existing container and PATH precedence.

- [x] **Step 4: Run test to verify it passes**

Run: `./scripts/python.sh -m pytest -q tests/test_runtime_mounts.py -k local_workspace`

Expected: PASS.

- [x] **Step 5: Update roadmap evidence**

Mark `RUNTIME-016` as `DONE` only after the focused runner tests and the real scoped agent invocation produce no launcher `FileNotFoundError`.

### Task 5: Stale global pointer must not break strict diagnosis

**Files:**
- Modify: `tests/test_workflow_gates.py`
- Modify: `src/career/workflow/state_store.py`
- Modify: `docs/roadmap.md`

- [x] Add a regression test for an unknown global pointer in SQLite-only mode.
- [x] Normalize this pointer to an empty non-authoritative projection while preserving strict errors for explicit scoped loads.
- [x] Verify `local:strict:doctor` in both containers.

## Verification note

The code and runtime gates are green. The host-only `agent:evaluate-notion -- 578`
now reaches the resolved Hermes executable and fails only because that host has no
configured inference provider; the two container profiles report Ollama Cloud and
remain supervised. Provider credentials/configuration were not changed here.

### Task 6: Bot01 memory review overflow

**Files:**
- Modify: `hermes/runtime/vagas_bot_01/config.yaml`
- Modify: `src/career/services/agent_guard.py`
- Modify: `tests/test_intake_sqlite_scope.py`
- Modify: `docs/roadmap.md`

- [x] Confirm the failure was in the bounded memory review, not an active task process.
- [x] Increase bot01's bounded memory limit from 2,200 to 3,000 chars, preserving existing memory.
- [x] Correct the guard fallback so a completed FIT_MAP is routed to the SQLite application stage instead of returning `análise concluída` as a command.
- [x] Restart only bot01 and verify the configuration, scoped guard, strict doctor and recent logs.

### Task 7: Cellular executor provenance path

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `src/career/services/multiagent.py`
- Modify: `tests/test_cell_cli.py`
- Modify: `tests/test_cell_workspace_safety.py`
- Modify: `docs/roadmap.md`

- [x] Reproduce the `NameError: CellExecutor is not defined` in `run_explicit_cellular()`.
- [x] Add the local import and narrow the cellular analyze contract so the agent writes the draft instead of running unrelated tests.
- [x] Retake the same run and confirm `analyze_fit` validates with a provenance-bearing artifact.

### Task 8: Historical positioning fallback

**Files:**
- Modify: `src/career/cells/handlers.py`
- Modify: `tests/test_cellular_cv_repair.py`
- Modify: `docs/roadmap.md`

- [x] Reproduce `application has no positioning revision` during `compose_cv`.
- [x] Treat only missing historical positioning/fit-map revisions as an optional pack; preserve failures for invalid data.
- [x] Allow `handler_error:*` repairs to rerun deterministic composition, while retaining external candidates for ATS repairs.
- [x] Confirm the same run generated and delivered the CV; leave Notion pending for explicit authorization.
