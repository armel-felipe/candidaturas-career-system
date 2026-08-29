# Plano: modo serial do pacote-base de candidatura

## Goal

Fechar `TEST-009` e implementar o modo serial do pacote-base usado por
`processe-a-vaga`, com a sequência `normalize → analyze → CV → OneDrive →
Notion → seal`, uma etapa lógica por invocação e sem avanço após falha,
aprovação pendente, receipt ausente ou repair incompleto.

## Architecture

Adicionar uma política serial persistida no `RunPlan` e consumida pelo mesmo
`CellExecutor`/serviço celular já existente. O modo wave continua sendo o
default de compatibilidade. A skill passa a criar runs `serial`; o executor
seleciona somente as células do estágio atual, enquanto os subagentes externos
continuam sendo disparados pelo Harness/runner oficial, com o mesmo
`application_id`, `run_id`, manifests, leases e receipts.

## Tech stack

Python 3, dataclasses, SQLite/control-plane, CLI npm/Python existente, pytest,
handlers e validators celulares existentes, subprocesso Hermes e rclone
OneDrive já configurados.

## Spec

`docs/superpowers/specs/2026-08-29-serial-package-base-design.md`

## Global constraints

- Fonte canônica de manutenção: `.agents/skills/` e `src/` do projeto.
- Não alterar `career.db`, manifests ou DOCX manualmente para contornar gates.
- Toda operação continua escopada por `--application-id` e `--run-id`.
- Não quebrar o modo wave nem o paralelismo entre candidaturas distintas.
- `completed` somente após `core_package_sealed`.
- O plano deve fechar `TEST-009` e tratar a nova frente `CELLULAR-011`;
  `HARNESS-016` cobre a semântica de status da rota conversacional.
- O reparo deve usar a run existente e os comandos oficiais; não criar
  fallback genérico, navegador ou script temporário.

## Estado inicial conhecido

Antes da implementação, registrar a baseline reproduzível. A execução focada
já observada teve `40 passed, 2 failed`: o primeiro failure é exatamente
`TEST-009`; o segundo é
`tests/test_harness_continuity.py::test_approved_handoff_uses_official_rebind_and_resumes`
e deve ser isolado, sem ser silenciosamente atribuído ao modo serial.

## Tarefas

### 1. Reproduzir a baseline e fechar TEST-009

**Roadmap:** `TEST-009`
**Arquivos:** `tests/test_cell_planner.py`.

1. Executar:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_planner.py
   ```

2. Confirmar o failure da expectativa de `compose_cv`.
3. Alterar somente a expectativa para
   `("analyze_fit", "normalize_job")`, mantendo asserções de
   `review_cv`, `sync_notion_final` e aciclicidade.
4. Acrescentar uma asserção de ordem topológica que impeça `compose_cv` de
   aparecer antes de `normalize_job`.
5. Reexecutar o arquivo e registrar o resultado no roadmap.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_planner.py
```

**Commit sugerido:** `test: align planner expectation with normalization contract`

### 2. Persistir o modo de execução no plano imutável

**Roadmap:** `CELLULAR-011`
**Arquivos:** `src/career/cells/planner.py`, `src/career/cells/executor.py`,
`src/career/cli.py`, `tests/test_cell_planner.py`, `tests/test_cell_cli.py`.

1. Adicionar `execution_mode` ao `RunPlan`, aceitando apenas `wave` e
   `serial`, com default `wave` ao ler planos antigos.
2. Incluir o campo em `as_dict()` e no `_load_run()`; manter a comparação
   exata entre JSON persistido e linha SQLite.
3. Estender `compile_run_plan()` e `CellExecutor.plan()` com o modo explícito,
   sem alterar o default dos chamadores atuais.
4. Adicionar `--execution-mode {wave,serial}` a `applications:plan`.
5. Rejeitar modo desconhecido antes de criar arquivo ou linha de run.
6. Testar persistência, compatibilidade com plano antigo e rejeição de troca de
   modo durante `applications:run`.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_planner.py tests/test_cell_cli.py
