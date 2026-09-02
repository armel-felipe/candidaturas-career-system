# Cellular Recovery Hardening Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Fazer o fluxo celular recuperar falhas de forma determinística, sem duplicar runs, repetir reparos sem progresso ou bloquear o agente por execução síncrona do hook.

**Architecture:** O HarnessSupervisor será idempotente por application_id/run_id; o executor celular tratará binding stale e reparos como estados recuperáveis, sempre com handoff novo e proveniência verificável. O hook Telegram apenas persistirá e despachará um job bounded; um worker supervisionado executará o pipeline fora do turno do LLM, enquanto o runtime limitará o contexto e manterá a revisão automática de skills opt-in.

**Tech Stack:** Python 3, SQLite canônico, pathlib, subprocess, pytest, Docker Compose, Hermes shell hooks e envelopes JSON de estado.

**Spec:** docs/superpowers/specs/2026-09-01-cellular-recovery-hardening-design.md

## Global Constraints

- Alterar somente fontes canônicas versionadas e testes; não editar manualmente SQLite, FIT_MAP, cv_content, DOCX, Notion ou receipts selados.
- Preservar o mesmo application_id e run_id durante toda recuperação celular.
- Nunca criar plano serial duplicado para uma candidatura com run existente em estado recuperável.
- Nunca aceitar candidato CV sem proveniência, idioma, metadata e gate objetivo válidos.
- Repetir uma tentativa somente quando houver mudança verificável; ausência de progresso deve ser um blocker terminal explicável.
- O hook não pode liberar Hermes para executar sem supervisão se o dispatch falhar ou expirar.
- Skills canônicas só podem ser alteradas pelo fluxo de manutenção aprovado; tarefas comuns não podem chamar skill_manage.
- Cada tarefa termina com teste executável, evidência, commit isolado e revisão independente com score mínimo de 99/100.
- Não alterar os contratos de Notion, OneDrive, Gmail ou os limites de aprovação já existentes.

## Mapa de arquivos e responsabilidades

- Modify: src/career/services/harness_supervisor.py — arbitração idempotente de runs seriais, captura de stdout/stderr e status de continuação.
- Modify: src/career/cells/executor.py — recuperação de binding stale, reconciliação de reservas e handoff de tentativa fresca.
- Modify: src/career/services/applications_v2.py — detecção de progresso no reparo de CV e recuperação scoped do run.
- Modify: scripts/telegram_harness_adapter.py — envelope idempotente de dispatch e leitura de resultado do worker.
- Modify: scripts/hermes_harness_context_hook.py — dispatch bounded; nunca aguardar o pipeline completo no pre_llm_call.
- Create: scripts/hermes_harness_dispatch_worker.py — worker supervisionado que executa uma mensagem fora do turno Hermes.
- Modify: hermes-src/agent/turn_context.py ou hermes-src/agent/conversation_loop.py — limite de histórico antes do hook/modelo.
- Modify: hermes-src/agent/turn_finalizer.py e/ou hermes-src/agent/background_review.py — revisão automática de skills opt-in.
- Test: tests/test_harness_serial_pipeline.py, tests/test_cell_executor_serial.py, tests/test_cv_language_and_repair_hardening.py, tests/test_harness_dispatch.py e novos testes do worker/contexto.
- Test: hermes-src/tests/agent/ para timeout do hook, compactação e curadoria.
- Modify: docs/roadmap.md — atualizar CELLULAR-016, CELLULAR-017, HARNESS-015 e RUNTIME-021 somente com evidência.

## Interfaces entre tarefas

    def resolve_or_reuse_serial_run(
        application_id: str,
        *,
        requested_steps: list[str],
    ) -> dict[str, object]:
        """Return one existing run or create exactly one new serial run."""

    def inspect_repair_progress(
        *,
        review_report: dict[str, object],
        cv_content_sha256: str,
    ) -> dict[str, object]:
        """Return changed, no_progress or retryable with deterministic evidence."""

    def dispatch_harness_job(payload: dict[str, object]) -> dict[str, object]:
        """Persist or reuse one bounded background job without running the pipeline."""

