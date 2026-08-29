# Vagas Bot 02 Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restaurar comportamento seguro e previsível do `vagas_bot_02`, preservando `application_id` entre turnos e impedindo que uma candidatura seja confundida com outra.

**Architecture:** O HarnessSupervisor continuará sendo a única fronteira de execução. O dispatcher passará a produzir uma intenção composta e ordenada por candidatura; o estado conversacional ficará vinculado a `runtime`, `profile_id`, `session_id`, `turn_id` e `application_id`. Fallback genérico não poderá responder sobre operações de candidatura sem evidência scoped.

**Tech Stack:** Python, SQLite, pytest, scripts do HarnessSupervisor, Docker Compose, comandos npm do pipeline celular.

**Spec:** `AGENTS.md`, `.agents/skills/career-system/SKILL.md`, `.agents/skills/processe-a-vaga/SKILL.md`, `docs/roadmap.md`.

## Global Constraints

- Toda etapa operacional de candidatura exige `application_id` explícito ou resolução determinística por sessão já vinculada.
- `active_job`, `active_intake`, JSON global e varredura de `outputs/` nunca selecionam a candidatura.
- Para `standard_cv`, o fechamento exige CV aprovado, `cv:deliver`, receipt de entrega e atualização do Notion.
- Fallback genérico não pode executar nem afirmar CV, OneDrive, Notion, FIT_MAP ou status de entrega.
- Nenhuma alteração manual em FIT_MAP, `authority.json`, ledger ou receipts será usada para contornar gates.
- O bot permanece fora do fluxo de candidaturas reais até o canário `RUNTIME-010` passar duas vezes consecutivas.

## Estrutura de arquivos

- Modificar `src/career/services/application_context.py`: resolver o profile ID explícito configurado no runtime.
- Modificar `src/career/services/harness_supervisor.py`: dispatcher composto, escopo de sessão, confirmações pendentes e bloqueio do fallback operacional.
- Modificar `scripts/hermes_harness_context_hook.py`: propagar metadados completos e impedir que estado pendente expirado seja tratado como contexto válido.
- Modificar `tests/test_harness_continuity.py`: identidade, binding, retomada e continuidade por sessão.
- Modificar `tests/test_harness_notion_filters.py` ou criar `tests/test_harness_dispatch.py`: precedência do dispatcher e mensagens compostas.
- Criar `tests/test_harness_pending_confirmation.py`: confirmação afirmativa/negativa e expiração de perguntas.
- Criar `tests/test_harness_scoped_status.py`: consultas de entrega usando somente receipts da candidatura.
- Criar `tests/test_bot02_canary.py`: jornada descartável do bot, sem tocar nos artefatos reais.
- Atualizar `docs/roadmap.md` com evidência ao concluir cada item `HARNESS-004` a `HARNESS-007` e `RUNTIME-010`.

### Task 1: Corrigir identidade de runtime e bloquear a janela de risco

**Files:**
- Modify: `src/career/services/application_context.py:334-337`
- Test: `tests/test_harness_continuity.py`
- Test: `tests/test_identity_firewall.py`

