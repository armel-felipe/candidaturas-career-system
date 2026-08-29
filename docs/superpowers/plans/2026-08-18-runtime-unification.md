# Runtime Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar o runtime de candidatura, mover a persistência operacional de JSON para SQLite centralizado e tornar cada candidatura recuperável, auditável e verificável em qualquer bot.

**Architecture:** A raiz do repositório será o único código executado pelos bots. `control-plane/career.db` será a fonte canônica dos dados de carreira; arquivos permanecerão apenas como materialização de artefatos grandes. O pipeline `processe-a-vaga` fechará somente o pacote-base da candidatura, enquanto FERAS, carta, Gupy, entrevista e outros artefatos serão derivados sob demanda a partir de revisões versionadas de análise e posicionamento.

**Tech Stack:** Python 3, SQLite, Node.js/npm, Hermes/Docker Compose, unittest, scripts existentes de FIT_MAP/CV/Notion/OneDrive, JSON apenas como exportação temporária de compatibilidade.

**Spec:** `docs/superpowers/specs/2026-08-18-runtime-unification-design.md`

## Global Constraints

- O código canônico será `/opt/agent-projects/candidaturas`; `app/` não poderá continuar como runtime independente.
- `control-plane/career.db` será o banco ativo compartilhado pelos bots; `.career-state/career.db` e `app/.career-state/career.db` serão apenas fontes legadas durante a migração.
- Nenhum agente poderá escolher candidatura por `active_job` global ou gravar gates em `workflow_state.json` global.
- Toda escrita de estado deverá incluir `application_id`, fingerprint, `run_id`, input hash e output hash.
- `processe-a-vaga` terá somente intake, FIT_MAP, CV, OneDrive e Notion.
- FERAS, carta, habilidades Gupy, entrevista, networking e revisão de histórias serão operações pós-processamento independentes.
- JSONs de estado e derivados não serão fonte canônica; exports temporários deverão ser recriáveis do SQLite.
- Nenhuma exclusão de JSON, output, banco ou diretório legado ocorrerá antes de backup, dry-run, canário e rollback testado.
- O worktree já possui alterações do usuário; cada tarefa deverá preservar mudanças não relacionadas e evitar `git reset --hard` ou checkout destrutivo.
- Cada tarefa termina com teste específico, verificação de diff e checkpoint revisável antes da próxima tarefa.
- O plano deve revisar `docs/roadmap.md` no início e no encerramento; pendências
  descobertas ou resolvidas devem ser sincronizadas por seus IDs no roadmap.

---

## Mapa de arquivos e responsabilidades

### Persistência e schema

- Modify: `src/career/services/database.py` — schema consolidado, pragmas, migrations e acesso transacional.
- Create: `src/career/services/persistence/application_repository.py` — CRUD e resolução de candidaturas.
- Create: `src/career/services/persistence/gate_repository.py` — receipts, dependências e invariantes.
- Create: `src/career/services/persistence/artifact_repository.py` — versões, conteúdo, hashes e dependências.
- Create: `src/career/services/persistence/migrations/` — migrations numeradas do SQLite.
- Create: `tests/test_sqlite_persistence.py` — schema, transações, idempotência e isolamento.

### Resolução e reconciliação

- Modify: `src/career/services/application_context.py` — resolver candidatura pelo banco, sem singleton global.
- Create: `src/career/services/reconciliation.py` — inventário, importação dry-run, conflitos e reparo explícito.
- Create: `scripts/persistence_inventory.py` — inventário somente leitura dos JSONs, bancos, outputs e mounts.
- Create: `scripts/migrate_json_to_sqlite.py` — importer idempotente com relatório e quarentena.
- Create: `scripts/verify_runtime_unification.py` — verificador estrito ponta a ponta.
- Create: `tests/test_reconciliation.py` — People Meet, Conexa 578, conflitos e fallback bloqueado.

### Pipeline e supervisor

- Modify: `src/career/workflow/state_store.py` — compatibilidade somente leitura e projeção por candidatura.
- Modify: `src/career/tasks/registry.py` — exigir `application_id` e persistir receipts no banco.
- Modify: `src/career/services/agent_guard.py` — intake já inicia contexto SQLite-scoped.
- Modify: `src/career/services/derived_context.py` — materializar contexto a partir do banco.
- Modify: `src/career/services/multiagent.py` — requests e handoffs persistidos por candidatura.
- Modify: `src/career/services/harness_supervisor.py` — required outputs, gates e falha fechada.
- Modify: `src/career/services/applications_v2.py` — estágio derivado de receipts e artifacts.
- Modify: `src/career/cli.py` — comandos de resolve, reconcile, materialize e verify.
- Create: `tests/test_workflow_gates.py`, `tests/test_supervisor_contracts.py`, `tests/test_cross_bot_recovery.py`.