## Task 1: Arbitrar runs seriais e recuperar binding stale

**Roadmap:** CELLULAR-016

**Files:**
- Modify: src/career/services/harness_supervisor.py, especialmente _latest_cellular_run e _run_serial_package_base.
- Modify: src/career/cells/executor.py, especialmente _validate_fit_map_draft_binding, defer_prepared_attempt e reconciliação de leases.
- Modify: src/career/services/applications_v2.py, especialmente _process_cellular_application e run_explicit_cellular.
- Test: tests/test_harness_serial_pipeline.py, tests/test_cell_executor_serial.py, tests/test_cv_language_and_repair_hardening.py.

**Interfaces:** consome o banco SQLite canônico e os manifests de tentativa; produz um único run_id por candidatura e um handoff de analyze_fit com tentativa/manifesto novos.

- [ ] Step 1: Escrever testes que reproduzem os dois incidentes.

    def test_continuation_reuses_existing_serial_run_without_new_plan(tmp_path):
        supervisor, calls = make_serial_supervisor(tmp_path, run_id="run_existing", status="running")
        result = supervisor._run_serial_package_base(
            requested_steps=["cv", "notion"],
            application_id="app_rappi",
            model=None,
            variant=None,
        )
        assert result["run_id"] == "run_existing"
        assert result["status"] == "running"
        assert not any(command[2] == "applications:plan" for command in calls)

    def test_stale_analyze_binding_is_quarantined_and_new_attempt_is_planned(tmp_path):
        executor, run_id, paths = make_analyze_run(tmp_path)
        write_stale_binding(paths, attempt=5, manifest_path="/old/manifest.json")
        result = executor.recover_stale_external_attempt(run_id, "analyze_fit")
        assert result["status"] == "planned"
        assert result["next_attempt"] == 6
        assert not paths.fit_map_draft.exists()
        assert paths.requests_dir.joinpath("quarantine").exists()

- [ ] Step 2: Executar os testes e confirmar a falha.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_harness_serial_pipeline.py \
      tests/test_cell_executor_serial.py \
      tests/test_cv_language_and_repair_hardening.py \
      -k 'reuse_existing or stale_analyze_binding or attempt'

Expected: FAIL porque a continuação ainda pode tentar applications:plan e não existe uma API única de recuperação da tentativa externa.

- [ ] Step 3: Implementar a arbitração idempotente.

    latest = self._latest_cellular_run(scoped_id)
    if latest and self._is_serial_cellular_run(latest):
        if latest["status"] in {
            "planned", "running", "awaiting_agent",
            "awaiting_approval", "blocked"
        }:
            return self._project_existing_serial_run(latest, requested_steps)

Após uma falha de applications:plan, consultar novamente application_runs; adotar o run serial recém-persistido se sua identidade e graph_json forem válidos. Capturar stdout e stderr no blocker quando nenhuma run puder ser adotada. Não criar outro plano para uma run blocked; devolver o nó bloqueado e o comando de recuperação apropriado.

- [ ] Step 4: Implementar recuperação de binding sem consumir tentativa stale.

Validar application_id, run_id, node_id, attempt, fingerprint, hash do draft e caminho do manifesto. Ao falhar, mover somente draft/binding inválidos para requests/quarantine/<timestamp>, devolver a tentativa à fila planned ou cancelá-la e criar o handoff com o novo manifesto. Uma reserva sem lease ativo não pode permanecer reserved.

- [ ] Step 5: Executar os testes direcionados e os gates estruturais.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_harness_serial_pipeline.py \
      tests/test_cell_executor_serial.py \
      tests/test_cv_language_and_repair_hardening.py
    npm run validate:structure
    git diff --check

