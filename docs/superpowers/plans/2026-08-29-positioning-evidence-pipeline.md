# Positioning Evidence Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que evidências completas do candidato sejam versionadas e que a estratégia de reposicionamento de cada candidatura seja traduzida de modo rastreável para CV, FERAS, carta, habilidades e respostas.

**Architecture:** Aproveitar a persistência existente em `reference_documents`, `candidate_facts`, `candidate_evidence`, `fit_map_revisions` e `positioning_revisions`. Introduzir uma fonte estruturada completa de evidências, derivar `candidate_cv_facts.json` dela por compatibilidade e materializar um pacote de posicionamento scoped que todos os especialistas consumam. O Notion continuará recebendo apenas o snapshot estratégico já suportado pelos campos existentes.

**Tech Stack:** Python 3, SQLite, dataclasses/typing já usados no projeto, JSON versionado, pytest, comandos npm canônicos e validações existentes de FIT_MAP/CV/artifacts.

**Spec:** `docs/positioning-evidence-spec.md`

## Global Constraints

- SQLite permanece como autoridade operacional; JSON local e Notion são projeções ou fontes canônicas explicitamente declaradas.
- Toda candidatura deve ser resolvida por `application_id`; nenhum ponteiro global pode selecionar execução.
- Toda história/claim deve preservar `source_refs` e não pode criar métricas ou escopos novos.
- FIT_MAP, revisão de posicionamento e artefatos devem manter hashes/revisões e proveniência.
- Não alterar o schema do Notion na primeira versão; usar `Decisões narrativas`, `Persona / Ângulo narrativo`, `Experiências priorizadas`, `Feedback humano` e os campos ATS atuais.
- Manter compatibilidade com o formato atual de `candidate_cv_facts.json` e com os packs existentes durante a migração.
- Cada tarefa deve seguir RED → GREEN → suíte focada e preservar alterações pré-existentes do worktree.

---

### Task 1: Fixar o contrato de evidências e a revisão canônica

**Roadmap:** `POSITION-001`

**Files:**
- Create: `.agents/skills/career-system/references/candidate_evidence.json`
- Create: `src/career/schemas/candidate_evidence.py`
- Modify: `src/career/services/provenance.py`
- Modify: `src/career/services/persistence/reference_repository.py`
- Test: `tests/test_candidate_evidence.py`
- Test: `tests/test_fit_map_provenance.py`

**Interfaces:**
- `validate_candidate_evidence(payload: Mapping[str, Any]) -> dict[str, Any]`
- `candidate_evidence_revision(sources: Iterable[Path] | None = None) -> str`
- `ReferenceRepository.upsert_version(kind="candidate_evidence", key="candidate", content, source_hash)`
- O registro de cada história deve aceitar `story_id`, `source_refs`, `allowed_claims`, `capabilities`, `metrics` e `artifact_guidance`.

- [x] **Step 1: Escrever testes RED para o contrato.**

  Cobrir história válida, `story_id` duplicado, história sem `source_refs`, claim sem texto e métrica não textual. O teste deve afirmar que o payload válido retorna o mesmo objeto normalizado e que cada inválido produz `ValidationFailure` com o caminho do campo.

- [x] **Step 2: Executar os testes para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_candidate_evidence.py`

  Expected: FAIL porque o schema e a referência estruturada ainda não existem.

- [x] **Step 3: Implementar o schema e cadastrar a primeira versão.**

  Usar `Mapping`/`Sequence`, rejeitar placeholders, exigir `source_refs.path` e `source_refs.lines`, e manter campos livres somente dentro de `payload`. O conteúdo inicial deve representar as histórias já presentes em `candidate_cv_facts.json` e apontar para linhas reais do `autoconhecimento.md`; não inventar histórias durante a migração.

- [x] **Step 4: Incluir a nova fonte na revisão de candidato.**

  Atualizar `provenance.candidate_facts_revision()` para incluir `candidate_evidence.json`, preservando as fontes atuais. Registrar a referência no SQLite pela mesma rotina usada para `candidate_cv_facts` e estender o parser de `ReferenceRepository` para indexar stories, claims e evidence.

- [x] **Step 5: Executar GREEN e regressões de proveniência.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_candidate_evidence.py tests/test_fit_map_provenance.py tests/test_analysis_revisions.py`

  Expected: PASS; a revisão muda quando o arquivo de evidências muda e FIT_MAPs antigos continuam identificando a revisão que consumiram.

