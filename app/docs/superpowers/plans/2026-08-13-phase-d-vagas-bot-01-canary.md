# Fase D Vagas Bot 01 Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Provar o caminho real do vagas_bot_01 até o Harness e a execução celular com gates reversíveis, mantendo vagas_bot_02 intocado.

**Architecture:** Um controlador de canário fará preflight read-only, validará o alvo do perfil, instalará o hook Hermes somente quando explicitamente autorizado e executará mensagens e uma candidatura por vez. O transporte Telegram permanece no gateway Hermes; o Harness decide a rota; o control plane SQLite continua sendo a autoridade; o runner controlado será usado antes de qualquer runner real.

**Tech Stack:** Python 3.12, sqlite3 read-only, PyYAML, subprocess, shutil.which, pytest, HarnessSupervisor, CellExecutor e scripts locais do projeto.

## Global Constraints

- O único alvo permitido é vagas_bot_01; nenhuma tarefa pode modificar ou reiniciar vagas_bot_02.
- D0 não escreve em perfil, banco, ledger, .career-state, inbox ou outputs.
- D1 cria backup antes de qualquer alteração no perfil Hermes.
- D2 aceita uma candidatura explicitamente identificada e um run/attempt por vez.
- D2 usa kind=controlled; não chama Notion, OneDrive, Gmail, Telegram real nem processe-a-vaga.
- D3 só executa runner real depois de D0, D1 e D2 aprovados; ausência de binário produz blocked e não fallback.
- Relatórios registram hashes, IDs, contagens e paths; não registram prompt completo, histórico Telegram, descrição longa ou stdout ilimitado no SQLite.
- O control plane exige CAREER_CONTROL_DB_PATH, CAREER_CONTROL_DB_ID e ledger coerentes; o plano não provisiona autoridade silenciosamente.
- Preservar os três arquivos sujos preexistentes: app/scripts/docx/generate_custom_cv.js, app/scripts/linkedin_extract_job.js e app/src/career/services/cv_content.py.
- Usar PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest a partir de app/.

---

## File Map

- app/src/career/services/canary_control.py: contratos de alvo, checks read-only, política de alvo único e relatório compacto.
- app/scripts/phase_d_canary.py: CLI interna para preflight, route-smoke, controlled-run, runner-probe e rollback-dry-run.
- app/scripts/install_hermes_harness_hook.py: instalador Hermes de baixo nível, reutilizado sem alteração pelo controlador de canário.
- app/scripts/telegram_harness_adapter.py: adapter existente, exercitado por smoke tests.
- app/scripts/run_phase_c_pilot.py: piloto existente, parametrizado para um application_id explícito quando necessário.
- app/tests/test_phase_d_canary.py: preflight, alvo único, hook dry-run, route smoke e rollback dry-run.
- app/tests/test_phase_d_canary_integration.py: uma candidatura em workspace temporário e snapshot de não alteração do bot02.
- app/tests/test_phase_d_runner_gate.py: probe de runner e bloqueio sem fallback.
- app/TELEGRAM_HARNESS_RUNBOOK.md: D0/D1, backup, route-only e rollback.
- app/docs/superpowers/status/architecture-implementation-control.md: evidência dos gates.
- app/docs/superpowers/status/scope-change-log.md: estado de CHG-0006 e rollback.

---

### Task 1: Implementar preflight read-only e guard de alvo único

**Files:**
- Create: app/src/career/services/canary_control.py
- Create: app/scripts/phase_d_canary.py
- Create: app/tests/test_phase_d_canary.py

**Interfaces:** CanaryTarget(bot_name, compose_service, hermes_config, adapter_script, control_db_path, authority_ledger_path, workspace_root), assert_canary_target(target) -> None e run_preflight(target, compose_path, env) -> dict[str, Any]. O relatório contém status (ready/blocked), checks com name/status/reason, target, identidade do banco quando segura e mutations=[].

- [ ] Step 1: Escrever os testes primeiro

Cubra alvo vagas_bot_02 rejeitado; compose sem vagas_bot_01 bloqueado; adapter/config/SQLite ausentes bloqueados; SQLite lido em modo read-only; control DB/ledger/CAREER_CONTROL_DB_ID coerentes aprovados; e mutations=[] em todos os casos.