Expected: todos passam; nenhuma mutação ocorre no checkout canônico durante o handoff externo.

- [ ] Step 6: Commitar a tarefa.

    git add src/career/services/harness_supervisor.py src/career/cells/executor.py \
      src/career/services/applications_v2.py tests/test_harness_serial_pipeline.py \
      tests/test_cell_executor_serial.py tests/test_cv_language_and_repair_hardening.py
    git commit -m "fix: recupera runs celulares sem duplicar tentativas"

## Task 2: Detectar reparo de CV sem progresso

**Roadmap:** CELLULAR-017

**Files:**
- Modify: src/career/services/applications_v2.py, no loop de reparo celular.
- Modify: src/career/cells/executor.py, para persistir evidência da tentativa.
- Test: tests/test_cv_language_and_repair_hardening.py e tests/test_cell_executor_serial.py.

**Interfaces:** consome cv_review.json, polish_review.json, hash do cv_content e blocker IDs; produz changed, retryable ou cv_repair_no_progress.

- [ ] Step 1: Escrever testes RED para candidato idêntico e blocker repetido.

    def test_identical_cv_repair_candidate_stops_without_consuming_attempt(tmp_path):
        state = make_repair_state(tmp_path, cv_hash="same", blocker="ats_top8_no_missing_unexplained")
        result = inspect_repair_progress(
            review_report=state.review_report,
            cv_content_sha256="same",
        )
        assert result["status"] == "no_progress"
        assert result["blocker_reason"] == "cv_repair_no_progress"

    def test_changed_candidate_with_missing_keyword_is_retryable(tmp_path):
        state = make_repair_state(tmp_path, cv_hash="old", blocker="ats_top8_no_missing_unexplained")
        result = inspect_repair_progress(
            review_report=state.review_report,
            cv_content_sha256="new",
        )
        assert result["status"] == "retryable"

- [ ] Step 2: Executar os testes RED.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_cv_language_and_repair_hardening.py \
      -k 'repair_progress or identical_cv_repair'

Expected: FAIL porque o loop atual reabre compose_cv e review_cv sem comparar hash/fingerprint.

- [ ] Step 3: Implementar fingerprint e limite de progresso.

Persistir em cada tentativa:

    progress = {
        "cv_content_sha256": cv_content_sha256,
        "blocker_fingerprint": sha256_json({
            "blocker_ids": sorted(blocker_ids),
            "missing_top8": sorted(missing_keywords),
        }),
    }

Antes de chamar o agente de reparo, comparar com a tentativa anterior. Se hash e fingerprint forem iguais, devolver cv_repair_no_progress sem reservar outra tentativa. Se o hash mudar, exigir metadata/proveniência válidas e deixar o mesmo run atravessar compose_cv -> render_cv -> review_cv. Após o limite configurado, retornar os termos ausentes e o caminho canônico que precisa ser corrigido; nunca afirmar aprovação.

- [ ] Step 4: Executar testes e confirmar que a entrega continua bloqueada sem aprovação.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_cv_language_and_repair_hardening.py \
      tests/test_cell_executor_serial.py
    git diff --check

- [ ] Step 5: Commitar.

    git add src/career/services/applications_v2.py src/career/cells/executor.py \
      tests/test_cv_language_and_repair_hardening.py tests/test_cell_executor_serial.py
    git commit -m "fix: interrompe reparo celular sem progresso"

## Task 3: Tornar o pre-LLM dispatch bounded e idempotente

**Roadmap:** HARNESS-015

**Files:**
- Modify: scripts/hermes_harness_context_hook.py, scripts/telegram_harness_adapter.py e hermes-src/agent/shell_hooks.py.
- Create: scripts/hermes_harness_dispatch_worker.py.
- Test: tests/test_harness_dispatch.py, tests/test_harness_pending_confirmation.py, novo tests/test_harness_async_dispatch.py e testes Hermes de `pre_llm_call`.

