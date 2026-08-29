# Hermes Pipeline Session Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o pipeline criar sessões Hermes enxutas para `vagas_bot_01` e `vagas_bot_02`, mantendo o histórico anterior recuperável por ID, com operação idempotente, auditável e segura por perfil/chat.

**Architecture:** O pipeline não enviará `"/new"` como texto comum ao `HarnessSupervisor`. Será criada uma ponte autenticada de controle para o gateway Hermes, que executará a mesma rotação de sessão usada pelo comando nativo. Antes da rotação, o pipeline gravará um ledger por candidatura com a sessão antiga, a nova sessão, o perfil, o `session_key`, o `run_id` e um handoff compacto; a retomada usará `/resume <session_id>` ou a mesma ponte de controle para `switch_session()`.

**Tech Stack:** Python, asyncio/aiohttp, SQLite `SessionDB`, SQLite do control-plane, `applications_v2`, testes pytest e os gateways Hermes executados por perfil.

## Global Constraints

- O reset deve atingir somente o perfil e o `session_key` solicitados; nunca resetar globalmente os dois bots.
- O histórico Hermes anterior não pode ser apagado pelo reset automático; exclusão/pruning continua sendo operação separada e explícita.
- O reset só pode ocorrer depois de os artefatos obrigatórios e o handoff compacto da candidatura estarem persistidos.
- O reset deve usar comparação com o `session_id` esperado para impedir troca acidental após uma corrida concorrente.
- O pipeline deve continuar tratando as células especialistas como processos frescos; elas não devem depender da sessão Telegram.
- A retomada de uma sessão antiga deve respeitar o mesmo perfil, plataforma, chat e origem autorizada.
- Cada operação de reset ou retomada precisa ser idempotente e deixar evidência no ledger e no log de execução.
- A configuração inicial permanece sem reset automático por idle/daily; o primeiro rollout usa somente o reset explícito no limite definido do pipeline.

---

### Task 1: Definir o contrato persistente de sessão por candidatura

**Files:**
- Create: `app/src/career/services/hermes_session_ledger.py`
- Modify: `app/src/career/services/applications_v2.py:170-190`
- Test: `app/tests/test_hermes_session_ledger.py`

**Interfaces:**
- Produces `HermesSessionLedger` with `record_reset()`, `record_resume()`, `current_binding()` and `history()`.
- Persists at `.career-state/applications_v2/<application_id>/hermes_session_ledger.json`.
- Every record contains `operation`, `profile_id`, `session_key`, `old_session_id`, `new_session_id`, `target_session_id`, `application_id`, `run_id`, `reason`, `status`, `created_at` and `idempotency_key`.

- [x] **Step 1: Write failing tests** for creating a ledger, appending a reset, rejecting a reset with a different application/profile binding, and replaying the same idempotency key without a second mutation.
- [x] **Step 2: Run the focused tests** with a temporary pytest environment; the expected collection failure confirmed the new module/API was absent. The repository's `scripts/python.sh` has no pytest dependency installed.
- [x] **Step 3: Implement atomic JSON persistence** using the project utility already used by `applications_v2`; write through a temporary file and `os.replace`, preserving prior entries.
- [x] **Step 4: Implement binding validation** so a ledger record cannot associate one application with another profile, chat route, or `session_key`.
- [x] **Step 5: Run the focused tests** and verify duplicate idempotency keys return the recorded result without appending a second operation.

### Task 2: Expor uma ponte de controle de sessão no gateway Hermes

**Files:**
- Modify: `hermes-src/gateway/run.py:11900-11980`
- Modify: `hermes-src/gateway/slash_commands.py:105-225,3529-3675`
- Modify: `hermes-src/gateway/platforms/api_server.py:1665-1865,4870-4890`
- Test: `hermes-src/tests/gateway/test_pipeline_session_control.py`

**Interfaces:**
- Add `GatewayRunner.reset_session_key(session_key, expected_session_id=None, reason="pipeline") -> dict`.
- Add `GatewayRunner.resume_session_key(session_key, target_session_id, expected_session_id=None, reason="pipeline") -> dict`.
- Add authenticated `POST /api/gateway/session-boundary` with body:

```json
{
  "operation": "reset",
  "session_key": "agent:main:telegram:dm:<chat>",
  "expected_session_id": "20260814_235751_99ca2b57",
  "target_session_id": null,
  "reason": "applications_v2:completed",
  "idempotency_key": "<run-id>:reset"
}
```

- Return `{ "status": "reset|resumed|already_applied|conflict", "old_session_id": ..., "new_session_id": ..., "session_key": ... }`.