- [x] **Step 6: Commitar a unidade.**

  Run: `git add .agents/skills/career-system/references/candidate_evidence.json src/career/schemas/candidate_evidence.py src/career/services/provenance.py src/career/services/persistence/reference_repository.py tests/test_candidate_evidence.py tests/test_fit_map_provenance.py && git commit -m "feat: version candidate evidence separately from cv facts"`

### Task 2: Derivar `candidate_cv_facts.json` e enriquecer a indexação

**Roadmap:** `POSITION-001`

**Files:**
- Create: `src/career/services/candidate_evidence.py`
- Create: `scripts/rebuild_candidate_facts.py`
- Modify: `src/career/services/cv_content.py`
- Modify: `src/career/services/persistence/reference_repository.py`
- Modify: `package.json`
- Test: `tests/test_candidate_cv_facts.py`
- Create: `tests/test_reference_repository.py`

**Interfaces:**
- `load_candidate_evidence(path: Path | None = None) -> dict[str, Any]`
- `build_cv_facts_view(evidence: Mapping[str, Any]) -> dict[str, Any]`
- `rebuild_candidate_facts() -> dict[str, Path]`
- O view gerado deve manter `experiences`, `education`, `languages`, `summary_profiles`, `summary_fragments`, `experience_locators` e `selectors` existentes.

- [x] **Step 1: Escrever teste RED para a view.**

  Inserir uma história nova no fixture de evidências, executar `build_cv_facts_view`, e afirmar que a experiência correspondente aparece na visão CV sem alterar as demais experiências. Também afirmar que `source_refs` permanece acessível no payload de evidências.

- [x] **Step 2: Executar o teste para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_candidate_cv_facts.py::test_new_evidence_story_is_available_to_cv_view`

  Expected: FAIL porque a view ainda não é derivada da base de evidências.

- [x] **Step 3: Implementar a derivação compatível.**

  Centralizar a leitura em `candidate_evidence.py`; gerar o formato atual de CV a partir de stories/facts e preservar o arquivo canônico existente como fixture de compatibilidade durante a transição. O gerador não deve usar texto bruto desconhecido sem passar pelo schema.

- [x] **Step 4: Expor comando de reconstrução.**

  Adicionar `candidate-facts:rebuild` ao `package.json`, chamando o script via `scripts/python.sh`. O comando deve validar o payload, escrever uma cópia com JSON determinístico e retornar revisão/hash e paths sem imprimir o conteúdo completo.

- [x] **Step 5: Executar GREEN e regressões do CV.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_candidate_cv_facts.py tests/test_reference_repository.py tests/test_cv_experience_selection.py`

  Expected: PASS; a seleção continua compatível e uma história nova fica disponível para seleção sem fallback fixo.

- [x] **Step 6: Commitar a unidade.**

  Run: `git add src/career/services/candidate_evidence.py scripts/rebuild_candidate_facts.py src/career/services/cv_content.py src/career/services/persistence/reference_repository.py package.json tests/test_candidate_cv_facts.py tests/test_reference_repository.py && git commit -m "feat: derive cv facts from candidate evidence"`

### Task 3: Construir o pacote de posicionamento scoped

**Roadmap:** `POSITION-002`

**Files:**
- Create: `src/career/services/positioning_pack.py`
- Modify: `src/career/services/persistence/analysis_repository.py`
- Modify: `src/career/services/context_materializer.py`
- Modify: `src/career/services/packs/feras_input_pack.py`
- Modify: `src/career/services/packs/cover_letter_pack.py`
- Modify: `src/career/services/packs/habilidades_pack.py`
- Test: `tests/test_positioning_pack.py`
- Test: `tests/test_context_materialization.py`

**Interfaces:**
- `build_positioning_pack(application_id: str, database: Database, positioning_revision_id: str | None = None) -> dict[str, Any]`
- `validate_positioning_pack(payload: Mapping[str, Any]) -> dict[str, Any]`
- Pacote obrigatório: `application_id`, `fit_map_revision_id`, `positioning_revision_id`, `candidate_evidence_revision_id`, `thesis`, `persona`, `stories`, `claims`, `keywords`, `gaps`, `artifact_targets`.

- [x] **Step 1: Escrever teste RED de isolamento e rastreabilidade.**

  Criar duas candidaturas SQLite com FIT_MAPs e revisões de posicionamento diferentes; afirmar que cada pacote retorna somente suas histórias, carrega os IDs de revisão corretos e rejeita uma história sem `source_refs`.