**Interfaces:** dispatch_harness_job(payload) grava envelope em .career-state/harness/dispatches/<message_id>/; o worker grava running, completed ou blocked no mesmo envelope e não executa o hook recursivamente.

- [x] Step 1: Escrever teste RED com supervisor lento.

    def test_pre_llm_dispatch_returns_without_waiting_for_pipeline(tmp_path, monkeypatch):
        monkeypatch.setattr(adapter, "dispatch_harness_job", slow_dispatch)
        result = adapter.dispatch_harness_job({
            "message_id": "m1",
            "message": "analise a vaga",
        })
        assert result["status"] == "awaiting_agent"
        assert result["message_id"] == "m1"
        assert result["worker_started"] is True

Também testar duas chamadas com o mesmo message_id: ambas devem retornar o mesmo job, sem iniciar dois workers.

- [x] Step 2: Executar o RED.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_harness_dispatch.py tests/test_harness_pending_confirmation.py \
      tests/test_harness_async_dispatch.py -k 'dispatch or worker'

Expected: FAIL porque hermes_harness_context_hook.py chama process_message(..., execute=True) no próprio pre_llm_call.

- [x] Step 3: Implementar envelope e worker.

O hook deve persistir o payload, adquirir lock/lease por message_id e iniciar; a classificação ocorre no worker assíncrono:

    subprocess.Popen(
        [sys.executable, str(WORKER), "--dispatch-dir", str(dispatch_dir)],
        env={**os.environ, "CAREER_HARNESS_SUBAGENT": "1"},
        start_new_session=True,
    )

O hook retorna em até 5 segundos awaiting_agent com request_id, escopo e próximo estado. O worker chama process_message(..., execute=True), persiste stdout/erro/status e libera o lease. Reentrância, processo morto e timeout devem produzir blocked estruturado; nenhum desses casos pode liberar Hermes para uma execução livre.

- [x] Step 4: Validar o hook real e a ausência de recursão.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q \
      tests/test_harness_dispatch.py tests/test_harness_pending_confirmation.py \
      tests/test_harness_async_dispatch.py
    python3 scripts/selftest_phases.py
    git diff --check

- [x] Step 5: Commitar.

Commits: `df3ec9e`, `344e6cf`, `86978e0`, `fce1bf0`, `eab4f98`, `3e8f791`, `260aea2`.
Evidência final: revisão independente `99,5/100 APPROVED`; 41 testes focados, regressão celular, `validate:structure`, `git diff --check`, self-tests 35/54 e compilação passaram.

    git add scripts/hermes_harness_context_hook.py scripts/telegram_harness_adapter.py \
      scripts/hermes_harness_dispatch_worker.py tests/test_harness_dispatch.py \
      tests/test_harness_pending_confirmation.py tests/test_harness_async_dispatch.py
    git commit -m "fix: torna dispatch do harness nao bloqueante"

## Task 4: Limitar contexto e desativar curadoria automática por padrão

**Roadmap:** RUNTIME-021

**Files:**
- Modify: hermes-src/agent/turn_context.py ou hermes-src/agent/conversation_loop.py.
- Modify: hermes-src/agent/turn_finalizer.py e/ou hermes-src/agent/background_review.py.
- Test: hermes-src/tests/agent/test_turn_context.py, hermes-src/tests/agent/test_shell_hooks.py e novo teste de curadoria.

**Interfaces:** o construtor do turno recebe um limite de caracteres configurável; a curadoria só é iniciada quando curator.enabled e curator.review_skills forem explicitamente verdadeiros.

- [x] Step 1: Escrever testes RED.

    def test_session_history_is_bounded_before_pre_llm_hook():
        history = make_history(total_chars=700_000)
        bounded = bound_session_history(history, max_chars=80_000)
        assert serialized_size(bounded) <= 80_000
        assert bounded[-1]["role"] == "user"

    def test_skill_review_is_not_started_by_default():
        assert should_review_skills(
            config={"curator": {}},
            valid_tools={"skill_manage"},
        ) is False