- [ ] Step 2: Confirmar a falha esperada

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k preflight --tb=short

Esperado antes da implementação: falha porque o contrato de preflight não existe.

- [ ] Step 3: Implementar checks read-only e CLI

Usar sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True); não chamar Database.init_schema() no D0. Ler o compose com YAML, confirmar o serviço canário e mounts, verificar arquivos e shutil.which sem imprimir tokens. phase_d_canary.py preflight retorna JSON compacto e código não zero quando status=blocked.

- [ ] Step 4: Validar

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k preflight --tb=short
    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python scripts/phase_d_canary.py preflight --compose compose.yaml --bot vagas_bot_01 --json

O comando do host pode bloquear pelo estado atual; registrar o motivo sem provisionar autoridade.

- [ ] Step 5: Commitar

    git add src/career/services/canary_control.py scripts/phase_d_canary.py tests/test_phase_d_canary.py
    git commit -m "feat: add phase D canary preflight"

---

### Task 2: Criar staging seguro do hook e smoke de roteamento D1

**Files:**
- Modify: app/src/career/services/canary_control.py
- Modify: app/scripts/phase_d_canary.py
- Modify: app/tests/test_phase_d_canary.py
- Modify: app/TELEGRAM_HARNESS_RUNBOOK.md

**Interfaces:** stage_hook(target, apply) -> dict[str, Any], route_smoke(root, messages, execute=False) -> list[dict[str, Any]] e rollback_dry_run(target) -> dict[str, Any]. O staging só aceita o config exato do bot01; dry-run não escreve; apply cria backup; smoke usa IDs determinísticos.

- [ ] Step 1: Testar dry-run, backup, deduplicação e exclusão do bot02

Verificar que dry-run não modifica config; apply rejeita config do bot02; backup é criado antes da escrita; status/menu são roteados; mensagem repetida retorna deduplicated=true; e o root do bot02 não aparece em mutations.

- [ ] Step 2: Confirmar falha esperada

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'hook or route or rollback' --tb=short

- [ ] Step 3: Implementar staging e smoke

Reutilizar install_hermes_harness_hook.install(config_path, apply=...) sem duplicar plugin. O wrapper rejeita caminhos do bot02, preserva o backup e nunca reinicia o gateway. O CLI expõe route-smoke e rollback-dry-run sem efeito externo.

- [ ] Step 4: Validar e documentar

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'hook or route or rollback' --tb=short
    ./scripts/python.sh scripts/phase_d_canary.py route-smoke --root /tmp/phase-d-fixture --message-id d1-1 --message 'status das candidaturas' --route-only

Atualizar o runbook com dry-run, backup, restart manual separado e rollback.

- [ ] Step 5: Commitar

    git add src/career/services/canary_control.py scripts/phase_d_canary.py tests/test_phase_d_canary.py TELEGRAM_HARNESS_RUNBOOK.md
    git commit -m "feat: add phase D canary hook staging"

---

### Task 3: Adaptar o piloto celular para uma candidatura canário explícita

**Files:**
- Modify: app/scripts/run_phase_c_pilot.py
- Modify: app/scripts/phase_d_canary.py
- Create: app/tests/test_phase_d_canary_integration.py
- Modify: app/tests/test_phase_c_pilot.py apenas para preservar defaults

**Interfaces:** run_pilot(workspace, application_id="phase-c-pilot") -> dict[str, Any] e run_controlled_canary(target, application_id, workspace) -> dict[str, Any]. O segundo aceita um único ID, usa kind=controlled e delega ao CellExecutor, CellRequestBuilder e HarnessSupervisor da Fase C.

- [ ] Step 1: Escrever integração de candidatura única

Criar fixture com control DB, ledger, uma aplicação e alvo bot01. Verificar request/hash, runtime, isolamento, validated, contagens SQLite e que uma segunda aplicação não foi criada nem tocada.

- [ ] Step 2: Confirmar falha esperada

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary_integration.py --tb=short

- [ ] Step 3: Parametrizar piloto e adicionar guard

Remover IDs hardcoded apenas onde necessário, mantendo defaults da Fase C. Antes de executar, chamar assert_canary_target, exigir application_id único e validar identidade app/run/node/attempt do request e manifest.