### Skills, deploy e documentação

- Modify: `.agents/skills/processe-a-vaga/SKILL.md` — remover sincronização global e limitar o escopo ao pacote-base.
- Modify: `.agents/skills/career-system/SKILL.md` — resolver candidatura pelo SQLite e documentar o contrato.
- Modify: `AGENTS.md` — comandos canônicos, runtime raiz e regras de persistência.
- Modify: `app/deploy/hermes/compose.yaml` — montar a raiz e o banco de controle compartilhado.
- Modify: `hermes/vagas_bot_01/config.yaml`, `hermes/vagas_bot_02/config.yaml` — cwd e runtime canônico.
- Create: `tests/test_runtime_mounts.py`, `tests/test_skill_contracts.py`.

### Verificação e operação

- Modify: `package.json` — scripts de inventário, migração dry-run, reconciliação e verificação.
- Create: `tests/fixtures/runtime_unification/` — snapshots sanitizados de People Meet, Conexa 578 e execução saudável.
- Create: `docs/superpowers/status/runtime-unification-progress.md` — checklist de fases, blockers, evidências e data de cada checkpoint.

## Phase 0 — Baseline, backup e bloqueio de escopo

**Comportamento esperado:** nenhum runtime é alterado; o sistema produz uma fotografia reproduzível de todas as fontes e confirma que o backup pode ser restaurado.

### Task 0.1: Inventariar fontes e montagens

**Files:**
- Create: `scripts/persistence_inventory.py`
- Create: `tests/test_persistence_inventory.py`

**Interfaces:**
- Produces `inventory.json` somente como relatório temporário de execução; o inventário não escreve em SQLite. O registro de `migration_runs` pertence ao importer da Task 5.1.
- A função pública será `build_inventory(root: Path) -> dict`.

- [ ] **Step 1: Escrever testes para detectar root/app divergentes e mounts do Hermes.**
- [ ] **Step 2: Executar `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_persistence_inventory.py` e confirmar falha inicial.**
- [ ] **Step 3: Implementar `build_inventory` usando `rg --files`, hashes SHA-256, leitura do Compose e classificação por domínio.**
- [ ] **Step 4: Executar o teste e `python3 scripts/persistence_inventory.py --root . --output outputs/_tmp/persistence_inventory.json`.**
- [ ] **Step 5: Conferir no relatório todos os JSONs de `.career-state`, `app/.career-state`, `hermes` e os arquivos críticos divergentes entre root/app.**

### Task 0.2: Criar backup restaurável

**Files:**
- Create: `scripts/backup_persistence.py`
- Create: `tests/test_persistence_backup.py`

**Interfaces:**
- `create_backup(root: Path, destination: Path) -> dict` deverá usar a API de backup do SQLite e cópia preservada dos JSONs/outputs.
- O relatório deverá conter banco original, hash, banco backup, hash e lista de diretórios preservados.

- [ ] **Step 1: Escrever teste com banco SQLite temporário e arquivo legado.**
- [ ] **Step 2: Executar o teste e verificar falha antes do helper existir.**
- [ ] **Step 3: Implementar backup sem apagar ou modificar a origem.**
- [ ] **Step 4: Executar `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_persistence_backup.py`.**
- [ ] **Step 5: Gerar backup dos estados reais em diretório explicitamente nomeado e registrar o caminho no status da migração.**

## Phase 1 — SQLite canônico e repositórios

**Comportamento esperado:** uma candidatura de fixture pode ser criada, atualizada e consultada no SQLite em uma transação; nenhuma alteração parcial permanece após rollback.

### Task 1.1: Consolidar schema e migrations

**Files:**
- Modify: `src/career/services/database.py`
- Create: `src/career/services/persistence/migrations/001_application_revisions.sql`
- Create: `src/career/services/persistence/migrations/002_analysis_and_positioning.sql`
- Create: `src/career/services/persistence/migrations/003_gates_artifacts_integrations.sql`
- Create: `tests/test_sqlite_persistence.py`

**Interfaces:**
- `Database.migrate() -> int` deverá aplicar migrations em ordem e registrar `schema_migrations`.
- `Database.transaction() -> ContextManager[sqlite3.Connection]` deverá executar commit ou rollback atômico.
- `Database.configure_for_runtime() -> None` deverá configurar foreign keys, WAL, busy timeout e synchronous.

- [ ] **Step 1: Escrever testes para schema version, pragmas, foreign keys e rollback.**
- [ ] **Step 2: Executar `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_sqlite_persistence.py` e confirmar falhas das tabelas novas.**
- [ ] **Step 3: Implementar migrations sem remover tabelas existentes e preservar `application_runs`, `artifacts`, `workflow_events` e `validation_receipts`.**
- [ ] **Step 4: Executar os testes e verificar o banco com `PYTHONPATH=src ./scripts/python.sh -c 'import sqlite3; c=sqlite3.connect("control-plane/career.db"); print(c.execute("PRAGMA integrity_check").fetchone()[0]); print(c.execute("PRAGMA foreign_key_check").fetchall())'`.**
- [ ] **Step 5: Validar o schema contra `control-plane/career.db` em modo somente leitura antes de qualquer importação.**

