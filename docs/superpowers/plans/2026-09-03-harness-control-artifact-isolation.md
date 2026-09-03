# Harness Control Artifact Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Impedir que `vagas_bot_01` e `vagas_bot_02` convertam uma atualização de Notion executada ou uma aprovação pendente em `specialist_isolation_failed`.

**Architecture:** O isolamento continuará protegendo a árvore inteira, mas reconhecerá explicitamente os artefatos de controle criados dentro da candidatura. O resultado de `notion-update`/`email-draft` só será `awaiting_approval` quando o retorno do worker, o escopo da candidatura e o isolamento estiverem válidos. Runs de dispatch órfãos serão reconciliados como espelhos operacionais, sem apagar histórico nem alterar comandos ativos no SQLite.

**Tech Stack:** Python 3.12, SQLite, HarnessSupervisor, dispatch assíncrono Hermes, pytest, Docker.

**Spec:** `docs/roadmap.md`, item `HARNESS-024`.

## Global Constraints

- Toda operação de vaga deve manter `application_id` explícito e usar `.career-state/applications_v2/<id>/` como escopo.
- A allowlist deve aceitar somente o arquivo de controle esperado: `.career-state/applications_v2/*/pending_actions/*.json`; não abrir `.career-state/**` genericamente.
- Nenhum teste pode escrever no Notion real, apagar histórico ou alterar uma candidatura não usada pelo teste.
- O estado `blocked` só pode ser emitido quando houver um blocker real; uma ação com isolamento válido deve preservar `awaiting_approval` ou `completed`.
- Ao terminar, executar `./scripts/python.sh -m pytest -q tests`, `npm run validate:structure`, `npm run runtime:verify -- --strict` e `git diff --check`.

---

### Task 1: Reproduzir os dois falsos bloqueios atuais

**Files:**
- Modify: `tests/test_harness_live_regressions.py`
- Test: `tests/test_harness_async_dispatch.py`

**Interfaces:**
- Consumes: `SPECIALIST_OUTPUT_PATTERNS`, `HarnessSupervisor._execute_pipeline_specialist` e o envelope de dispatch com `application_id`.
- Produces: regressões que distinguem `specialist_isolation_failed` real de uma ação de controle válida e verificam o escopo por candidatura.

- [x] **Step 1: Write the failing allowlist tests**

Adicionar um teste parametrizado que exija que ambos os padrões aceitem os caminhos reais:

```python
@pytest.mark.parametrize("step", ["notion-update", "email-draft"])
def test_control_action_allowlist_accepts_scoped_pending_action(step):
    path = ".career-state/applications_v2/notion_624/pending_actions/request-1.json"
    patterns = SPECIALIST_OUTPUT_PATTERNS[step]
    assert any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
```

O mesmo teste deve rejeitar `.career-state/applications_v2/notion_624/other.json`.

- [x] **Step 2: Write the failing status test**

Adicionar uma execução isolada simulada para `notion-update` em que o worker retorna código zero e altera somente o `pending_actions` scoped. O resultado esperado é `awaiting_approval`, sem `blocker_reason`:

```python
assert result["status"] == "awaiting_approval"
assert result.get("blocker_reason") is None
assert result["execution"]["isolation"]["status"] == "ok"
```

Adicionar um caso negativo em que o worker altera `not_allowed.json`; o resultado esperado continua sendo `blocked` com `specialist_isolation_failed`.

- [x] **Step 3: Run the focused tests and confirm failure**

Run:

```bash
./scripts/python.sh -m pytest -q tests/test_harness_live_regressions.py tests/test_harness_async_dispatch.py
```

Expected: FAIL porque os padrões atuais não aceitam `applications_v2/*/pending_actions/*.json`.

### Task 2: Corrigir allowlist, precedência de estado e vínculo de escopo

**Files:**
- Modify: `src/career/services/harness_supervisor.py:75-118`
- Modify: `src/career/services/harness_supervisor.py:1225-1270`
- Modify: `tests/test_harness_live_regressions.py`

**Interfaces:**
- Consumes: os padrões de saída por etapa e o payload de `request_payload["application_id"]`.
- Produces: `notion-update` e `email-draft` com isolamento válido, aprovação pendente representada como `awaiting_approval` e execução inválida bloqueada com evidência.

- [x] **Step 1: Add only the scoped control-file patterns**

Em `SPECIALIST_OUTPUT_PATTERNS`, adicionar aos dois steps:

```python
".career-state/applications_v2/*/pending_actions/*.json",
```

Manter o padrão global legado somente para compatibilidade existente; o novo fluxo deve sempre gerar o caminho scoped por `application_id`.

- [x] **Step 2: Make the status transition explicit**

Na montagem do status de `_execute_pipeline_specialist`, manter esta ordem operacional:

```python
if result.returncode != 0:
    status = "blocked"
    payload["blocker_reason"] = "specialist_runner_failed"
elif isolation.get("status") != "ok":
    status = "blocked"
    payload["blocker_reason"] = "specialist_isolation_failed"
elif step in {"notion-update", "email-draft"}:
    status = "awaiting_approval"
```