- [x] **Step 2: Executar para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_pack.py`

  Expected: FAIL porque o builder e o contrato do pacote ainda não existem.

- [x] **Step 3: Implementar usando `PositioningRevision` existente.**

  Resolver a candidatura e o FIT_MAP pelo `ApplicationRepository`/`AnalysisRepository`; combinar as histórias selecionadas com a base de evidências versionada; persistir a revisão por `create_positioning_revision` quando necessário; não consultar `active_job`, JSON global ou Notion.

- [x] **Step 4: Fazer os packs existentes carregarem o pacote.**

  Adicionar `positioning_pack` ou seu identificador/hash aos contextos `cv_input`, `feras_input`, `cover_letter_input` e `habilidades_input`. Manter os campos antigos (`selected_stories`, `keywords_para_ats`, `gaps_sem_cobertura`) para compatibilidade.

- [x] **Step 5: Executar GREEN e a suíte de materialização.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_pack.py tests/test_context_materialization.py tests/test_analysis_revisions.py tests/test_artifact_provenance.py`

  Expected: PASS; cada pack é scoped e carrega a mesma revisão de posicionamento.

- [x] **Step 6: Commitar a unidade.**

  Run: `git add src/career/services/positioning_pack.py src/career/services/persistence/analysis_repository.py src/career/services/context_materializer.py src/career/services/packs tests/test_positioning_pack.py tests/test_context_materialization.py && git commit -m "feat: materialize scoped positioning pack"`

### Task 4: Adaptar artefatos à estratégia compartilhada

**Roadmap:** `POSITION-002`

**Files:**
- Modify: `src/career/services/cv_content.py`
- Modify: `src/career/services/feras.py`
- Modify: `src/career/services/cover_letter.py`
- Modify: `src/career/services/habilidades_chave.py`
- Modify: `src/career/services/post_processing.py`
- Modify: `src/career/services/persistence/artifact_repository.py`
- Test: `tests/test_positioning_artifacts.py`
- Test: `tests/test_cv_positioning.py`

**Interfaces:**
- Cada builder deve aceitar o pacote via `build_from_positioning_pack(pack: Mapping[str, Any], ...)` ou adaptar internamente a mesma interface; não deve reconstruir estratégia a partir de texto livre.
- Cada artifact receipt deve manter `application_id`, `source_revision_id` e `positioning_revision_id`; a revisão de evidências será anexada pela tabela existente `artifact_version_dependencies` como `candidate_evidence_reference`, junto de `story_ids` e `claim_ids` no payload do artefato.

- [x] **Step 1: Escrever testes RED por formato.**

  Usar uma história fixture com claim permitido e assertar que CV, FERAS, carta e habilidades produzem conteúdo do mesmo `story_id`, com redações específicas de cada formato. Assertar que um claim não permitido não aparece.

- [x] **Step 2: Executar para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_artifacts.py`

  Expected: FAIL porque os builders atuais consomem FIT_MAP/fields legados sem registrar cobertura de stories/claims.

- [x] **Step 3: Implementar os adaptadores sem alterar regras ATS.**

  CV continua sujeito à materialização factual e aos gates existentes; FERAS/carta/habilidades reutilizam o pacote e produzem narrativa adequada ao formato. Nenhum adaptador pode transformar reposicionamento em cobertura direta de keyword sem evidência.

- [x] **Step 4: Registrar dependências nos receipts.**

  Estender `ArtifactRepository` para aceitar a dependência existente `candidate_evidence_reference`, validá-la contra `reference_documents` e anexá-la junto de `fit_map_revision` e `positioning_revision`. `post_processing` deve encaminhar a revisão de posicionamento efetivamente utilizada; a revisão de evidências deve ser resolvida a partir desse snapshot, sem adicionar uma coluna duplicada a `artifact_versions`.

- [x] **Step 5: Executar GREEN e suíte dos artefatos.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_artifacts.py tests/test_cv_positioning.py tests/test_artifact_provenance.py tests/test_cv_delivery_scope.py`

  Expected: PASS; outputs usam o mesmo posicionamento e permanecem entregáveis somente com os gates atuais aprovados.

- [x] **Step 6: Commitar a unidade.**

  Run: `git add src/career/services/cv_content.py src/career/services/feras.py src/career/services/cover_letter.py src/career/services/habilidades_chave.py src/career/services/post_processing.py src/career/services/persistence/artifact_repository.py tests/test_positioning_artifacts.py tests/test_cv_positioning.py && git commit -m "feat: translate positioning across application artifacts"`