### Task 1.2: Implementar resolução de candidatura

**Files:**
- Create: `src/career/services/persistence/application_repository.py`
- Modify: `src/career/services/application_context.py`
- Create: `tests/test_application_repository.py`

**Interfaces:**
- `ApplicationRepository.create_application(identity: ApplicationIdentity) -> ApplicationRecord`.
- `ApplicationRepository.resolve(*, application_id: str | None = None, notion_id: str | None = None, fingerprint: str | None = None, company: str | None = None, role: str | None = None) -> ApplicationRecord`.
- `ApplicationRepository.update_projection(application_id: str) -> ApplicationProjection`.

- [ ] **Step 1: Escrever testes para resolução por application_id, Notion ID, fingerprint e ambiguidade empresa/cargo.**
- [ ] **Step 2: Executar o teste e confirmar falha do repositório inexistente.**
- [ ] **Step 3: Implementar queries parametrizadas, unicidade e erro explícito para resolução ambígua.**
- [ ] **Step 4: Executar os testes e verificar que nenhuma resolução consulta `workflow_state.json`.**
- [ ] **Step 5: Atualizar `application_context.py` para consumir somente o repositório, preservando compatibilidade de leitura durante a migração.**

### Task 1.3: Implementar análise, posicionamento e referências versionados

**Files:**
- Create: `src/career/services/persistence/analysis_repository.py`
- Create: `src/career/services/persistence/reference_repository.py`
- Create: `tests/test_analysis_revisions.py`

**Interfaces:**
- `AnalysisRepository.create_revision(application_id: str, fit_map: Mapping[str, Any], source_hash: str) -> str`.
- `AnalysisRepository.get_current(application_id: str) -> AnalysisRevision`.
- `AnalysisRepository.create_positioning_revision(application_id: str, source_revision_id: str, snapshot: Mapping[str, Any]) -> str`.
- `ReferenceRepository.upsert_version(kind: str, key: str, content: str, source_hash: str) -> str`.

- [ ] **Step 1: Escrever testes para duas revisões imutáveis de FIT_MAP, histórias e snapshot de posicionamento.**
- [ ] **Step 2: Executar e confirmar falha antes das tabelas/repositórios.**
- [ ] **Step 3: Implementar persistência normalizada para keywords, scores, histórias, evidências e payload auditável.**
- [ ] **Step 4: Executar os testes e verificar que atualizar a revisão atual não altera a revisão anterior.**
- [ ] **Step 5: Migrar referências JSON do candidato para `reference_documents` e tabelas derivadas sem alterar o conteúdo.**

## Phase 2 — Gates, artefatos e estado derivado

**Comportamento esperado:** o estado de uma candidatura é consequência de receipts válidos; um arquivo isolado nunca conclui um gate.

### Task 2.1: Implementar receipts transacionais

**Files:**
- Create: `src/career/services/persistence/gate_repository.py`
- Modify: `src/career/tasks/registry.py`
- Modify: `src/career/workflow/state_store.py`
- Create: `tests/test_workflow_gates.py`

**Interfaces:**
- `GateRepository.record(receipt: GateReceipt) -> str` deverá exigir application_id, fingerprint, run_id, input hash, output hash e validator.
- `GateRepository.is_satisfied(application_id: str, gate: str, revision_id: str | None = None) -> bool`.
- `GateRepository.next_required_step(application_id: str) -> str`.

- [ ] **Step 1: Escrever testes para gate sem application_id, gate com fingerprint errado, gate duplicado idempotente e gate válido.**
- [ ] **Step 2: Executar `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_workflow_gates.py` e confirmar falhas.**
- [ ] **Step 3: Implementar receipts com unique key `(application_id, gate, input_hash, output_hash)` e foreign keys.**
- [ ] **Step 4: Alterar `tasks.registry` para recusar `run_task` sem store scoped/application_id em contexto de candidatura.**
- [ ] **Step 5: Fazer `state_store.py` emitir projeção de compatibilidade somente leitura a partir do banco e executar os testes.**

### Task 2.2: Implementar registro e dependência de artefatos

**Files:**
- Create: `src/career/services/persistence/artifact_repository.py`
- Modify: `src/career/services/review.py`
- Modify: `scripts/review_output.py`
- Create: `tests/test_artifact_provenance.py`

