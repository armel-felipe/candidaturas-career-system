# SQLite Refactor + Service Decomposition Design

**Date:** 2026-07-12
**Status:** Approved for implementation

## Motivation

O sistema atual de candidaturas usa JSON filesystem como único mecanismo de persistência. Com 44+ diretórios de aplicação, estado duplicado (global + per-application), e serviços com 1000-1700 linhas, modelos locais pequenos (12-30B) sofrem para:

1. Consultar dados relacionais (ex: "vagas com Etapa Funil = Aplicação em Análise")
2. Manter arquivos grandes no contexto limitado
3. Navegar entre estado global e por aplicação
4. Recomeçar após interrupção sem reler dezenas de arquivos

## Escopo

1. Migrar armazenamento relacional de JSON para SQLite
2. Refatorar serviços grandes em unidades menores
3. Implementar CLI de queries com filtros SQL
4. Implementar memória de sessão para modelos locais
5. Deletar legado e migrar dados existentes

## 1. SQLite Schema

Arquivo único: `.career-state/career.db`

### Tabela: `applications`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | TEXT PRIMARY KEY | `local_20260708T212754` (mesmo formato atual) |
| `notion_id` | TEXT NULLABLE | ID único do Notion |
| `company` | TEXT | Nome da empresa |
| `role` | TEXT | Cargo/vaga |
| `source_type` | TEXT | `linkedin`, `notion`, `paste`, `url` |
| `source_url` | TEXT NULLABLE | URL de origem |
| `stage` | TEXT | `analyze_pending`, `generate_pending`, `done`, etc |
| `funil_stage` | TEXT | `Fila Agente`, `Aplicação em Análise`, `Aplicação andamento` |
| `score` | REAL NULLABLE | FIT_MAP score (0-10) |
| `cv_language` | TEXT | `pt`, `en` |
| `status` | TEXT | `active`, `archived`, `error` |
| `created_at` | TEXT | ISO 8601 |
| `updated_at` | TEXT | ISO 8601 |
| `job_description_path` | TEXT NULLABLE | Caminho para `.md` em `inbox/job_descriptions/` |
| `fit_map_path` | TEXT NULLABLE | Caminho para `fit_map.json` |
| `cv_path` | TEXT NULLABLE | Caminho para `outputs/<cv>.docx` |

**Índices:** `(funil_stage, status)`, `(notion_id)`, `(company, role)`, `(stage, status)`

### Tabela: `workflow_events`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `application_id` | TEXT NOT NULL REFERENCES applications(id) | |
| `event` | TEXT | `fit_map_built`, `cv_generated`, `review_passed` |
| `fingerprint` | TEXT | SHA256 do input |
| `metadata` | TEXT | JSON blob com detalhes |
| `created_at` | TEXT | ISO 8601 |

**Índice:** `(application_id, event)`

### Tabela: `notion_cache`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | TEXT PRIMARY KEY | ID único do Notion |
| `raw_json` | TEXT | JSON completo da página (fallback) |
| `company` | TEXT | |
| `role` | TEXT | |
| `funil_stage` | TEXT | `Etapa Funil` do Notion |
| `canal_aplicacao` | TEXT NULLABLE | |
| `tipo_empresa` | TEXT NULLABLE | |
| `status` | TEXT NULLABLE | |
| `url` | TEXT NULLABLE | |
| `last_synced` | TEXT | ISO 8601 |

**Índices:** `(funil_stage)`, `(company)`, `(tipo_empresa)`, `(canal_aplicacao)`

### Tabela: `keyword_registry`

| Coluna | Tipo | Descrição |
|---|---|---|
| `keyword` | TEXT | |
| `application_id` | TEXT | (composite PK com keyword) |
| `coverage` | TEXT | `exact`, `similar`, `gap`, `missing` |
| `evidence` | TEXT NULLABLE | História/experiência que cobre |
| `created_at` | TEXT | ISO 8601 |
| PRIMARY KEY | `(keyword, application_id)` | |

**Índice:** `(application_id)`

### Tabela: `session_memory`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `session_id` | TEXT | UUID automático gerado por sessão do agente |
| `key` | TEXT | `active_application`, `last_step`, `next_step` |
| `value` | TEXT | JSON value |
| `created_at` | TEXT | ISO 8601 |
| `ttl_seconds` | INTEGER | Tempo de vida (default 3600) |

**Índice:** `(session_id, key)`

### O que permanece em JSON

- `fit_map.draft.json` e `fit_map.json` — artefatos de sessão, referenciados por path
- `cv_content.json` — conteúdo do CV, gerado por sessão
- Derived packs (`cv_input_pack.json`, `feras_input_pack.json`, etc) — contexto compacto
- `outputs/` — artefatos finais DOCX
- `.career-state/approvals/` — aprovações transientes
- `.career-state/pending_actions/` — ações pendentes transientes
- `.career-state/agent_requests/` — requests de agente
- `.career-state/harness/` — estado de menu

## 2. Refatoração dos Serviços

### `harness_supervisor.py` (1773 → ~300 linhas)

Decomposto em 4 serviços + orquestrador enxuto:

| Arquivo | Responsabilidade | Linhas |
|---|---|---|
| `services/classifier.py` | Classificar intenção do usuário | ~150 |
| `services/router.py` | Roteamento para especialista correto | ~200 |
| `services/menu.py` | Construir menus interativos | ~150 |
| `services/executor.py` | Executar ação, validar saída | ~250 |
| `services/harness_supervisor.py` | Orquestrador: coordena os 4 acima | ~300 |

### `applications_v2.py` (1177 → ~300 linhas)

