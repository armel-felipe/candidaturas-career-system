# Unificação do Runtime de Candidaturas — Design

## Objetivo

Unificar o runtime executado pelos bots de candidatura e tornar o SQLite a fonte canônica de persistência para todas as informações operacionais da carreira: vagas, análises, estados, gates, memória, requests, execuções, artefatos, revisões e entregas.

O sistema deverá permitir recuperar qualquer candidatura por `application_id`, ID do Notion ou fingerprint, independentemente do bot que a processou, e deverá impedir que uma execução pareça concluída quando seus gates e artefatos não foram registrados.

## Diagnóstico de origem

O diagnóstico que motivou este design encontrou:

1. O Hermes de `vagas_bot_01` monta `/opt/agent-projects/candidaturas/app`, enquanto correções recentes foram feitas na raiz do projeto. Existem duas cópias divergentes de código, skills e documentação.
2. A execução de intake e tarefas usa `WorkflowStateStore()` global quando o `application_id` não é propagado. A lista global de `task_history` mistura vagas diferentes e não possui `application_id` em todos os registros.
3. O estado por candidatura pode continuar em `created`/`fill_fit_map_draft` mesmo quando FIT_MAP, CV e relatório de revisão existem em caminhos globais ou em outro escopo.
4. O supervisor considera a existência de qualquer output permitido suficiente para concluir um especialista; ele não exige o conjunto de artefatos e gates necessários.
5. A skill `processe-a-vaga` contém sincronização inline que sobrescreve o estado global, remove fingerprints e desfaz gates anteriores.
6. Estado, FIT_MAP, manifests, input packs, requests, memória e relatórios são persistidos em muitos JSONs concorrentes. O banco SQLite existente possui tabelas de aplicações, runs, artefatos e receipts, mas os runtimes legado, `app` e celular não usam uma fonte única.
7. O diretório `app` e a raiz contêm implementações diferentes de serviços críticos, incluindo `agent_guard.py`, `derived_context.py`, `harness_supervisor.py`, `multiagent.py` e `application_context.py`.

## Requisitos funcionais

### R1 — Runtime único

Todos os bots devem executar o código canônico da raiz do repositório. `app/` não poderá ser uma segunda implementação ativa. O Compose deverá montar o código raiz e os diretórios mutáveis de estado/output de cada bot separadamente.

### R2 — Fonte canônica SQLite

No domínio de candidatura, nenhum arquivo JSON será fonte de verdade. O banco-alvo é `control-plane/career.db`, compartilhado pelos bots no mesmo host e protegido por WAL, foreign keys, `busy_timeout`, transações e migrations versionadas.

Os bancos `.career-state/career.db`, `app/.career-state/career.db` e qualquer banco legado de candidatura serão tratados como fontes de migração ou backup, não como fontes ativas após o cutover.

### R3 — Processamento fechado da vaga

`processe-a-vaga` terá exatamente este escopo:

```text
intake → FIT_MAP calculado/analisado/validado → CV revisado/aprovado
→ CV entregue ao OneDrive → Notion criado/atualizado → pacote-base fechado
```

FERAS, carta de apresentação, habilidades Gupy, respostas de entrevista, networking e revisão de histórias serão artefatos pós-processamento, criados sob demanda e sem bloquear o fechamento do pacote-base.

### R4 — Recuperação cross-bot

Qualquer agente deverá localizar a candidatura sem depender de `active_job`, estado global, nome presumido de arquivo ou bot de origem. A resolução deverá aceitar:

- `application_id`;
- ID único do Notion;
- fingerprint da descrição;
- combinação empresa/cargo somente quando não houver ambiguidade.

### R5 — Proveniência e versionamento

FIT_MAP, posicionamento, histórias e artefatos serão imutáveis por revisão. Cada artefato deverá registrar a revisão de análise e de posicionamento que utilizou, além de hash, runtime, bot, run e status de validação.

### R6 — Gates fail-closed

Arquivo existente não equivale a gate aprovado. Uma tarefa só poderá alterar o estágio da candidatura quando houver receipt compatível com `application_id`, fingerprint, input hash, output hash e validador aprovado.