### Task 5: Adicionar cobertura estratégica e invalidação

**Roadmap:** `POSITION-003`

**Files:**
- Create: `src/career/services/positioning_coverage.py`
- Modify: `src/career/services/persistence/artifact_repository.py`
- Modify: `src/career/services/context_materializer.py`
- Modify: `src/career/services/provenance.py`
- Modify: `src/career/services/workflow_reset.py`
- Test: `tests/test_positioning_coverage.py`
- Test: `tests/test_artifact_provenance.py`

**Interfaces:**
- `evaluate_positioning_coverage(pack: Mapping[str, Any], artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]`
- Resultado: `covered`, `uncovered`, `unsupported_claims`, `stale_dependencies`, `approved`.
- `artifact_repository` deve devolver motivo explícito quando a revisão de evidências/posicionamento não corresponde ao artefato.

- [x] **Step 1: Escrever teste RED do gate.**

  Criar um pacote com duas stories, registrar um CV cobrindo uma e FERAS cobrindo as duas; afirmar que o resultado identifica a story ausente no CV. Alterar a revisão de evidências e afirmar `stale_dependencies` no artefato antigo.

- [x] **Step 2: Executar para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_coverage.py`

  Expected: FAIL porque não existe cálculo de cobertura estratégica nem dependência explícita da revisão de evidências.

- [x] **Step 3: Implementar o gate.**

  Comparar IDs, não similaridade textual; claims sem evidência são blockers; estratégia opcional não usada em determinado formato permanece `not_required`, não `missing`. Reutilizar o padrão de blockers/receipts já usado pelo reviewer de CV.

- [x] **Step 4: Integrar a invalidação aos builders e receipts.**

  Resolver `candidate_evidence_revision_id/hash` pela dependência `candidate_evidence_reference` e pelo snapshot de posicionamento; bloquear aprovação de artefato stale. Não apagar artefatos históricos; marcar incompatibilidade e exigir regeneração.

- [x] **Step 5: Executar GREEN e a suíte completa da frente.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_positioning_coverage.py tests/test_artifact_provenance.py tests/test_context_materialization.py tests/test_candidate_cv_facts.py tests/test_cv_experience_selection.py`

  Expected: PASS; alterações nas fontes não são silenciosamente reutilizadas.

- [x] **Step 6: Commitar a unidade.**

  Run: `git add src/career/services/positioning_coverage.py src/career/services/persistence/artifact_repository.py src/career/services/context_materializer.py src/career/services/provenance.py src/career/services/workflow_reset.py tests/test_positioning_coverage.py tests/test_artifact_provenance.py && git commit -m "feat: gate positioning coverage and stale artifacts"`

### Task 6: Sincronizar o snapshot final com Notion e validar end-to-end

**Roadmap:** `POSITION-003`

**Files:**
- Modify: `scripts/notion_sync.py`
- Modify: `.agents/skills/notion-transactions/SKILL.md`
- Modify: `docs/roadmap.md`
- Create: `tests/test_notion_sync.py`
- Test: `tests/test_phase3_integration_e2e.py`

**Interfaces:**
- O payload existente de governança continua preenchendo `narrative_decisions`, `persona_angle`, `prioritized_experiences`, `top8_keywords`, `covered_keywords`, `declared_gap_keywords`, `review_status` e `final_artifact`.
- A sincronização pode incluir no corpo uma seção compacta `Memória complementar` com revisão/IDs dos artefatos, mas não exige propriedade nova no database.

- [x] **Step 1: Escrever teste RED de projeção.**

  Dar ao `notion_sync` um FIT_MAP/positioning pack com tese, stories e cobertura; afirmar que o payload mantém os campos atuais e inclui somente um resumo legível, sem enviar o JSON completo de evidências.

- [x] **Step 2: Executar para confirmar a falha.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_notion_sync.py`

  Expected: FAIL apenas se o resumo de revisão ainda não estiver projetado; os campos atuais devem continuar passando.

- [x] **Step 3: Implementar a projeção sem mudar a autoridade.**

  Derivar o payload a partir do estado final scoped; manter dry-run obrigatório e nenhuma elevação automática de `Etapa Funil`. Não sincronizar histórias inteiras ou fatos pessoais como se Notion fosse fonte canônica.

- [x] **Step 4: Executar canário end-to-end.**

  Run: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_notion_sync.py tests/test_phase3_integration_e2e.py tests/test_positioning_artifacts.py tests/test_positioning_coverage.py`

  Expected: PASS; uma história adicionada à base chega ao pack, aos artefatos selecionados, aos receipts e ao snapshot Notion, sempre pelo mesmo `application_id`.

