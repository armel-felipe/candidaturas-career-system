# Bots Canonical Flow Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auditar e corrigir o fluxo canônico compartilhado pelos dois bots para que pedidos de candidatura sejam escopados, executados na pasta correta e respondidos conversacionalmente com explicações úteis sobre bloqueios e posicionamento.

**Architecture:** O `HarnessSupervisor` continua sendo a porta de entrada única. IDs externos do Notion serão convertidos por intake em `application_id` antes de qualquer especialista; perguntas livres seguirão por um fallback Hermes que usa o mesmo resolvedor/profile do runner de etapas; diagnósticos globais serão executados como diagnósticos globais, enquanto diagnósticos de contexto continuarão explicitamente por candidatura.

**Tech Stack:** Python 3, pytest, CLI `scripts/career_cli.py`, SQLite canônico, Hermes local/perfil, arquivos scoped em `.career-state/applications_v2/<application_id>/`, logs dos perfis Hermes.

**Spec:** `AGENTS.md`, `.agents/skills/career-system/SKILL.md` e `docs/roadmap.md`.

## Global Constraints

- Toda execução operacional por vaga deve usar `application_id` canônico resolvido no SQLite.
- Estado global e ponteiros `active_*` são somente descoberta/compatibilidade e nunca selecionam execução.
- Diagnóstico global não pode exigir `WorkflowStateStore` de uma candidatura.
- Perguntas de conversa devem permanecer no supervisor/fallback conversacional e não fabricar artefatos.
- Entrega ou aprovação de CV continua sujeita aos gates existentes; esta auditoria não relaxa o firewall.
- Cada correção deve ter teste regressivo, comando de validação e entrada `DONE` em `docs/roadmap.md`.

### Task 1: Corrigir os contratos dos diagnósticos locais

**Files:**
- Modify: `src/career/cli.py:1220-1240`
- Modify: `AGENTS.md:283-291,614` e `.agents/skills/career-system/SKILL.md:125,465`
- Test: `tests/test_cell_cli.py` ou novo `tests/test_project_diagnostics_cli.py`

**Interfaces:**
- `project diagnose-runtime` chama `project_service.write_runtime_diagnosis()` sem uma candidatura ativa.
- `derive context-doctor` continua recebendo `--application-id <id>` e a documentação passa a mostrar esse escopo.

- [x] Escrever teste que execute `cli.main(["project", "diagnose-runtime", "--output", ...])` sem `WorkflowStateStore` scoped e exija código 0, JSON de diagnóstico e arquivo persistido.
- [x] Rodar o teste e confirmar o RED atual com `ValueError: run_task requires an application-scoped WorkflowStateStore`.
- [x] Trocar somente o dispatch CLI de `project.diagnose-runtime` para o serviço global `write_runtime_diagnosis`, preservando a saída existente.
- [x] Atualizar os exemplos de `context:doctor` para incluir `--application-id` e manter `runtime:diagnose` como global.
- [x] Rodar o teste focado, `npm run runtime:diagnose`, `npm run context:doctor -- --application-id notion_625` e `git diff --check`.

### Task 2: Tornar a conversa livre executável nos dois perfis

**Files:**
- Modify: `src/career/services/agent_runner.py:36-120`
- Modify: `src/career/services/harness_supervisor.py:1884-1925,3340-3355`
- Test: `tests/test_harness_live_regressions.py` e `tests/test_harness_async_dispatch.py`

**Interfaces:**
- Um helper compartilhado resolve Hermes na ordem container, `PATH`, `hermes-src/hermes` com a venv local.
- `_run_generic_message(message, model=None, profile_name=None)` preserva o perfil Hermes da sessão.

- [x] Escrever teste que simule Hermes ausente no `PATH`, disponibilize `hermes-src/hermes` e verifique que perguntas livres usam o launcher local e o `profile` recebido.
- [x] Rodar o teste e confirmar o RED por `generic_runner_unavailable` ou comando sem profile.
- [x] Extrair/reusar o resolvedor do `SubprocessAgentRunner` no fallback genérico e propagar `runtime_context.profile_id` ao chamar `_run_generic_message`.
- [x] Garantir que a rota `generic_assistant` preserve explicação do último resultado e perguntas de posicionamento sem entrar em rota de artefato.
- [x] Rodar os testes parametrizados para `vagas_bot_01` e `vagas_bot_02` e o teste de resposta de bloqueio do adapter.

### Task 3: Cobrir conversa de candidatura e bloqueios com contrato explícito

**Files:**
- Modify: `src/career/services/harness_supervisor.py:3340-3905` somente se a auditoria encontrar falha reproduzível
- Test: `tests/test_harness_live_regressions.py` e/ou `tests/test_harness_continuity.py`
- Reference: `.agents/skills/career-fit-analysis/SKILL.md` e `docs/positioning-evidence-spec.md`

**Interfaces:**
- `generic_assistant` responde perguntas sobre vaga/fit/posicionamento usando o contexto da sessão sem selecionar outra candidatura.
- `explain_last_result` explica causa, etapa não executada e próximo comando/ação quando há bloqueio.

- [x] Reproduzir perguntas como `por que parou?`, `como essa vaga me posiciona?` e `como responder essa pergunta da candidatura?` nos dois contextos de sessão.
- [x] Identificar se a falha está no roteamento, na ausência de contexto ou no launcher; não alterar comportamento sem teste RED.
- [x] Implementar somente a correção necessária, preservando respostas determinísticas de status, aprovação e escopo.
- [x] Rodar testes de conversa e verificar que nenhum pedido de pergunta livre cria CV, FIT_MAP ou update Notion indevidamente.

### Task 4: Varredura de integração dos bots e encerramento

**Files:**
- Inspect: `hermes/vagas_bot_01/`, `hermes/vagas_bot_02/`, `scripts/telegram_harness_adapter.py`, `scripts/hermes_harness_context_hook.py`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Os dois perfis carregam o workspace canônico e chegam ao mesmo supervisor/adapter.
- Logs são evidência diagnóstica; nenhum token, `.env` ou configuração secreta será exposto.

- [x] Verificar logs recentes de cada perfil, dispatches pendentes e mensagens do Harness, separando falha de rede Telegram de falha de fluxo canônico.
- [x] Rodar `npm test`, `npm run validate:structure`, `npm run runtime:verify -- --strict`, `npm run local:strict:doctor` e os diagnósticos scoped/global corrigidos.
- [x] Registrar cada falha corrigida com ID único, causa, arquivos e evidência em `docs/roadmap.md`; registrar bloqueios externos sem mascará-los como sucesso.
- [x] Fazer `git diff --check` e revisão final dos diffs e status do workspace.