```

**Commit sugerido:** `feat: persist cellular execution mode`

### 3. Criar o contrato de estágios seriais

**Roadmap:** `CELLULAR-011`
**Arquivos:** novo `src/career/cells/serial.py`,
`src/career/cells/__init__.py`, `tests/test_cell_serial.py`.

1. Definir uma tabela ordenada de estágios: `normalize`, `analyze`, `cv`,
   `delivery`, `notion` e `seal`.
2. Mapear cada estágio aos node IDs permitidos; `cv` deve ordenar
   `compose_cv`, `render_cv`, `review_cv`.
3. Implementar funções puras para descobrir o estágio atual a partir do estado
   persistido, reconhecendo blockers, `awaiting_agent` e `awaiting_approval`.
4. Bloquear `sync_notion_initial` e `sync_notion_final` antes de `deliver_cv`,
   mesmo quando o DAG legado os reportar como ready.
5. Retornar `stage`, `status`, `completed_nodes`, `next_stage` e
   `blocked_nodes`, sem declarar conclusão do pacote.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_serial.py
```

**Commit sugerido:** `feat: define serial cellular stage policy`

### 4. Adicionar execução de exatamente um nó autorizado

**Roadmap:** `CELLULAR-011`
**Arquivos:** `src/career/cells/executor.py`,
`tests/test_cell_executor_serial.py`.

1. Extrair uma primitiva interna que reserve e execute um único node ID ready,
   usando os mesmos leases, attempts, manifests, validators e receipts de
   `run_ready()`.
2. Recusar node ausente, dependência não validada ou node fora do estágio
   serial atual.
3. Manter inalterada a semântica de `run_ready()` para planos `wave`.
4. Fazer reparos chamarem a primitiva autorizada e devolverem a attempt ao
   estado previsto quando o agente não produzir binding.
5. Testar o caso em que `compose_cv` e `sync_notion_initial` estão prontos: o
   modo serial consome somente o primeiro estágio permitido e deixa Notion sem
   attempt reservada.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_executor_serial.py tests/test_cell_parallel_integration.py
```

**Commit sugerido:** `feat: gate cellular executor by serial stage`

### 5. Integrar o scheduler serial ao serviço celular

**Roadmap:** `CELLULAR-011`
**Arquivos:** `src/career/services/applications_v2.py`,
`tests/test_cell_serial_integration.py`, testes de repair celular existentes.

1. Fazer `run_explicit_cellular()` e o heartbeat celular lerem o
   `execution_mode` da run e encaminharem runs seriais ao scheduler novo.
2. No modo serial, substituir o avanço incondicional de
   `_drain_cellular_ready_waves()` por uma chamada que consome somente o
   estágio corrente.
3. Parar após `analyze_fit`, após `review_cv` e após o receipt `delivered`,
   antes de iniciar o estágio posterior.
4. Preservar o worker pool entre candidaturas diferentes e garantir no máximo
   um agente externo ativo por candidatura.
5. Retornar `ready`/`running` quando um estágio terminou mas o pacote não;
   retornar `awaiting_agent`, `awaiting_approval` ou `blocked` quando aplicável;
   usar `completed` somente com SQLite sealed.
6. Validar que nova invocação com o mesmo `run_id` retoma o estágio correto e
   não reprocessa receipts já verificados.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_serial_integration.py tests/test_cell_deliverable_branches.py tests/test_cell_notion_delivery.py
```

**Commit sugerido:** `feat: run cellular package base serially`

### 6. Preservar dispatch e tornar reparos serialmente seguros

**Roadmap:** `CELLULAR-011`
**Arquivos:** `src/career/services/applications_v2.py`,
`src/career/cells/executor.py`, testes de workspace, repair e dispatch.

1. Disparar `analyze_fit` somente quando o estágio `analyze` estiver atual e o
   request compacto da candidatura existir.
2. Disparar repair de CV somente após blocker de `review_cv`, com nova attempt
   e binding scoped, sem delivery ou Notion no mesmo ciclo.
3. Manter a proteção de `analyze_fit` contra consumo sem
   `fit_map.draft.json`/binding, aproveitando `CELLULAR-003`.
4. Testar falha de subprocesso, timeout, aprovação pendente, lease expirado e
   receipt inválido; todos devem gerar retomada explícita ou bloqueio.
5. Testar duas aplicações distintas em paralelo e duas invocações concorrentes
   da mesma aplicação; a segunda deve ser bloqueada pelo lease.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_cell_workspace_safety.py tests/test_cell_final_review_regressions.py tests/test_cell_parallel_integration.py