- [x] **Step 5: Rodar validações estruturais do projeto.**

  Run: `npm run validate:structure`

  Run: `npm run runtime:verify -- --strict`

  Expected: PASS sem tocar credenciais, overlays Hermes ou workspaces de bots.

- [x] **Step 6: Registrar a evidência no roadmap.**

  Atualizar `POSITION-001`, `POSITION-002` e `POSITION-003` para `DONE` somente com os testes, hashes/revisões e canário registrados. Se a cobertura de respostas de entrevista ou networking não estiver implementada no primeiro corte, criar um novo item separado em `BACKLOG`; não encerrar o item abrangente por inferência.

## Ondas de entrega, branches e worktrees

Branch e pasta separada são conceitos diferentes: a branch é a linha de
histórico que será commitada/mesclada; o `git worktree` é a pasta de trabalho
isolada ligada a essa branch. Este plano usará os dois.

Não criar as branches enquanto a execução não for autorizada. Quando for,
partir sempre do último `main` aprovado:

| Onda | Branch | Worktree | Escopo | Saída mínima |
|---|---|---|---|---|
| 1 — evidências | `feat/positioning-evidence-foundation` | `.worktrees/positioning-evidence-foundation` | Tasks 1–2 | base estruturada versionada, revisão/hash e `candidate_cv_facts` derivado |
| 2 — tradução | `feat/positioning-artifact-adapters` | `.worktrees/positioning-artifact-adapters` | Tasks 3–4 | positioning pack scoped e artefatos consumindo a mesma estratégia |
| 3 — governança | `feat/positioning-gates-notion` | `.worktrees/positioning-gates-notion` | Tasks 5–6 | cobertura/invalidação, snapshot Notion e canário end-to-end |

Cada onda seguirá este ciclo:

1. Confirmar que o checkout de `main` está limpo e atualizado.
2. Criar a branch e seu worktree a partir de `origin/main` ou do `main` local explicitamente aprovado.
3. Executar testes de baseline no worktree antes de editar.
4. Implementar somente o escopo da onda, com RED → GREEN → suíte focada.
5. Executar `npm run validate:structure`, `npm run runtime:verify -- --strict` e os canários previstos para a onda.
6. Commitar na branch, fazer push para o GitHub e abrir PR para `main`.
7. Após o merge, atualizar o checkout de deploy com `git pull --ff-only origin main`.
8. Recriar/reiniciar os serviços afetados e executar smoke pós-deploy antes de iniciar a onda seguinte.

O worktree de uma onda deve ser removido somente depois do merge e da
verificação do deploy. A branch pode ser preservada durante a janela de
observação e excluída depois, conforme a política do repositório.

## Pré-condição para começar

O checkout atual de `/opt/agent-projects/candidaturas` está na branch `main`,
mas possui alterações não commitadas e worktrees históricos. Portanto, não se
deve fazer `pull`, merge ou deploy diretamente nessa pasta enquanto ela estiver
suja. Antes da Onda 1 será necessário escolher uma destas opções:

- preservar essas alterações em um commit explicitamente identificado e
  incorporá-las ao histórico que será publicado; ou
- mantê-las fora do deploy e preparar um checkout limpo separado para `main`.

O plano não autoriza descarte, `reset --hard`, `checkout --` ou sobrescrita das
alterações atuais. A pasta principal só será usada como deploy após estar em um
commit conhecido, limpo e alinhado ao `origin/main`.

## Ordem de execução

Executar Onda 1, depois Onda 2 e somente então Onda 3. Cada onda passa por
revisão/merge/deploy antes da próxima. A Onda 1 foi implementada nesta branch
com testes focados e validação estrutural; sua integração em `main` ocorre
após a revisão final do commit.
ela torna as evidências completas e o `candidate_cv_facts` derivado, sem ainda
alterar o fluxo de produção dos demais artefatos.

## Decisão sobre Notion

Não criar propriedades novas no Notion neste plano inicial. Os campos atuais já registram o snapshot necessário. Uma futura frente separada pode criar uma base de histórias reutilizáveis no Notion apenas se houver necessidade real de consulta humana/relatórios; isso não deve ser pré-requisito para a geração correta dos artefatos.