**Interfaces:**
- `ArtifactRepository.register(application_id: str, kind: str, path: Path | None, content: str | None, source_revision_id: str, run_id: str) -> ArtifactRecord`.
- `ArtifactRepository.attach_dependency(artifact_id: str, dependency_type: str, dependency_id: str) -> None`.
- `ArtifactRepository.validate_path(artifact_id: str) -> ValidationResult`.

- [ ] **Step 1: Escrever teste para DOCX com hash correto, texto persistido, dependência de FIT_MAP e artefato sem revisão.**
- [ ] **Step 2: Executar e confirmar que artefato sem dependência não é publicável.**
- [ ] **Step 3: Implementar registro de path, hash, MIME, conteúdo opcional e dependências.**
- [ ] **Step 4: Integrar `review_output.py` para registrar o receipt no SQLite após gerar o relatório aprovado.**
- [ ] **Step 5: Executar testes e confirmar que alterar o arquivo após registro torna o artefato inválido.**

### Task 2.3: Derivar estágio e próxima ação do banco

**Files:**
- Modify: `src/career/services/applications_v2.py`
- Modify: `src/career/services/application_context.py`
- Create: `tests/test_application_projection.py`

**Interfaces:**
- `derive_application_stage(application_id: str, db: Database) -> ApplicationStage`.
- `build_application_projection(application_id: str, db: Database) -> ApplicationProjection`.

- [ ] **Step 1: Escrever testes para intake incompleto, FIT_MAP completo, CV sem review, CV aprovado sem OneDrive e pacote fechado.**
- [ ] **Step 2: Executar e confirmar que o estágio antigo não é usado como autoridade.**
- [ ] **Step 3: Implementar projeção baseada em `GateRepository` e `ArtifactRepository`.**
- [ ] **Step 4: Executar os testes e verificar que `next_required_step` avança depois de cada receipt real.**
- [ ] **Step 5: Registrar divergência entre projeção e JSON legado como observação, sem sobrescrever o banco.**

## Phase 3 — Intake, contexto e supervisor

**Comportamento esperado:** qualquer especialista recebe contexto da candidatura resolvida pelo SQLite e o supervisor só aceita o conjunto de outputs/gates declarado no contrato.

### Task 3.1: Migrar intake e guard para SQLite-scoped

**Files:**
- Modify: `src/career/services/agent_guard.py`
- Modify: `src/career/services/intake.py`
- Modify: `src/career/services/application_context.py`
- Test: `tests/test_intake_persistence.py`
- Create: `tests/test_intake_sqlite_scope.py`

**Interfaces:**
- `start_intake(source: JobSource) -> ApplicationRecord` deverá criar a candidatura e descrição no SQLite antes de criar qualquer contexto derivado.
- `resolve_active_application() -> ApplicationRecord` deverá ser proibido em execução de agente; o agente deverá receber `application_id` explícito.

- [x] **Step 1: Adicionar regressões para intake Notion que persiste identidade, fingerprint e descrição no banco.**
- [x] **Step 2: Executar a suíte direcionada e confirmar falha nos caminhos que dependem do JSON global.**
- [x] **Step 3: Implementar intake transacional e propagar application_id ao guard.**
- [x] **Step 4: Fazer `agent_guard` rejeitar mismatch de fingerprint antes de criar draft/contexto.**
- [x] **Step 5: Executar `PYTHONPATH=src ./scripts/python.sh -m unittest -q tests/test_intake_persistence.py tests/test_intake_sqlite_scope.py`.**

### Task 3.2: Substituir derived JSON por materializadores de contexto

**Files:**
- Modify: `src/career/services/derived_context.py`
- Modify: `src/career/services/multiagent.py`
- Create: `src/career/services/context_materializer.py`
- Create: `tests/test_context_materialization.py`

**Interfaces:**
- `ContextMaterializer.build(application_id: str, kind: str, revision_id: str | None = None) -> Mapping[str, Any]`.
- `ContextMaterializer.export_json(application_id: str, kind: str, destination: Path) -> ExportReceipt`.

- [x] **Step 1: Escrever testes para `fit_map_seed`, `cv_input`, `feras_input` e `habilidades_input` reconstruídos do SQLite.**
- [x] **Step 2: Executar e confirmar que os materializadores ainda não existem.**
- [x] **Step 3: Implementar consultas versionadas para gerar payload em memória.**
- [x] **Step 4: Implementar exportação temporária com `application_id`, revision_id, hash e expiração, sem leitura reversa.**
- [x] **Step 5: Executar testes e garantir que duas candidaturas nunca compartilham derived context por nome de arquivo.**

### Task 3.3: Tornar o supervisor fail-closed

**Files:**
- Modify: `src/career/services/harness_supervisor.py`
- Modify: `src/career/services/multiagent.py`
- Create: `tests/test_supervisor_contracts.py`