**Interfaces:** `profile_id_from_env(env)` deve retornar `CAREER_HERMES_PROFILE_ID` quando definido e só calcular hash de `HERMES_HOME` como fallback. `session_key()` continua usando `runtime:profile_id:session_id`.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_explicit_hermes_profile_id_wins_over_hermes_home(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/opt/data")
    monkeypatch.setenv("CAREER_HERMES_PROFILE_ID", "bcc27ffe51db")
    assert application_context.profile_id_from_env() == "bcc27ffe51db"
```

- [ ] **Step 2: Executar o teste isolado e confirmar a falha**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_continuity.py -k explicit_hermes_profile_id`

Expected: FAIL, retornando o hash de `/opt/data` em vez de `bcc27ffe51db`.

- [ ] **Step 3: Implementar a correção mínima**

Adicionar a leitura de `CAREER_HERMES_PROFILE_ID` antes de `HERMES_HOME` em `src/career/services/application_context.py`, mantendo o hash como fallback para ambientes sem configuração explícita.

- [ ] **Step 4: Executar os testes e o smoke do container**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_continuity.py tests/test_identity_firewall.py`

Run: `docker exec hermes-vagas-bot-02 sh -lc 'PYTHONPATH=/workspace/candidaturas/src /opt/hermes/.venv/bin/python -c "from career.services import application_context; print(application_context.profile_id_from_env())"'`

Expected: testes verdes e saída `bcc27ffe51db` no bot 02.

### Task 2: Fazer mensagens compostas virarem uma intenção de pipeline

**Files:**
- Modify: `src/career/services/harness_supervisor.py:337-404, 1189-1193, 1227-1277`
- Create: `tests/test_harness_dispatch.py`

**Interfaces:** Introduzir uma decisão `pipeline` com `parameters.application_id` e `parameters.requested_steps`. A ordem mínima para `standard_cv` será `fit-map` se necessário, `cv`, `onedrive` e `notion`; o dispatcher não poderá reduzir a intenção a `notion_update` só porque a mensagem contém “Notion”.

- [ ] **Step 1: Escrever testes de roteamento composto e escopo explícito**

```python
def test_cv_onedrive_notion_is_one_scoped_pipeline():
    decision = HarnessSupervisor().classify(
        "crie o cv, envie para o onedrive e crie o registro no notion "
        "application_id local_test"
    )
    assert decision.workflow == "pipeline"
    assert decision.parameters["application_id"] == "local_test"
    assert decision.parameters["requested_steps"] == ["cv", "onedrive", "notion"]
```

```python
def test_application_id_prevents_collecting_notion_id():
    decision = HarnessSupervisor().classify(
        "retome application_id local_test e prossiga com CV, OneDrive e Notion"
    )
    assert decision.workflow == "pipeline"
    assert decision.workflow != "collect_notion_id"
```

- [ ] **Step 2: Executar os testes e confirmar que a implementação atual falha**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_dispatch.py`

Expected: FAIL porque o classificador atual retorna `notion_update` ou `collect_notion_id`.

- [ ] **Step 3: Implementar o dispatcher antes das regras unitárias**

Extrair `application_id` da mensagem, calcular `_requested_pipeline_steps(message)` e avaliar a combinação de duas ou mais etapas antes das regras isoladas de Notion/CV. Se houver etapas operacionais e nenhum `application_id` resolvido, retornar `explicit_application_scope_required` sem iniciar subprocesso.

- [ ] **Step 4: Ligar a decisão ao executor celular**

O ramo `pipeline` deve chamar a retomada scoped por `application_id`, respeitar o `delivery_profile` da candidatura e devolver uma lista de etapas com status individual. Ele não deve chamar `execute_specialist("notion-update")` como substituto do pacote completo.

- [ ] **Step 5: Rodar os testes focados**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_dispatch.py tests/test_harness_continuity.py tests/test_harness_notion_filters.py`

Expected: PASS sem regressão nos filtros e seleções Notion existentes.

### Task 3: Tornar perguntas e respostas curtas determinísticas

**Files:**
- Modify: `src/career/services/harness_supervisor.py:1018-1056`
- Modify: `scripts/hermes_harness_context_hook.py:62-126`
- Create: `tests/test_harness_pending_confirmation.py`

**Interfaces:** `pending_input.json` deve conter `session_id`, `application_id`, `turn_id`, `input_kind`, `display_text`, `created_at` e `expires_at`. O resolvedor deve aceitar `sim`/`não` somente para `input_kind` afirmativo/negativo e somente quando a sessão e a candidatura coincidirem.

- [ ] **Step 1: Escrever testes para “sim”, “não” e contexto expirado**

```python
def test_yes_resolves_the_pending_question_for_same_session(tmp_path):
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_pending_input({
        "input_kind": "confirmation",
        "session_id": "s1",
        "application_id": "app1",
        "turn_id": "t1",
        "display_text": "Gerar também o resumo ATS?",
    })
    assert supervisor._resolve_pending_input("sim", session_id="s1", application_id="app1")["answer"] is True
```

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_pending_confirmation.py`

Expected: FAIL porque o resolvedor atual só reconhece seleções numéricas para alguns tipos de input.

- [ ] **Step 3: Implementar correlação e expiração**

Alterar a assinatura do resolvedor para receber `session_id` e `application_id`, rejeitar pendências de outra sessão, limpar pendências expiradas e registrar a resposta correlacionada no envelope de auditoria.

- [ ] **Step 4: Remover o fallback genérico para mensagens operacionais sem contexto**

Quando houver pergunta pendente, ausência de escopo ou mensagem de status de candidatura, retornar bloqueio estruturado com instrução de retomada. Não executar `hermes -z` para esses casos. O fallback genérico ficará restrito a conversa não operacional sem pendência.

- [ ] **Step 5: Rodar os testes do hook e da continuidade**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_pending_confirmation.py tests/test_harness_continuity.py`

Expected: PASS; nenhuma resposta curta operacional inicia processo Hermes novo.

### Task 4: Impedir status e entrega de outra candidatura

**Files:**
- Modify: `src/career/services/harness_supervisor.py:386-404, 1189-1193`
- Create: `tests/test_harness_scoped_status.py`

**Interfaces:** Perguntas sobre “entregou CV?”, “qual arquivo?” e “está no OneDrive?” devem exigir `application_id`, consultar o registro da candidatura e o receipt de entrega scoped. Sem receipt `status=delivered`, a resposta será `blocked`.

- [ ] **Step 1: Escrever teste com Jobgether antigo e C&A sem delivery**

Preparar um banco temporário com duas candidaturas e um receipt de entrega somente para Jobgether. Consultar C&A com seu `application_id` e afirmar que o resultado não contém o arquivo de Jobgether e não retorna `delivered`.

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_scoped_status.py`

Expected: FAIL enquanto a consulta puder cair no fallback genérico ou em reports globais.

- [ ] **Step 3: Implementar a consulta scoped**

Usar `application_context.paths_for(application_id)` e as tabelas/receipts do banco canônico. Proibir glob em `outputs/`, `outputs/_tmp/` e bindings de outra candidatura como fonte de confirmação.

- [ ] **Step 4: Rodar testes de escopo e entrega**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_scoped_status.py tests/test_cv_delivery_scope.py tests/test_identity_firewall.py`

Expected: PASS; consultas sem escopo ou sem receipt são bloqueadas.

### Task 5: Executar canário realista antes de reativar o bot

**Files:**
- Create: `tests/test_bot02_canary.py`
- Modify: `docs/roadmap.md`

**Interfaces:** O canário deve usar diretório temporário, banco temporário e `session_id` fixo de teste. Deve simular: intake C&A, pedido composto, pergunta de confirmação, resposta `sim`, retomada, geração/revisão/entrega simuladas e consulta final de status.

- [ ] **Step 1: Escrever o canário com duas candidaturas**

Criar C&A e Jobgether no banco temporário; vincular somente C&A à sessão; executar a sequência e verificar que todos os envelopes operacionais contêm C&A.

- [ ] **Step 2: Rodar o canário contra o código local**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_bot02_canary.py`

Expected: FAIL até as tarefas anteriores estarem integradas.

- [ ] **Step 3: Rodar a suíte focada completa**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_continuity.py tests/test_harness_notion_filters.py tests/test_harness_dispatch.py tests/test_harness_pending_confirmation.py tests/test_harness_scoped_status.py tests/test_bot02_canary.py`

Expected: PASS.

- [ ] **Step 4: Validar o container e a sessão Telegram sem candidatura real**

Executar `docker compose config`, `docker compose ps`, o smoke de `profile_id_from_env()` nos dois bots e uma sessão Telegram de canário com dados descartáveis. Confirmar que o hook retorna envelopes estruturados e que não existe `generic_hermes_fallback` para etapas operacionais.

- [ ] **Step 5: Atualizar o roadmap com evidências**

Somente após duas execuções consecutivas do canário, mover `HARNESS-004` a `HARNESS-007` e `RUNTIME-010` para `DONE`, registrando comandos, data, IDs temporários e artefatos de teste. Antes disso, manter o bot bloqueado para entrega real.

## Critérios de encerramento

- Uma mensagem composta nunca é reduzida a uma única etapa por ordem acidental de palavras.
- “Sim” responde à pergunta correta ou recebe bloqueio explícito; nunca inicia fallback sem histórico.
- O bot não pode citar Jobgether, KnowBe4 ou qualquer outra vaga durante a execução da C&A.
- O bot não pode afirmar CV/OneDrive sem receipt scoped da candidatura.
- O canário passa duas vezes consecutivas nos containers reais.
- O roadmap contém evidência para todos os IDs deste plano.

## Execution record

- [x] Task 1 — profile ID explícito corrigido; 31 testes focados e smoke do bot 02 aprovados.
- [x] Task 2 — dispatcher composto `pipeline` implementado com `application_id` e etapas ordenadas.
- [x] Task 3 — confirmações, expiração e pendências legadas protegidas contra fallback genérico.
- [x] Task 4 — status de entrega consulta somente `deliveries` da candidatura scoped.
- [x] Task 5 — canário descartável passou duas vezes consecutivas; `validate:structure` e `runtime:verify -- --strict` passaram.
- [x] A antiga Task 6 de retomada da C&A foi removida do plano por decisão do usuário; a candidatura foi resolvida manualmente.

The canonical project suite was also run with `PYTHONPATH=src .venv/bin/pytest -q tests --import-mode=importlib`: 517 tests passed and 4 unrelated existing tests failed in concurrent CV isolation and legacy persistence fixtures (`TEST-001`, `TEST-005`, `TEST-007` and `TEST-008`). The unscoped workspace command `pytest -q` is not a valid project gate because it collects backups, Hermes runtimes and lazy-package tests; it stopped during collection with 165 environment/discovery errors.