- [x] **Step 1: Write tests** for reset rotation, expected-session conflict, resume to an ended session, invalid target origin, missing session key, and authentication failure.
- [x] **Step 2: Run the focused Hermes tests** in a temporary test environment and confirm the new methods/routes were absent before implementation.
- [x] **Step 3: Reuse the common reset lifecycle** from `_handle_reset_command()` so the native `/new` path and the programmatic path share cleanup of running agents, queues, delegations, model overrides and security state.
- [x] **Step 4: Reuse the common switch lifecycle** from `_handle_resume_command()` so the native `/resume` path and the programmatic path share target ownership/origin checks and reopening of the old session.
- [x] **Step 5: Add the authenticated API route** using the existing `API_SERVER_KEY` bearer guard; resolve the active `GatewayRunner` through the existing gateway reference and reject requests when the runner is unavailable.
- [x] **Step 6: Add compare-and-swap behavior**: if `expected_session_id` no longer matches the active route, return `conflict` and do not rotate or switch anything.
- [x] **Step 7: Run the focused tests** and confirm that both native commands and API control produce the same session-store state transitions.

The pipeline preflight is exposed as an authenticated `GET /api/gateway/session-boundary?session_key=...`; it is read-only and lets the bridge perform the expected-session CAS without guessing the active session ID.

### Task 3: Implementar o adaptador do pipeline para os dois perfis

**Files:**
- Create: `app/src/career/services/hermes_session_bridge.py`
- Modify: `app/src/career/services/applications_v2.py:40-120,2800-2920`
- Modify: `app/src/career/services/harness_supervisor.py:124-260`
- Test: `app/tests/test_hermes_session_bridge.py`
- Test: `app/tests/test_applications_v2_session_boundary.py`

**Interfaces:**
- `HermesSessionBridge.reset_for_application(application_id, profile_id, session_key, run_id, reason) -> dict`.
- `HermesSessionBridge.resume_for_application(application_id, target_session_id, run_id, reason) -> dict`.
- `HermesSessionBridge.endpoint_for_profile(profile_id) -> str` resolves only the configured local gateway endpoint for `vagas_bot_01` or `vagas_bot_02`.
- The bridge reads the active binding from `application_context`, obtains the current session ID before mutation, sends the authenticated request, and records the result through `HermesSessionLedger`.

- [x] **Step 1: Write tests** using a fake HTTP transport for successful reset, already-applied reset, gateway conflict, timeout, malformed response and unknown profile.
- [x] **Step 2: Run the focused bridge tests** and confirm failure.
- [x] **Step 3: Implement profile allowlisting** with explicit mapping for `vagas_bot_01` and `vagas_bot_02`; do not derive an endpoint from arbitrary user input.
- [x] **Step 4: Implement timeout and retry rules**: one read-only status retry is allowed; the mutating request is retried only with the same idempotency key; ambiguous timeout remains `pending_verification` until status reconciliation.
- [x] **Step 5: Integrate the bridge into `applications_v2`** behind a configuration flag disabled by default, with the boundary invoked only after a successful terminal stage (`done`, `low_fit`, or an explicitly configured review boundary), never while a stage is `*_running`.
- [x] **Step 6: Keep `HarnessSupervisor` generic-message classification unchanged** and add an explicit guard/test proving that `/new` sent to the supervisor is not mistaken for the gateway reset operation.
- [x] **Step 7: Run both focused test files** and verify that a failed gateway call leaves the application result intact and records a recoverable pending operation.

### Task 4: Criar handoff compacto e protocolo de retomada

**Files:**
- Modify: `app/src/career/services/applications_v2.py:1090-1120,1246-1260,1666-1720`
- Modify: `app/src/career/services/hermes_session_ledger.py`
- Modify: `hermes-src/gateway/slash_commands.py:3529-3675`
- Test: `app/tests/test_hermes_resume_handoff.py`
- Test: `hermes-src/tests/gateway/test_pipeline_resume_handoff.py`

**Interfaces:**
- Handoff file: `.career-state/applications_v2/<application_id>/hermes_handoff.json`.
- Handoff fields: `application_id`, `record_id`, `company`, `role`, `stage`, `service_status`, `fit_score`, `artifact_paths`, `next_action`, `last_run_id`, `current_session_id`, `previous_session_ids`, `generated_at`.
- A resumed session must be able to locate the handoff without loading the old transcript into the new session automatically.

- [x] **Step 1: Write tests** that generate a handoff before reset, verify all referenced paths exist, and verify that a new session can continue from the handoff without replaying the old 206k-token transcript.
- [x] **Step 2: Implement handoff generation** from validated `applications_v2` state and artifacts immediately before the bridge mutation.
- [x] **Step 3: Add a compact resume response** containing the application ID, stage and handoff path when the pipeline requests a fresh session.
- [x] **Step 4: Make `/resume <session_id>` preserve the handoff binding** and clear only session-scoped model/security overrides, as the existing native implementation does.
- [x] **Step 5: Add a “return to clean session” operation** after correction so a user can inspect the old transcript, correct the artifact, and then rotate again without leaving the large history active.
- [x] **Step 6: Run both focused resume test files** and verify bidirectional movement: clean session → old session → clean session.