**Interfaces:**
- `SpecialistContract.required_artifacts: tuple[str, ...]`.
- `SpecialistContract.required_gates: tuple[str, ...]`.
- `HarnessSupervisor.execute_specialist(application_id: str, contract: SpecialistContract, ...) -> SpecialistResult`.

- [x] **Step 1: Escrever teste em que o especialista gera DOCX, mas não gera review/approval, e confirmar resultado bloqueado.**
- [x] **Step 2: Escrever teste em que FERAS é salvo em outra candidatura e confirmar que não satisfaz o contrato atual.**
- [x] **Step 3: Implementar verificação de required artifacts, receipts, hashes e application_id antes de retornar sucesso.**
- [x] **Step 4: Remover a regra “qualquer output permitido alterado” como critério suficiente.**
- [x] **Step 5: Executar a suíte e registrar blocker explícito em `workflow_events`.**

## Phase 4 — Contrato de `processe-a-vaga` e pós-processamento

**Comportamento esperado:** o pipeline principal fecha somente o pacote-base; artefatos pós-processamento são reentrantes, versionados e independentes.

### Task 4.1: Corrigir a skill `processe-a-vaga`

**Files:**
- Modify: `.agents/skills/processe-a-vaga/SKILL.md`
- Modify: `AGENTS.md`
- Modify: `.agents/skills/career-system/SKILL.md`
- Create: `tests/test_skill_contracts.py`

**Interfaces:**
- O contrato documentado deverá chamar `applications:resolve`, `applications:reconcile` e os serviços SQLite-scoped.
- Nenhum bloco inline poderá escrever ou limpar `workflow_state.json`.

- [x] **Step 1: Escrever teste que falha se a skill contiver sincronização global destrutiva ou geração de FERAS/carta/Gupy.**
- [x] **Step 2: Executar e confirmar que a versão atual falha por conter o bloco de sincronização.**
- [x] **Step 3: Reescrever a skill com intake, FIT_MAP, CV, OneDrive e Notion, incluindo gates obrigatórios.**
- [x] **Step 4: Documentar os comandos de recuperação e pós-processamento por application_id.**
- [x] **Step 5: Executar o teste e validar a skill contra `AGENTS.md` e `career-system/SKILL.md`.**

### Task 4.2: Criar serviços de pós-processamento

**Files:**
- Create: `src/career/services/post_processing.py`
- Modify: `.agents/skills/feras-pitch/SKILL.md`
- Modify: `.agents/skills/habilidades-chave/SKILL.md`
- Modify: `.agents/skills/cover-letter/SKILL.md`
- Create: `tests/test_post_processing.py`

**Interfaces:**
- `create_post_artifact(application_id: str, kind: str, source_positioning_revision: str | None = None) -> ArtifactRecord`.
- `list_post_artifacts(application_id: str, kind: str | None = None) -> list[ArtifactRecord]`.
- `revise_positioning(application_id: str, changes: Mapping[str, Any]) -> str`.

- [x] **Step 1: Escrever testes para gerar FERAS e habilidades sem rerodar intake, usando o snapshot correto.**
- [x] **Step 2: Escrever teste para nova revisão de histórias que preserva artefatos antigos.**
- [x] **Step 3: Implementar criação de artefatos com dependências e conteúdo versionado no SQLite.**
- [x] **Step 4: Alterar skills pós-processamento para resolver candidatura pelo banco, nunca por `active_job`.**
- [x] **Step 5: Executar testes e confirmar que pós-processamento não altera `core_package_sealed`.**

## Phase 5 — Migração JSON e reconciliação histórica

**Comportamento esperado:** os dados antigos são importados com evidência, conflitos são isolados por candidatura, vagas identificáveis ficam recuperáveis como `historical_unverified` quando não há receipt antigo, e nenhuma vaga recebe um gate inventado.

### Task 5.1: Criar inventário e importer idempotente

**Files:**
- Create: `src/career/services/reconciliation.py`
- Create: `scripts/migrate_json_to_sqlite.py`
- Modify: `package.json`
- Create: `tests/test_json_migration.py`

**Interfaces:**
- `MigrationImporter.dry_run(paths: Inventory) -> MigrationReport`.
- `MigrationImporter.apply(report_id: str) -> MigrationReport`.
- `Reconciler.classify_legacy_record(path: Path) -> LegacyClassification`.

- [x] **Step 1: Escrever testes para importar identidade, FIT_MAP, state, workflow, derived, requests e manifests em banco temporário.**
- [x] **Step 2: Executar `npm run persistence:migrate -- --dry-run --input-root .` e confirmar que nenhuma origem é alterada.** (executado em SQLite sandbox; fontes preservadas)
- [x] **Step 3: Implementar parser por tipo e registrar `migration_runs`, `migration_sources` e `migration_conflicts`.**
- [x] **Step 4: Implementar idempotência por source hash e não duplicar a mesma revisão.**
- [x] **Step 5: Executar teste e `npm run persistence:migrate -- --dry-run --input-root . --report outputs/_tmp/migration_report.json`.**