### R7 — Recuperação sem improviso

Dados legados com identidade resolvida por Notion ID, alias, fingerprint ou evidência consistente poderão ser importados como `historical_unverified` quando não houver receipts antigos. Isso torna FIT_MAP, posicionamento e catálogo de artefatos recuperáveis sem inventar validações. Somente identidade ambígua, fonte alterada ou fingerprint incompatível bloqueia aquela candidatura; o conflito não bloqueia as demais.

### R8 — Verificação ponta a ponta

O projeto deverá ter um verificador executável que confira runtime, schema, isolamento, invariantes de gates, cobertura da migração, recuperação cross-bot, ausência de novas escritas canônicas em JSON e comportamento da skill `processe-a-vaga`.

## Arquitetura-alvo

### Banco de controle

`control-plane/career.db` será o banco compartilhado de carreira. A camada `src/career/services/database.py` será consolidada com o schema celular já existente, sem manter uma versão divergente em `app/src`.

O banco deverá conter, no mínimo, os seguintes grupos de dados:

| Grupo | Tabelas ou entidades |
|---|---|
| Candidaturas | `applications`, `application_aliases`, `application_revisions` |
| Fontes da vaga | `job_sources`, `job_descriptions`, `job_sections` |
| Análise | `fit_map_revisions`, `fit_map_dimensions`, `fit_map_keywords`, `fit_map_evidence`, `fit_map_objections`, `fit_map_stories`, `fit_map_scores` |
| Posicionamento | `positioning_revisions`, `positioning_stories`, `positioning_principles` |
| Referências do candidato | `reference_documents`, `candidate_facts`, `candidate_evidence`, `keyword_translations` |
| Execução | `application_runs`, `run_nodes`, `run_attempts`, `agent_requests`, `agent_responses` |
| Gates | `workflow_events`, `validation_receipts`, `gate_dependencies` |
| Artefatos | `artifacts`, `artifact_versions`, `artifact_contents`, `artifact_dependencies` |
| Integrações | `notion_records`, `notion_syncs`, `deliveries` |
| Operação | `runtime_workers`, `runtime_observations`, `resource_locks`, `migration_runs`, `migration_conflicts` |

As tabelas existentes serão reutilizadas quando a semântica for compatível. Novas tabelas receberão migrations incrementais; não haverá recriação destrutiva do banco.

### Política de conteúdo

Dados atualmente representados em JSON serão tratados assim:

1. Identidade, estado, gates, relações, hashes, prioridades e status virarão colunas e tabelas relacionais.
2. Estruturas de análise variáveis poderão manter um `payload_json` validado dentro do SQLite como snapshot imutável, acompanhado das colunas relacionais necessárias para consulta e validação.
3. Input packs serão views/consultas materializadas em memória. Quando uma ferramenta exigir JSON, o runtime fará uma exportação temporária com fingerprint e expiração; esse arquivo não será lido de volta como estado.
4. Textos de FERAS, cartas, respostas e revisões poderão ser armazenados em `artifact_contents` e também exportados para `.md`/`.txt`.
5. DOCX/PDF permanecerão em armazenamento de arquivos. O SQLite guardará caminho, tamanho, hash, MIME type, revisão, aprovação e entrega.
6. `package.json`, arquivos de configuração exigidos pelo Node/Python, perfis de navegador, OAuth e caches de terceiros ficam fora do domínio de carreira e não serão artificialmente convertidos em tabelas.

### Pacote-base e pós-processamento

O pacote-base será identificado no SQLite por `application_id` e conterá o FIT_MAP final, o snapshot de posicionamento, o CV aprovado, receipts de revisão/entrega e a sincronização do Notion.

Os artefatos pós-processamento serão filhos da candidatura e apontarão para as revisões utilizadas:

```text
application_id
  ├── analysis_revision
  ├── positioning_revision
  ├── core artifacts: cv, delivery, notion
  └── post artifacts: feras, cover_letter, gupy, interview, networking, story_review
```