- [ ] Step 4: Rodar integração/regressão

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary_integration.py tests/test_phase_c_pilot.py tests/test_phase_c_harness.py tests/test_cellular_runtime.py --tb=short

- [ ] Step 5: Commitar

    git add scripts/run_phase_c_pilot.py scripts/phase_d_canary.py tests/test_phase_d_canary_integration.py tests/test_phase_c_pilot.py
    git commit -m "feat: run one application through phase D canary"

---

### Task 4: Implementar o gate D3 de runner real sem fallback

**Files:**
- Modify: app/src/career/services/canary_control.py
- Modify: app/scripts/phase_d_canary.py
- Create: app/tests/test_phase_d_runner_gate.py

**Interfaces:** probe_runner(runner_config, root) -> dict[str, Any]; a execução real só é chamada depois de D0-D2 aprovados e usa HarnessSupervisor.run_application_stage com o request/hash/allowlist da Task 3.

- [ ] Step 1: Testar runner disponível, indisponível e fallback proibido

Usar monkeypatch para shutil.which; verificar comando novo sem resume, ausência produz blocked e nenhum subprocesso é chamado no caso bloqueado.

- [ ] Step 2: Confirmar falha esperada

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_runner_gate.py --tb=short

- [ ] Step 3: Implementar probe fail-closed

Manter stdout/stderr fora do SQLite e limitar o relatório a comando, tipo, disponibilidade, return code e blocker. Não chamar processe-a-vaga, generic_hermes_fallback ou runner alternativo.

- [ ] Step 4: Validar sem ativar runner real

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_runner_gate.py tests/test_controlled_agent_runner.py tests/test_cellular_runtime.py --tb=short
    ./scripts/python.sh scripts/phase_d_canary.py runner-probe --bot vagas_bot_01 --json

Ausência de runner real deve ser registrada como blocked.

- [ ] Step 5: Commitar

    git add src/career/services/canary_control.py scripts/phase_d_canary.py tests/test_phase_d_runner_gate.py
    git commit -m "feat: add fail closed phase D runner gate"

---

### Task 5: Fechar evidências, rollback e governança

**Files:**
- Modify: app/TELEGRAM_HARNESS_RUNBOOK.md
- Modify: app/docs/superpowers/status/architecture-implementation-control.md
- Modify: app/docs/superpowers/status/scope-change-log.md
- Modify: app/tests/test_phase_d_canary.py

- [ ] Step 1: Testar relatório e não alteração

Verificar D0-D3, target bot01, hashes/IDs/contagens, mutations, ausência de tokens/histórico/prompt/descrição longa e snapshot idêntico do bot02.

- [ ] Step 2: Rodar testes da Fase D

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py tests/test_phase_d_canary_integration.py tests/test_phase_d_runner_gate.py --tb=short
    git diff --check

- [ ] Step 3: Atualizar runbook e matriz

Registrar comandos e status de cada gate. ARCH-06 só muda de divergente para em validação com evidência real de transporte pelo Harness; D3 pode ficar blocked por ausência de runner sem invalidar D0-D2.

- [ ] Step 4: Rodar suíte proporcional

    PYTHONPATH=src:scripts ../.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py tests/test_phase_d_canary_integration.py tests/test_phase_d_runner_gate.py tests/test_cell_workspace_safety.py tests/test_cell_parallel_integration.py tests/test_runtime_control.py --tb=no

Separar falhas novas das 15 falhas ambientais já documentadas. Não marcar CHG-0006 concluído com gate real ausente ou teste sem evidência.

- [ ] Step 5: Commitar governança

    git add TELEGRAM_HARNESS_RUNBOOK.md docs/superpowers/status/architecture-implementation-control.md docs/superpowers/status/scope-change-log.md tests/test_phase_d_canary.py
    git commit -m "docs: record phase D canary evidence"

## Handoff

Após aprovação, executar as tarefas em sessão separada usando superpowers:executing-plans ou superpowers:subagent-driven-development. O primeiro comando real é o preflight em fixture; o primeiro alvo de D0 é read-only. Nenhum --apply, restart de gateway ou processamento real ocorre antes de o relatório D0 estar ready.