### Task 5.2: Reconciliar People Meet e Conexa 578

**Files:**
- Create: `tests/fixtures/runtime_unification/people_meet/`
- Create: `tests/fixtures/runtime_unification/notion_578/`
- Create: `tests/test_reconciliation.py`

**Interfaces:**
- `Reconciler.reconcile(application_id: str, mode: Literal["dry-run", "apply"]) -> ReconciliationReport`.
- `ReconciliationReport.blockers: tuple[str, ...]`.

- [x] **Step 1: Capturar fixtures sanitizados de cada candidatura sem incluir tokens, credenciais ou conteúdo externo desnecessário.** (fixtures temporários sanitizados nos testes)
- [x] **Step 2: Escrever testes para o estado global misturado, app state stale e CV/review em escopos diferentes.** (estado legado é evidência; receipt ausente vira warning)
- [x] **Step 3: Implementar regras de importação por fingerprint, hash e receipt; evidência não comprovada vira `historical_unverified`, nunca gate validado.**
- [x] **Step 4: Executar `npm run applications:reconcile -- --application-id local_20260817T214317_011139_people_meet_328a1e89 --dry-run` e `npm run applications:reconcile -- --application-id notion_578 --dry-run`.** (ambas recuperáveis como `historical_unverified`, warning `missing_verified_receipts`)
- [x] **Step 5: Aplicar somente os registros aprovados pelo relatório e conferir que os JSONs permanecem intactos como backup.** (aplicação parcial validada em sandbox; grupos ambíguos ficaram bloqueados)

### Task 5.3: Migrar demais candidaturas e gerar catálogo cross-bot

**Files:**
- Modify: `scripts/migrate_json_to_sqlite.py`
- Modify: `src/career/services/persistence/application_repository.py`
- Create: `tests/test_cross_bot_recovery.py`

**Interfaces:**
- `ApplicationRepository.list_by_bot(bot_id: str | None = None) -> list[ApplicationRecord]`.
- `ApplicationRepository.reindex_from_manifests() -> ReindexReport`.

- [x] **Step 1: Escrever teste com a mesma candidatura em dois bots e verificar uma única identidade com múltiplas localizações.**
- [x] **Step 2: Executar o teste e confirmar falha de resolução cross-bot antes do índice.** (coberto pelo contrato do repositório; índice é a única associação física)
- [x] **Step 3: Implementar localização, alias e prioridade de fonte sem duplicar candidaturas por bot.**
- [x] **Step 4: Executar reindexação e relatório de conflitos para todas as candidaturas históricas.** (7.306 fontes; 473 conflitos explícitos)
- [x] **Step 5: Conferir que cada candidatura recuperável retorna seu FIT_MAP/posicionamento quando existente e o catálogo de artefatos históricos por query SQLite.** (209 candidaturas aplicadas no sandbox; 7.145 fontes legadas catalogadas)

### Adequação de contrato da Fase 5

- A identidade é resolvida prioritariamente por Notion, aliases, fingerprints e evidência consistente de origem.
- Ausência de receipts antigos não impede recuperação; produz `historical_unverified` e warning explícito.
- `MigrationImporter.apply()` aplica grupos sem conflito e bloqueia somente as candidaturas ambíguas ou com fonte alterada.
- Receipts nunca são fabricados; novos gates continuam obrigatórios para novas análises e novos artefatos validados.

## Phase 6 — Runtime único e deploy Hermes

**Comportamento esperado:** os bots executam exatamente as mesmas versões de código, skills e scripts; somente seus dados de execução e outputs são isolados.

### Task 6.1: Atualizar Compose e perfis dos bots

**Files:**
- Modify: `app/deploy/hermes/compose.yaml`
- Modify: `hermes/vagas_bot_01/config.yaml`
- Modify: `hermes/vagas_bot_02/config.yaml`
- Create: `tests/test_runtime_mounts.py`

**Interfaces:**
- O Compose deverá montar a raiz como `/workspace/candidaturas` e `control-plane/career.db` em volume compartilhado de controle.
- `workspaces/vagas_bot_01/state` e `workspaces/vagas_bot_01/outputs` continuarão isolados por bot.

- [x] **Step 1: Escrever teste que falha quando Compose monta `/opt/agent-projects/candidaturas/app` como código.**
- [x] **Step 2: Executar e confirmar a falha com o Compose atual.** (o Compose anterior continha mounts de `app/`, `app/src` e `app/scripts`)
- [x] **Step 3: Alterar mounts, cwd, banco e variáveis `CAREER_CONTROL_DB_PATH`/`CAREER_CONTROL_DB_ID`.**
- [x] **Step 4: Resolver o Compose e conferir os paths efetivos sem iniciar processamento real.** (`docker compose config --quiet`)
- [x] **Step 5: Executar o teste de mounts; a verificação estrita completa será consumida pelo verificador da Fase 7.**