- [x] Step 2: Executar o RED.

    cd hermes-src
    /opt/hermes/.venv/bin/python -m pytest -q \
      tests/agent/test_turn_context.py tests/agent/test_shell_hooks.py \
      -k 'history or curator or skill_review'

Expected: FAIL porque a sessão persistente pode chegar ao hook com centenas de milhares de caracteres e a presença de skill_manage habilita revisão automática.

- [x] Step 3: Implementar compactação bounded.

Antes de montar o payload do hook/modelo, preservar a mensagem atual, o resumo de tarefa e as últimas mensagens até o limite configurado. Emitir evento session_context_compacted com tamanho anterior/novo, sem incluir o transcript completo no log. Não apagar artefatos nem estado de candidatura; somente reduzir o contexto enviado ao modelo.

- [x] Step 4: Tornar curadoria opt-in.

Alterar a decisão de iniciar revisão de skills para exigir configuração explícita. A execução normal dos bots deve permitir leitura das skills canônicas, mas não iniciar skill_manage; pedidos de mudança continuam sendo enviados ao HarnessSupervisor de manutenção.

- [x] Step 5: Executar testes Hermes e verificar que não há tentativa automática de skill_manage.

    cd hermes-src
    /opt/hermes/.venv/bin/python -m pytest -q \
      tests/agent/test_turn_context.py tests/agent/test_shell_hooks.py \
      tests/agent/test_background_review.py
    cd ..
    npm run validate:structure
    git diff --check

- [x] Step 6: Commitar.

    git add hermes-src/agent/turn_context.py hermes-src/agent/conversation_loop.py \
      hermes-src/agent/turn_finalizer.py hermes-src/agent/background_review.py \
      hermes-src/tests/agent
    git commit -m "fix: limita contexto e torna curadoria opt-in"

Evidência: commits `187b1c4`, `89ec631` e `4b6e532`; revisão independente final
`100/100 APPROVED`; testes focados de contexto/curadoria, persistência de
linhagem, cleanup de `PreLlmHookBlocked`, compilação e `git diff --check`
passaram. A integração Codex permaneceu dependente da ausência local do pacote
`openai` e não foi usada como evidência positiva.

## Task 5: Revalidar incidentes, integrar e observar

**Roadmap:** CELLULAR-016, CELLULAR-017, HARNESS-015, RUNTIME-021

**Files:**
- Modify: docs/roadmap.md.
- Test: todos os testes dos Tasks 1–4 e canários controlados.

- [x] Step 1: Executar a suíte completa na branch integrada.

    /opt/agent-projects/candidaturas/.venv/bin/python -m pytest -q tests --import-mode=importlib
    npm run validate:structure
    npm run runtime:verify -- --strict
    git diff --check

Critério: zero falhas; warnings existentes devem ser identificados e não mascarados.

Evidência executada em 2026-09-01: `785 passed, 3 warnings` em 123,14 s.
Os três warnings são `DeprecationWarning` preexistentes em
`tests/test_intake_persistence.py`, relacionados aos adaptadores legados
`configure_derived_dir` e `configure_state_store_path`. `npm run
validate:structure` passou, `npm run runtime:verify -- --strict` passou com
`blockers: []` e `git diff --check` passou.

- [x] Step 2: Executar canários descartáveis dos dois bots, um por vez.

Para cada perfil, enviar um request estruturado a um checkout descartável e verificar awaiting_agent -> committed/blocked, reviewer, receipt, resume, application_id/run_id, ausência de duplicidade e ausência de mutação no checkout de produção. Depois verificar a política de reload somente para os serviços exatos vagas_bot_01 e vagas_bot_02.

