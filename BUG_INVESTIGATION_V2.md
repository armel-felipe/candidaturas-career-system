# Bug Investigation Guide: Applications V2

## Objetivo

Este guia define como investigar bugs no `applications_v2` sem depender de memória de conversa.

O foco é responder, para qualquer falha:

1. qual vaga entrou
2. em qual estágio falhou
3. qual arquivo era esperado
4. o que o agente recebeu
5. o que o agente devolveu
6. qual decisão local o orquestrador tomou depois

## Fontes de evidência

### 1. Log do heartbeat

Cada execução grava um resumo em:

```text
.career-state/applications_v2/_logs/<timestamp>.json
```

Use esse arquivo para descobrir:

- vagas selecionadas
- ordem da fila
- status final por vaga
- horário de início/fim

### 2. Pacote da candidatura

Cada vaga materializada fica em:

```text
.career-state/applications_v2/<ID>/
```

Arquivos principais:

- `manifest.json`: identidade da vaga
- `state.json`: estágio e score atual
- `job_description.md`: descrição usada
- `analysis_request.json`: contrato enviado ao agente
- `analysis_request.md`: prompt curto usado no runner
- `generation_request.json`: contrato textual do `generate`
- `generation_request.md`: prompt curto do `generate`
- `fit_map.draft.json`: draft produzido/esperado
- `fit_map.json`: resultado canonizado
- `cv_content.json`: conteúdo estruturado usado para renderizar o CV
- `agent_run.json`: stdout/stderr e comando do último agente executado
- `agent_run_analyze.json`: stdout/stderr do `analyze`
- `agent_run_generate.json`: stdout/stderr do `generate`
- `cv_review_report.json`: gate objetivo ATS/editorial do CV
- `polish_review.json`: gate de polimento textual
- `notion_update_payload.json`: payload devolvido ao Notion quando houver update rico
- `run_result.json`: resultado local final da vaga
- `error_report.json`: erro final, quando houver
- `event_log.json`: trilha cronológica estruturada

### 3. Trilha de eventos

O arquivo mais importante para investigação no v2 é:

```text
event_log.json
```

Ele registra, em ordem:

- `package_prepared`
- `package_reset_for_reprocess`
- `analyze_request_written`
- `generate_request_written`
- `context_written`
- `agent_started`
- `agent_finished`
- `postprocess_started`
- `postprocess_finished`
- `notion_status_updated`
- `run_result_written`
- `error`

## Fluxo de investigação recomendado

### Caso 1: a vaga não entrou na fila

Verificar:

1. status atual no Notion
2. aliases aceitos pela fila no config do v2
3. log do heartbeat para confirmar seleção

Perguntas:

- o status da vaga está dentro de `queue_status_aliases`?
- a vaga foi arquivada/excluída?
- o `record_id` apareceu no log do heartbeat?

### Caso 2: a vaga entrou, mas falhou no `analyze`

Verificar nesta ordem:

1. `state.json`
2. `event_log.json`
3. `agent_run.json`
4. existência de `fit_map.draft.json`
5. `error_report.json`

Perguntas:

- o agente foi chamado?
- o agente terminou com `returncode 0`?
- o draft foi realmente gravado?
- o draft foi gravado mas falhou na validação?
- a falha foi do modelo ou do pós-processamento local?

### Caso 3: o score saiu estranho

Verificar:

1. `fit_map.draft.json`
2. `fit_map.json`
3. `event_log.json` com `postprocess_finished`

Perguntas:

- o draft está no formato canônico?
- a pontuação final veio do `fit_map.json` já canonizado?
- a vaga caiu em `low_fit` por score real ou por draft incompleto?

### Caso 4: a vaga passou no fit, mas falhou depois

Verificar nesta ordem:

1. `generation_request.json`
2. `agent_run_generate.json`
3. existência de `cv_content.json`, `feras_formal.md` e habilidades
4. `cv_review_report.json`
5. `polish_review.json`
6. `run_result.json`

Perguntas:

- o `generate` gravou todos os artefatos textuais?
- o DOCX foi renderizado?
- a falha veio do gate objetivo ou do polimento?
- a vaga caiu em `blocked_review` com blockers reais ou por ausência de artefato?

### Caso 5: o Notion foi atualizado errado

Verificar:

1. `event_log.json` nos eventos `notion_status_updated`
2. `state.json`
3. `notion_update_payload.json` quando existir
3. log do heartbeat

Perguntas:

- a atualização foi para `Fila Agente`, `Aplicação em Análise` ou outro status?
- essa atualização aconteceu antes ou depois do score?
- houve update simples de status ou update rico com FIT_MAP?
- a vaga foi marcada como `low_fit` por regra local coerente?

## Regras para diagnóstico consistente

- Nunca investigar só pelo terminal; sempre abrir `event_log.json`.
- Nunca assumir que `returncode 0` significa artefato válido.
- Sempre confirmar a existência do arquivo esperado no pacote local.
- Sempre comparar `analysis_request.json` com o artefato produzido.
- Em falhas pós-análise, comparar `generation_request.json` com `cv_content.json`.
- Quando houver divergência entre stdout do agente e arquivos no disco, o disco vence.

## Checklist mínimo por bug

Ao registrar um bug do v2, guardar pelo menos:

1. `record_id`
2. arquivo de log do heartbeat
3. `state.json`
4. `event_log.json`
5. `agent_run.json`
6. `error_report.json` se existir
7. `cv_review_report.json` e `polish_review.json` quando a falha for após `generate`

Sem esses artefatos, a investigação é considerada incompleta.