```

**Commit sugerido:** `test: prove serial subagent and repair isolation`

### 7. Alinhar Harness, CLI de retomada e status conversacional

**Roadmap:** `HARNESS-016`
**Arquivos:** `src/career/services/harness_supervisor.py`, `src/career/cli.py`,
`tests/test_harness_continuity.py`, `tests/test_harness_dispatch.py`.

1. Fazer a intenção composta de `processe-a-vaga` criar ou retomar um plano
   serial do pacote-base, sem transformar a lista textual em autorização para
   executar todas as etapas na mesma chamada.
2. Manter a ordem canônica persistida no plano; a numeração do usuário não
   substitui dependências ou gates.
3. Manter `awaiting_approval` pendente e retornar `running`/`ready` com
   `next_stage` após etapa intermediária; `completed` só vale para sealed.
4. Garantir que confirmação curta retome o mesmo `application_id`/`run_id`.
5. Isolar o failure pré-existente de handoff oficial, registrando-o como
   pendência separada se continuar.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_harness_continuity.py tests/test_harness_dispatch.py
```

**Commit sugerido:** `fix: report serial pipeline continuation states`

### 8. Atualizar a skill e seus contratos operacionais

**Roadmap:** `CELLULAR-011`
**Arquivos:** `.agents/skills/processe-a-vaga/SKILL.md`,
`tests/test_skill_contracts.py`, documentação de `career-system` se exigida
pelos contratos.

1. Documentar que o pacote-base usa entrada celular com
   `--execution-mode serial`.
2. Atualizar o exemplo para planejar `cv` e `notion` na mesma run, com
   `application_id` explícito, e executar `applications:run --run-agent` uma
   vez por continuação.
3. Descrever a parada após cada estágio e os estados que exigem nova
   invocação, aprovação ou correção.
4. Remover a ambiguidade que trata Notion como ação separada quando ele faz
   parte do critério do pacote-base; manter autorização externa e receipt como
   gates.
5. Proibir na skill o uso do executor wave ou o disparo manual de etapa
   posterior fora da run.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider tests/test_skill_contracts.py
```

**Commit sugerido:** `docs: specify serial processe-a-vaga workflow`

### 9. Validar o pacote completo e atualizar o roadmap

**Roadmap:** `TEST-009`, `CELLULAR-011`, `HARNESS-016`
**Arquivos:** `docs/roadmap.md` e registro de plano.

1. Executar a suíte focada sem esconder failures de baseline.
2. Executar:

   ```bash
   npm run validate:structure
   npm run runtime:verify -- --strict
   git diff --check
   ```

3. Criar fixture descartável e comprovar em `applications:inspect-run` a ordem
   dos estágios e a ausência de attempts posteriores antes do gate atual.
4. Rodar canário serial controlado para cada agente, com `run_id` explícito;
   confirmar artefatos, status, leases e receipts. Credencial externa ausente
   deve ser registrada como `BLOCKED`, sem contorno.
5. Atualizar o roadmap: `TEST-009` só vira `DONE` com teste verde;
   `CELLULAR-011` e `HARNESS-016` recebem estado baseado em evidência.
6. Registrar comandos, datas, artefatos e falhas residuais no registro do plano.

**Teste de passagem:**

```bash
PYTHONPATH=src .venv/bin/pytest -q -p no:cacheprovider \
  tests/test_cell_planner.py tests/test_cell_serial.py \
  tests/test_cell_executor_serial.py tests/test_cell_serial_integration.py \
  tests/test_cell_cli.py tests/test_skill_contracts.py \
  tests/test_harness_continuity.py tests/test_harness_dispatch.py
```

**Commit sugerido:** `test: validate serial package-base canary`

## Revisão do plano

- Cada tarefa está vinculada a `TEST-009`, `CELLULAR-011` ou `HARNESS-016`.
- O modo wave permanece explicitamente fora da alteração comportamental.
- O plano cobre planner, executor, serviço, CLI, Harness, skill, subagentes,
  reparos, receipts, leases e canários.
- Não há placeholders nem etapas que dependam de edição manual de estado.

## Opções de execução

Após aprovação desta especificação e deste plano, a implementação pode ser
executada de duas formas:

1. **Subagent-driven:** uma tarefa por vez, com revisão entre tarefas;
   adequado para checkpoints entre planner, executor e Harness.
2. **Inline:** implementação contínua nesta sessão, mantendo os mesmos gates e
   executando a suíte após cada grupo de mudanças.