Evidência bot01, executada isoladamente: os três testes oficiais de dispatch/
worker e `test_structured_profile_request_commits_in_disposable_checkout`
para `vagas_bot_01` passaram, totalizando `5 passed in 0.30s`. As asserções
confirmaram `awaiting_agent`, envelope/lease, deduplicação de `message_id`,
resultado terminal do worker, `application_id=app_disposable`,
`run_id=run_disposable`, reviewer `99.0`, receipt `committed`,
`resume=resumed`, commit no checkout descartável e o arquivo canônico de
produção `src/career/services/cv_content.py` preservado byte a byte.

Evidência bot02, executada somente após o bot01: os testes oficiais de rota e
de checkout descartável passaram, totalizando `5 passed in 0.28s`, com
`application_id=app_disposable`, `run_id=run_disposable`, reviewer `99.0`,
receipt `committed`, `resume=resumed`, commit restrito ao checkout temporário
e o arquivo canônico de produção `src/career/services/cv_content.py`
preservado byte a byte (hash
`d79e259dc473d2396f10ee0c769e9a39661a69d2ab124adc897574de53baf8d2`).
A cobertura assíncrona foi parametrizada para os dois perfis em
`tests/test_harness_async_dispatch.py`, cobrindo `awaiting_agent`, lease stale,
deduplicação e persistência do worker para cada bot.

- [x] Step 3: Recuperar os incidentes existentes pelos comandos oficiais.

Não editar JSON/SQLite manualmente. Para Rappi, usar o mesmo application_id/run_id e o handoff fresco de analyze_fit. Para Empresa Confidencial, corrigir somente a fonte canônica do CV quando houver evidência real para as keywords, cancelar/replanejar pelo comando oficial e rerodar os gates; se não houver evidência, manter o gap declarado e reportar o blocker.

Resultado: investigação oficial executada, mas nenhuma recuperação foi
autorizada porque os dois runs live não existem na projeção canônica atual e
nenhum `application_id` pôde ser confirmado. Para Rappi,
`npm run applications:resolve -- --company Rappi` retornou
`resolver requires company and role together when using company/role
resolution`; para Empresa Confidencial, o mesmo comando com
`--company 'Empresa Confidencial'` retornou o mesmo erro. O status oficial
retornou `tracked_applications=0`; `npm run applications:list-active` retornou
somente iFood e Conexa. O run Rappi
`run_9a62f3c91c5b467c8f63b08efacf1b7f` e o run Empresa Confidencial
`run_d2ff78cd9c5644a4bf98476d223ec12b` permanecem `BLOCKED` por identidade
ausente. O gap `liderança de equipes multidisciplinares`/`NPS` permanece
declarado como `missing_unexplained`; não houve edição de fonte, JSON, SQLite,
cancelamento, replanejamento ou rerun de gates.

- [x] Step 4: Atualizar o roadmap com evidência.

Marcar cada item como DONE somente quando o teste e o canário correspondente passarem. Se o ambiente impedir uma prova, manter BLOCKED e registrar comando, saída e dependência exata.

Evidência: `docs/roadmap.md` registra CELLULAR-016/017 como `BLOCKED`, mantém
HARNESS-015 e RUNTIME-021 como `DONE` e preserva o Step 5 pendente. Os
comandos, erros e dependências exatas dos dois incidentes estão registrados
acima e nas linhas correspondentes do roadmap.

- [ ] Step 5: Integrar e fazer deploy controlado.

Após revisão independente >=99/100 de cada tarefa e suíte completa verde:

    git checkout main
    git merge --ff-only <feature-branch>
    git push origin main
    docker compose -f compose.yaml up -d --force-recreate vagas_bot_01 vagas_bot_02
    docker compose -f compose.yaml ps --status running vagas_bot_01 vagas_bot_02

Registrar o commit, os dois serviços ativos, logs sem erro de inicialização e a janela de observação pós-deploy antes de encerrar o plano.