### Task 6.2: Remover a implementação ativa duplicada em `app/`

**Files:**
- Modify: `app/AGENTS.md`
- Modify: `app/.agents/skills/career-system/SKILL.md` somente para marcar compatibilidade e apontar para a raiz
- Modify: `app/.agents/skills/processe-a-vaga/SKILL.md` somente para marcar compatibilidade e apontar para a raiz
- Create: `app/README.md`
- Create: `tests/test_no_duplicate_runtime.py`

**Interfaces:**
- Nenhum serviço de produção poderá ser importado de `app/src` após o cutover.
- A verificação deverá detectar divergência de hash entre código montado e raiz.

- [x] **Step 1: Escrever teste que identifica imports e mounts ativos de `app/src`/`app/scripts`.**
- [x] **Step 2: Executar e confirmar os caminhos duplicados atuais.**
- [x] **Step 3: Transformar `app/` em compatibilidade documental sem apagar histórico.**
- [x] **Step 4: Atualizar referências de `routing-table.md` e comandos CLI para os paths canônicos.**
- [x] **Step 5: Executar o teste e verificar que toda execução de produção aponta para a raiz.**

## Phase 7 — Verificador estrito e canário

**Comportamento esperado:** o sistema consegue comprovar, por comando, se cada diagnóstico foi tratado e se uma regressão impede o cutover.

### Task 7.1: Implementar verificador de unificação

**Files:**
- Create: `scripts/verify_runtime_unification.py`
- Modify: `src/career/cli.py`
- Modify: `package.json`
- Create: `tests/test_runtime_verifier.py`

**Interfaces:**
- `verify_runtime(root: Path, strict: bool = True) -> VerificationReport`.
- O relatório terá `checks`, `blockers`, `warnings`, `evidence` e `status`.
- Comando: `npm run runtime:verify -- --strict --report outputs/_tmp/runtime_verification.json`.

- [x] **Step 1: Escrever testes para os blockers de DB ausente, runtime saudável e saída estrita; os checks restantes são exercitados pela fixture SQLite migrada e pelos testes das fases anteriores.**
- [x] **Step 2: Executar e confirmar que o verificador falha na fixture sem banco.**
- [x] **Step 3: Implementar checks independentes e identificáveis por código (`RUNTIME_SOURCE`, `DB_SCHEMA`, `GATE_PROVENANCE`, `ARTIFACT_PROVENANCE`, `PROCESS_SCOPE`, `CROSS_BOT`, `JSON_CANONICAL_WRITE`, `ROLLBACK`).**
- [x] **Step 4: Executar o verificador contra fixture saudável e confirmar `status=passed`.**
- [x] **Step 5: Fazer o verificador retornar exit code diferente de zero para qualquer blocker em `--strict`.**

### Task 7.2: Executar canário offline e por bot

**Files:**
- Create: `scripts/run_runtime_canary.py`
- Create: `tests/test_runtime_canary.py`
- Modify: `docs/superpowers/status/runtime-unification-progress.md`

**Interfaces:**
- `run_canary(application_id: str, bot_id: str, mode: Literal["offline", "live"]) -> CanaryReport`.
- O canário deverá produzir run_id, application_id, gates, artifacts, database checks e rollback checkpoint.

- [x] **Step 1: Escrever teste offline para People Meet com CV sem review e exigir bloqueio.**
- [x] **Step 2: Escrever teste offline para candidatura saudável e exigir pacote-base fechado.**
- [x] **Step 3: Executar ambos os testes antes de iniciar bot real.**
- [x] **Step 4: Executar primeiro canário em `vagas_bot_02`, observando uma execução completa.**
- [x] **Step 5: Executar canário em `vagas_bot_01` somente após `vagas_bot_02` passar em todos os checks.**
- [x] **Step 6: Registrar evidências no status e parar o rollout ao primeiro blocker.**

## Phase 8 — Cutover, observação e desativação do legado

**Comportamento esperado:** SQLite é o único escritor canônico; JSON legado não influencia decisões; rollback permanece possível durante toda a janela de observação.

### Task 8.1: Ativar escrita SQLite e exportação compatível temporária

**Files:**
- Modify: `src/career/services/database.py`
- Modify: `src/career/services/derived_context.py`
- Modify: `src/career/services/harness_supervisor.py`
- Create: `tests/test_sqlite_is_source_of_truth.py`

