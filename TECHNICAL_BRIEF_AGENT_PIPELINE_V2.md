# Technical Brief: Agent Pipeline V2

## Objetivo

O `applications_v2` existe para substituir o heartbeat atual por uma base menor e previsível.

Princípios:

- fila lida direto da API do Notion
- uma candidatura por vez, sempre serial
- pacote local isolado em `.career-state/applications_v2/<ID>/`
- o agente só produz artefatos da etapa corrente
- o orquestrador decide fila, persistência, score, render e gates locais

## Escopo atual

Implementado:

- leitura direta do Notion
- seleção de vagas elegíveis por status
- criação do pacote local da candidatura
- detecção de idioma da vaga
- template obrigatório de `fit_map.draft.json`
- request compacto de `analyze`
- request compacto de `generate`
- chamada do agente por etapa
- pós-processamento local do FIT_MAP
- registro de keywords do FIT_MAP
- geração de artefatos textuais:
  - `cv_content.json`
  - `feras_formal.md`
  - `habilidades_gupy.md`
  - `habilidades_mercado_livre.md`
- render local do DOCX
- gate local de review/polish do CV
- atualização estruturada no Notion com `update_from_fit_map_record`
- classificação operacional:
  - `low_fit`
  - `generate`
  - `blocked_review`
  - `done`

Ainda não implementado no v2:

- etapa dedicada de `repair`
- comandos manuais granulares equivalentes ao legado (`prepare/analyze/generate/finalize` por record)

## Observabilidade e investigação

O v2 grava evidência estruturada para debugging:

- log de execução do heartbeat em `.career-state/applications_v2/_logs/`
- trilha por candidatura em `event_log.json`
- stdout/stderr bruto do último agente em `agent_run.json`
- stdout/stderr por etapa em:
  - `agent_run_analyze.json`
  - `agent_run_generate.json`
- reports locais de gate:
  - `cv_review_report.json`
  - `polish_review.json`

Guia operacional de investigação:

```text
BUG_INVESTIGATION_V2.md
```

## Comandos

```bash
npm run applications:heartbeat -- --dry-run --max-per-run 2
npm run applications:agent-heartbeat -- --max-per-run 2
```

Script local dedicado:

```bash
./run_agent_heartbeat_once.sh
```

## Estado local

Diretório canônico:

```text
.career-state/applications_v2/<record_id>/
```

Arquivos esperados:

```text
manifest.json
state.json
job_description.md
fit_map.draft.json
fit_map.json
analysis_request.json
analysis_request.md
generation_request.json
generation_request.md
conversation_context.md
cv_content.json
feras_formal.md
habilidades_gupy.md
habilidades_mercado_livre.md
agent_run.json
agent_run_analyze.json
agent_run_generate.json
cv_review_report.json
polish_review.json
notion_update_payload.json
run_result.json
error_report.json
event_log.json
```