### Task 5: Segurança, retenção e observabilidade

**Files:**
- Modify: `app/src/career/services/hermes_session_ledger.py`
- Modify: `app/src/career/services/hermes_session_bridge.py`
- Modify: `app/src/career/services/applications_v2.py:2800-2920`
- Modify: `app/TELEGRAM_HARNESS_RUNBOOK.md`
- Create: `app/docs/hermes-session-boundaries.md`
- Test: `app/tests/test_hermes_session_security.py`

**Interfaces:**
- All mutations emit structured events `session_boundary_requested`, `session_boundary_applied`, `session_boundary_conflict`, `session_boundary_pending` and `session_boundary_failed`.
- Logs include profile, application ID, `session_key` hash, old/new session IDs, run ID and idempotency key; never include bearer keys or full transcript contents.

- [x] **Step 1: Write tests** for cross-profile rejection, cross-chat rejection, stale expected-session rejection, duplicate idempotency, missing handoff rejection and bearer-key redaction.
- [x] **Step 2: Implement retention checks** that refuse to report resumability after an explicit transcript deletion; normal reset remains resumable while the Hermes session record exists.
- [x] **Step 3: Add reconciliation** at heartbeat startup for ledger entries in `pending_verification`, querying the gateway and resolving them to applied/conflict/failed without issuing an unsafe second reset.
- [x] **Step 4: Document operator commands** for `/status`, `/resume <session_id>`, session ledger inspection, and emergency disabling of automatic boundaries.
- [x] **Step 5: Run security tests** and inspect emitted logs for secret leakage.

### Task 6: Teste de integração com `vagas_bot_01` e `vagas_bot_02`

**Files:**
- Create: `app/tests/integration/test_live_hermes_session_boundary.py`
- Modify: `app/scripts/selftest_phases.py:1680-1755`
- Modify: `app/TELEGRAM_HARNESS_RUNBOOK.md`

- [x] **Step 1: Add a dry-run test** that exercises the pipeline boundary without mutating a live gateway.
- [x] **Step 2: Add a canary for `vagas_bot_01`**: capture `/status`, execute one controlled boundary, verify a new session ID, verify the old ID remains queryable and verify `/resume` returns to it.
- [x] **Step 3: Repeat the canary for `vagas_bot_02`** using its own state database and Telegram route.
- [x] **Step 4: Verify context behavior**: the first post-reset request must show a small prompt/history payload and must not contain the previous transcript; the old session must retain its original message/tool/API counts.
- [x] **Step 5: Verify failure recovery** by stopping or hiding the gateway endpoint during a dry-run and confirming that the pipeline records `pending_verification` without marking the application stage failed.
- [x] **Step 6: Run the complete relevant suites** for applications v2, harness hook, gateway sessions and integration canaries before enabling the feature.

### Task 7: Rollout controlado

**Files:**
- Modify: `hermes/vagas_bot_01/config.yaml:20-21`
- Modify: `hermes/vagas_bot_02/config.yaml:20-21`
- Modify: `.career-state/applications_v2/config.json`
- Modify: `app/docs/hermes-session-boundaries.md`

- [x] **Step 1: Enable the bridge in dry-run mode** and collect ledger records for at least one complete pipeline cycle per bot.
- [x] **Step 2: Compare expected versus actual old/new IDs, context size, API counts and resumability.**
- [x] **Step 3: Enable mutation for only one bot** while keeping the other in dry-run as a control group.
- [x] **Step 4: Verify one correction cycle** using `/resume <old_id>`, artifact correction, and a second `/new`.
- [x] **Step 5: Enable the second bot** only after the first canary passes the rollback and reconciliation checks.
- [x] **Step 6: Keep `session_reset.mode: none`** during the first rollout; automatic idle/daily policies are evaluated separately after operational evidence exists.

## Verification Checklist

- [x] `/new` native continua funcionando e usa o mesmo lifecycle compartilhado da ponte.
- [x] Uma rotação muda o `session_id` ativo e conserva o transcript antigo.
- [x] `/resume <old_session_id>` reabre somente a sessão do mesmo bot/chat.
- [x] Repetir o mesmo `run_id`/idempotency key não cria uma terceira sessão.
- [x] Um conflito de sessão não apaga, troca ou sobrescreve estado.
- [x] O handoff compacto existe antes de toda rotação aplicada.
- [x] O primeiro turno pós-reset não reutiliza os 206k tokens anteriores.
- [x] O pipeline celular continua usando processos frescos e não depende do reset Telegram.
- [x] `vagas_bot_01` e `vagas_bot_02` permanecem isolados.
- [x] Operadores conseguem desligar a automação e continuar usando `/new`/`/resume` manualmente.