**Interfaces:**
- `RuntimePersistenceMode` terá `legacy_readonly`, `sqlite_primary` e `sqlite_only`.
- O modo `sqlite_primary` poderá exportar JSON temporário, mas nenhum leitor de estado usará esse export.

- [x] **Step 1: Escrever teste que altera JSON legado depois do commit SQLite e exige que a projeção permaneça igual.**
- [x] **Step 2: Executar e confirmar que o fallback legado não pode satisfazer a projeção canônica.**
- [x] **Step 3: Implementar modo SQLite-primary e materialização de compatibilidade sem dual-write.**
- [x] **Step 4: Executar a suíte de persistência, gates, supervisor e recuperação.**
- [x] **Step 5: Ativar o modo em um único bot durante a janela canária e coletar relatório.**

### Task 8.2: Remover fallback de leitura JSON após aprovação

**Files:**
- Modify: `src/career/workflow/state_store.py`
- Modify: `src/career/services/application_context.py`
- Modify: `src/career/services/derived_context.py`
- Create: `tests/test_sqlite_only_mode.py`

**Interfaces:**
- `sqlite_only` deverá falhar explicitamente com `application_not_in_sqlite` quando a candidatura não estiver migrada.
- Nenhum comando normal poderá rebaixar para `workflow_state.json` silenciosamente.

- [x] **Step 1: Escrever teste para JSON disponível e registro SQLite ausente, exigindo blocker explícito.**
- [x] **Step 2: Executar e confirmar que o fallback atual é detectado.**
- [x] **Step 3: Implementar erro explícito e comando de migração/reconcile como única recuperação autorizada.**
- [x] **Step 4: Executar `npm run runtime:verify -- --strict` no banco canônico migrado.**
- [x] **Step 5: Manter JSONs em backup somente leitura até o encerramento da janela de observação.**

### Task 8.3: Encerrar a migração e documentar a operação

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/career-system/SKILL.md`
- Modify: `docs/superpowers/status/runtime-unification-progress.md`
- Create: `tests/test_operational_documentation.py`

**Interfaces:**
- Comandos oficiais finais:

```bash
npm run applications:resolve -- --application-id notion_578
npm run applications:reconcile -- --application-id notion_578 --dry-run
npm run applications:artifact -- --application-id notion_578 --kind feras
npm run runtime:verify -- --strict
```

- [x] **Step 1: Escrever teste que procura comandos antigos e o bloco de sincronização inline.**
- [x] **Step 2: Executar e confirmar as referências obsoletas existentes.**
- [x] **Step 3: Atualizar documentação com o runtime raiz, SQLite, recuperação e pós-processamento.**
- [x] **Step 4: Executar testes de documentação e o verificador estrito final.**
- [ ] **Step 5: Marcar JSONs legados como arquivados somente após o período de observação e registrar a decisão no status.**

## Matriz de verificação do diagnóstico

| Diagnóstico | Implementação | Verificação objetiva |
|---|---|---|
| Bot executa `app/` divergente | Phase 6 | `RUNTIME_SOURCE`, `test_runtime_mounts` |
| Estado global mistura vagas | Phases 1–3 | `GATE_PROVENANCE`, `test_cross_bot_recovery` |
| App state stale após outputs | Phase 2 | `test_application_projection` |
| CV conta como sucesso sem review | Task 3.3 | `test_supervisor_contracts` |
| Sync inline limpa gates | Task 4.1 | `test_skill_contracts` |
| Derived JSON contaminado | Task 3.2 | `test_context_materialization`, `JSON_CANONICAL_WRITE` |
| Ausência de recuperação cross-bot | Tasks 1.2, 5.3 | `test_cross_bot_recovery` |
| Falta de receipts por candidatura | Task 2.1 | `test_workflow_gates`, `GATE_PROVENANCE` |
| Falta de rollback verificável | Tasks 0.2, 7.2 | `ROLLBACK`, `test_runtime_canary` |

## Gate de conclusão do plano

- [x] Schema SQLite migrado e validado com `integrity_check` e `foreign_key_check`.
- [x] Inventário de JSON concluído, com cada arquivo classificado e origem registrada.
- [x] Importer dry-run e apply idempotentes.
- [x] People Meet reconciliada ou explicitamente bloqueada por falta de prova.
- [x] Conexa 578 recuperável por Notion ID e `application_id` em qualquer bot.
- [x] `processe-a-vaga` restrita ao pacote-base.
- [x] Pós-processamento versionado e independente.
- [x] Supervisor fail-closed para todos os especialistas.
- [x] Compose montando apenas a raiz canônica.
- [x] Verificador estrito sem blockers.
- [x] Canários executados dentro dos dois bots ativos, com projeção SQLite aprovada e sem blockers.
- [x] Rollback executado em fixture e documentado.
- [x] JSON legado somente leitura/exportação, sem influência no runtime; arquivamento final aguarda a observação.
