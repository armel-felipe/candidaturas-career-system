# Fase D Canary Runtime Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alinhar o canário ao compose real e separar preflight read-only do registro explícito de evidência D0.

**Architecture:** O target resolve workspace, state root e control plane a partir dos mounts do serviço. D0 continua sem escrita; `record-preflight` é o controlador explícito que persiste D0 somente após um preflight `ready`. D1/D2 continuam produzindo evidência compacta no state root canônico.

**Tech Stack:** Python 3.12, PyYAML, pytest, Docker Compose YAML e SQLite read-only.

## Global Constraints

- O único alvo operacional desta fase é `vagas_bot_01`.
- D0 não escreve em perfil, banco, ledger, `.career-state`, inbox ou outputs.
- O state root deve ser o source host do mount `/workspace/candidaturas/.career-state`.
- Paths de ambiente internos ao container devem ser traduzidos pelo volume correspondente.
- `record-preflight` só persiste D0 quando o resultado é `ready`.
- Nenhum bot será iniciado ou reiniciado por estes testes.
- Os três arquivos sujos preexistentes permanecem intocados.

---

### Task 1: Resolver paths de container e state root

**Files:**
- Modify: `app/src/career/services/canary_control.py`
- Test: `app/tests/test_phase_d_canary.py`
- Test: `app/tests/test_phase_d_canary_integration.py`
- Test: `app/tests/test_phase_d_runner_gate.py`

**Interfaces:** `CanaryTarget.state_root: Path`; `resolve_target_from_compose(...)` retorna o state root host e traduz paths internos declarados no ambiente.

- [ ] Escrever testes para resolver `CAREER_CONTROL_DB_PATH` e `CAREER_AUTHORITY_LEDGER_PATH` de `/workspace/candidaturas/.career-control/...` para o source host, e para manter `state_root` separado do workspace.
- [ ] Rodar os testes novos e confirmar falha porque `CanaryTarget` não possui `state_root` nem tradução de paths.
- [ ] Implementar `_resolve_service_path` e atualizar target/evidência/runner para usar `state_root` onde o contrato é `.career-state`.
- [ ] Rodar os testes focados de canário, integração e runner; confirmar verde.
- [ ] Commitar `fix: align phase d canary with mounted state roots`.

### Task 2: Registrar D0 por comando explícito

**Files:**
- Modify: `app/scripts/phase_d_canary.py`
- Test: `app/tests/test_phase_d_canary.py`

**Interfaces:** novo subcomando `record-preflight --compose <path> --bot vagas_bot_01 --json`; ele imprime o relatório D0 e retorna zero somente para `ready`, persistindo evidência/manifest apenas nesse caso.

- [ ] Escrever teste que prova que `preflight` não chama persistência e que `record-preflight` persiste D0 quando `run_preflight` retorna `ready`.
- [ ] Rodar os testes novos e confirmar falha por parser/branch ausente.
- [ ] Implementar o branch explícito reutilizando `persist_gate_evidence` somente após status `ready`.
- [ ] Rodar testes focados e verificar que D0 bloqueado não cria evidência.
- [ ] Commitar `feat: add explicit phase d preflight recording`.

### Task 3: Alinhar compose e documentação operacional

**Files:**
- Modify: `compose.yaml`
- Modify: `app/deploy/hermes/compose.yaml`
- Modify: `app/TELEGRAM_HARNESS_RUNBOOK.md`
- Modify: `app/docs/superpowers/status/architecture-implementation-control.md`
- Modify: `app/docs/superpowers/status/scope-change-log.md`

**Interfaces:** ambos os compose files declaram o control plane/ledger compartilhados e `CAREER_CONTROL_DB_ID`; o runbook documenta `preflight` → `record-preflight` → D1.

- [ ] Escrever/ajustar testes YAML que confirmem os mounts e variáveis em ambos os serviços sem alterar comandos, imagens ou restart policy.
- [ ] Atualizar os dois compose files com os paths compartilhados e o ID canônico provisionado.
- [ ] Documentar que bot02 permanece sem execução nesta fase.
- [ ] Rodar `git diff --check`, suíte proporcional e preflight read-only contra o compose canônico.
- [ ] Commitar `docs: align phase d compose authority paths`.

### Task 4: Verificação final do canário

- [ ] Rodar `record-preflight` com D0 `ready` e verificar evidência no state root correto.
- [ ] Rodar D1 dry-run sem escrever o `config.yaml`.
- [ ] Rodar o controlled-run em fixture isolada; não executar candidatura real no host.
- [ ] Rodar suíte proporcional e confirmar ausência de processos/containers iniciados.
- [ ] Atualizar o status: D0 validado no host; D1/D2 ainda fixture; D3 bloqueado até Hermes disponível.