Antes dessa transição, validar que qualquer `pending_action_path` informado no request pertence ao mesmo `application_id` e à árvore `.career-state/applications_v2/<id>/pending_actions/`. Se não pertencer, bloquear com `control_artifact_scope_mismatch`.

- [x] **Step 3: Preserve the concrete worker result**

Quando a ação externa já retornar `status=written`, manter esse resultado no payload e não substituí-lo por uma mensagem genérica de isolamento. A resposta deve indicar claramente `written` ou `awaiting_approval`, conforme o estado final, e nunca afirmar que nenhuma etapa foi executada quando o worker informou sucesso.

- [x] **Step 4: Run the focused tests**

Run:

```bash
./scripts/python.sh -m pytest -q tests/test_harness_live_regressions.py tests/test_harness_async_dispatch.py tests/test_harness_continuity.py
```

Expected: PASS, incluindo o caso negativo de arquivo não permitido.

### Task 3: Reconciliar dispatches órfãos sem contaminar novas sessões

**Files:**
- Create: `scripts/reconcile_harness_dispatches.py`
- Modify: `src/career/services/harness_supervisor.py`
- Test: `tests/test_harness_async_dispatch.py`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: `state/harness/dispatches/*/status.json`, `lease.json`, `request.json` e o estado correspondente no `HarnessCommandStore`.
- Produces: relatório dry-run e reconciliação idempotente dos espelhos `running` antigos, sem apagar diretórios, sem alterar comandos SQLite ativos e sem reutilizar o `application_id` de outro perfil.

- [x] **Step 1: Write the stale-dispatch tests**

Cobrir os seguintes contratos:

```python
def test_reconcile_marks_old_running_dispatch_without_live_lease(tmp_path):
    report = reconcile_dispatches(tmp_path, older_than_seconds=300, dry_run=False)
    assert report["reconciled"] == 1
    assert read_status(tmp_path)["status"] == "blocked"
    assert read_status(tmp_path)["blocker_reason"] == "dispatch_orphaned"

def test_reconcile_does_not_touch_live_dispatch(tmp_path):
    report = reconcile_dispatches(tmp_path, older_than_seconds=300, dry_run=False)
    assert report["skipped_live"] == 1
    assert read_status(tmp_path)["status"] == "running"
```

O teste também deve confirmar que um `command_id` terminal no SQLite não é reaberto e que um dispatch de outro `profile_id` não é adotado.

- [x] **Step 2: Implement dry-run first**

O script deve aceitar:

```bash
./scripts/python.sh scripts/reconcile_harness_dispatches.py --profile vagas_bot_01 --dry-run
./scripts/python.sh scripts/reconcile_harness_dispatches.py --profile vagas_bot_02 --dry-run
```

O relatório deve listar `dispatch_id`, idade, `profile_id`, `application_id`, existência de lease vivo e ação proposta. Nenhum arquivo é alterado no dry-run.

- [x] **Step 3: Implement idempotent reconciliation**

No modo real, somente dispatches em `running` mais antigos que 300 segundos, sem processo/lease vivo e sem comando SQLite ativo podem receber `status=blocked`, `blocker_reason=dispatch_orphaned` e `completed_at`. O diretório e `result.json` devem ser preservados.

- [x] **Step 4: Run reconciliation in production**

Executar primeiro os dois dry-runs, registrar os dois dispatches observados (`bot_01` de 02/09 18:16 e `bot_02` de 02/09 23:56), depois executar o modo real somente para esses perfis. Confirmar que `active_agents=0` continua válido e que uma nova mensagem não herda esses runs.

### Task 4: Verificação de produção e encerramento

**Files:**
- Modify: `docs/roadmap.md`
- Test: `tests/test_harness_live_regressions.py`

**Interfaces:**
- Consumes: os dois containers reiniciados, o banco canônico e os resultados das Tasks 1–3.
- Produces: evidência de que o fluxo de análise → Notion/CV não gera falso bloqueio e que o item `HARNESS-024` pode ser encerrado.

- [x] **Step 1: Run the complete project test scope**

```bash
./scripts/python.sh -m pytest -q tests
```

Expected: zero failures; a coleta deve ser limitada a `tests/`, não à raiz, para não incluir backups e dependências empacotadas.

- [x] **Step 2: Run operational gates**

```bash
npm run validate:structure
npm run runtime:verify -- --strict
git diff --check
```

Expected: estrutura válida, `blockers=[]`, banco íntegro e nenhum erro de whitespace.

- [x] **Step 3: Verify the live application-specific outcomes**

Confirmar no estado persistido:

- `bot_02` / `notion_624`: atualização real preservada como `written` ou aprovação pendente, sem `specialist_isolation_failed`.
- `bot_01` / Keeta: ação de registro vinculada ao seu `application_id` ativo, sem adoção da vaga 624 e sem bloqueio falso do `pending_action`.
- Nenhum novo dispatch `running` órfão após o restart.

- [x] **Step 4: Close the roadmap item with evidence**

Atualizar `HARNESS-024` para `DONE` somente depois dos testes, dos dry-runs/reconciliação e da verificação dos dois containers. Se algum resultado live continuar bloqueado, manter `IN_PROGRESS` e registrar o blocker concreto.