Uma nova revisão de histórias não sobrescreverá a anterior. Artefatos antigos permanecerão recuperáveis e novos artefatos apontarão para o snapshot atualizado.

## Contrato de estado

O estágio da candidatura será derivado dos receipts válidos e não de um campo livre gravado por agentes.

Estados previstos:

- `intake_pending`;
- `fit_map_pending`;
- `fit_map_validated`;
- `cv_pending`;
- `cv_review_pending`;
- `cv_approved`;
- `onedrive_pending`;
- `notion_pending`;
- `core_package_sealed`;
- `post_processing_available`;
- `historical_unverified`;
- `blocked_reconciliation`;
- `failed_retryable`.

`next_required_step` será uma projeção calculada a cada leitura. O estado global legado poderá existir apenas como projeção de compatibilidade e não poderá ser escrito por agentes.

## Fluxo de transação

Cada operação que altera o processamento deverá:

1. resolver `application_id` e fingerprint;
2. abrir uma transação SQLite;
3. criar `run` e tentativa idempotentes;
4. registrar inputs e hashes;
5. persistir artefatos e receipts;
6. validar dependências;
7. atualizar a projeção de estágio;
8. confirmar a transação;
9. materializar arquivos derivados somente após commit.

Falhas antes do commit não poderão deixar um gate parcialmente avançado.

## Migração

A migração deverá ser em três estágios:

1. **Inventário e shadow import:** ler JSONs e bancos existentes, registrar origem, hash e classificação no SQLite sem alterar o runtime.
2. **Cutover controlado:** o runtime passa a escrever SQLite e, se necessário, materializa JSONs compatíveis somente como saída temporária.
3. **Desativação:** leituras de fallback em JSON são removidas após canários aprovados e período de observação.

Conflitos serão resolvidos nesta ordem:

1. registro por candidatura com fingerprint compatível;
2. receipt validado e artefato cujo hash corresponde;
3. dado global somente se identidade e fingerprint coincidirem;
4. identidade confirmada sem receipt antigo: importar como `historical_unverified`, com warning explícito;
5. caso contrário, `migration_conflicts` e bloquear somente a candidatura afetada.

People Meet será o fixture de recuperação de estado inconsistente. Conexa 578 será o fixture de recuperação cross-bot e de contexto app-scoped.

## Segurança operacional e backup

- Antes da migração, criar backup SQLite via API de backup e cópia dos diretórios JSON/outputs.
- Ativar `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout=10000` e `synchronous=FULL` no banco de controle.
- Executar `PRAGMA integrity_check` e `PRAGMA foreign_key_check` no início e no fim de cada migration.
- Não executar limpeza destrutiva em `outputs/`, `.career-state/`, `app/` ou `workspaces/` durante a migração.
- Rollback de código deverá restaurar o mount/runtime anterior; rollback de dados deverá usar snapshot SQLite e preservar eventos posteriores em banco separado de quarentena.

## Critérios de aceite

O design será considerado implementado quando:

1. `vagas_bot_01` e `vagas_bot_02` executarem a mesma árvore canônica da raiz.
2. Nenhum gate novo for escrito em `workflow_state.json` global ou em JSON por candidatura.
3. Uma candidatura recuperada por Notion ID produzir o mesmo FIT_MAP e posicionamento independentemente do bot.
4. People Meet e Conexa 578 ficarem recuperáveis como `historical_unverified` quando a identidade e o FIT_MAP forem confirmados, sem criar receipts retroativos.
5. Um CV sem review/approval/delivery não puder fechar o pacote-base.
6. `processe-a-vaga` não gerar FERAS, carta ou habilidades automaticamente.
7. Um artefato pós-processamento puder ser criado sem reexecutar intake ou alterar o FIT_MAP vigente.
8. A revisão de histórias criar nova versão e não invalidar silenciosamente os artefatos antigos.
9. O verificador estrito retornar zero blockers em fixtures novos; fixtures históricos não verificáveis devem aparecer como `historical_unverified`, nunca como gates aprovados.
10. O rollback do canário ser executável sem apagar dados novos.