| Arquivo | Responsabilidade | Linhas |
|---|---|---|
| `services/queue.py` | Montar fila de elegíveis do SQLite | ~150 |
| `services/stages.py` | Stage machine pura | ~200 |
| `services/heartbeat.py` | Loop principal | ~300 |

### `derived_context.py` (1179 → ~150 linhas)

| Arquivo | Responsabilidade | Linhas |
|---|---|---|
| `services/derived_context.py` | Orquestrador enxuto | ~150 |
| `services/packs/cv_input_pack.py` | Pack CV input | ~120 |
| `services/packs/feras_input_pack.py` | Pack FERAS | ~80 |
| `services/packs/cover_letter_pack.py` | Pack cover letter | ~80 |
| `services/packs/habilidades_pack.py` | Pack habilidades | ~80 |
| `services/packs/fit_map_seed.py` | Seed FIT_MAP | ~100 |

### `multiagent.py` (967 → ~450 linhas)

| Arquivo | Responsabilidade | Linhas |
|---|---|---|
| `services/agent_contracts.py` | Definição dos 8 contratos | ~200 |
| `services/agent_requests.py` | Geração/validação de requests | ~250 |

### `workflow/state_machine.py` + `state_store.py` → `services/workflow.py`

| Arquivo | Responsabilidade | Linhas |
|---|---|---|
| `services/workflow.py` | State machine + SQLite persistence | ~200 |

## 3. CLI de Queries

### Comando: `career_cli.py query`

```
career_cli.py query --filter "funil_stage = 'Aplicação em Análise'"
career_cli.py query --filter "funil_stage = 'Fila Agente' AND score >= 6.0"
career_cli.py query --filter "company LIKE '%uber%'"
career_cli.py query --filter "tipo_empresa = 'Startup'" --source notion
```

### Formatos de saída

| Formato | Uso |
|---|---|
| `table` | Tabela no terminal (padrão) |
| `json` | JSON array para agente/script |
| `human` | Frases curtas |
| `ids` | Só IDs para pipe |

### Comandos auxiliares

```
career_cli.py query --list-filters
career_cli.py query --count --filter "funil_stage = 'Fila Agente'"
career_cli.py query --filter "funil_stage = 'Fila Agente'" --limit 5 --offset 0
```

### Comandos de sessão

```
career_cli.py session status
career_cli.py session set <key> <value>
career_cli.py session get <key>
career_cli.py session get-all
career_cli.py session clean
career_cli.py session reset
```

## 4. Migração de Dados

### Regra de deduplicação

O script de migração deve deduplicar as 44 entradas de `applications_v2/` por `company+role`, mantendo apenas a entrada mais recente (por `created_at`). Entradas duplicadas mais antigas são movidas para `legado/migrated_duplicates/` — não deletadas, apenas arquivadas.

### Segurança do parser de filtro

O comando `query --filter` usa um parser próprio que aceita apenas: `=`, `!=`, `LIKE`, `AND`, `OR`, `>`, `<`, `>=`, `<=`, `IN`, `IS NULL`, `IS NOT NULL`. Valores são sempre passados como parâmetros SQLite (`?`), nunca interpolados. Não há risco de SQL injection.

### Script: `scripts/migrate_to_sqlite.py`

```
python3 scripts/migrate_to_sqlite.py --dry-run   # prévia
python3 scripts/migrate_to_sqlite.py              # executa
python3 scripts/migrate_to_sqlite.py --cleanup    # + move JSONs para legado/
```

### Fluxo de migração

1. Criar `career.db` com schema
2. Ler cada application v2, inserir em `applications`
3. Ler `workflow_state.json`, inserir eventos em `workflow_events`
4. Ler `applications_cache.json`, inserir em `notion_cache`
5. Ler `keyword_ats_registry.json`, inserir em `keyword_registry`
6. Ler `session_registry.json`, inserir em `session_memory`
7. Validar integridade (contagem de linhas vs registros fonte)
8. Se `--cleanup`, mover JSONs fonte para `legado/migrated_jsons/`

## 5. Deleções

### Remover definitivamente

| Caminho | Motivo |
|---|---|
| `legado/` | Código morto |
| `sessions/` | Auditoria antiga |
| `.career-state/cv_content 2.json` | Duplicata |
| `.career-state/fit_map.draft 2.json` | Duplicata |
| `.career-state/cv_content.json.stale` | Stale |
| `.career-state/cv_content.json.edited.backup` | Backup manual |
| `.career-state/fit_map_general.json` | Substituído |
| `.career-state/linkedin_job_extract.json` | Substituído |
| `.career-state/url_job_extract.json` | Substituído |
| `.career-state/browser-gateway/` | Não usado |
| `.career-state/telegram/` | Será migrado se necessário |
| `inbox/linkedin_posts/` | Extrações antigas |
| `inbox/drafts/` | Drafts antigos |
| `outputs.local-before-onedrive-20260525-125925/` | Backup de migração |

## 6. Princípios de Design para Modelos Locais

1. **Cada arquivo < 350 linhas** — cabe no contexto de uma chamada de modelo 12-30B
2. **CLI como interface do agente** — modelo local não lê JSON direto, usa comandos que retornam respostas curtas
3. **Session memory com TTL** — elimina necessidade de reler estado a cada passo
4. **Queries SQL em vez de grep/json walk** — `query --filter` retorna só o necessário
5. **JSON apenas para artefatos de sessão** — FIT_MAP draft, CV content, derived packs são gerados e consumidos no mesmo ciclo
6. **Sem dualidade de estado** — SQLite é a fonte única; `workflow_state.json` global desaparece
