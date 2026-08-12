---
name: intake-orchestrator
instruction_modules: [runtime-core, intake-fit-map]
description: >
  Normaliza a entrada de vagas antes de qualquer análise, FIT_MAP, CV, FERAS, carta, habilidades ou update no Notion.
  Use quando o usuário pedir avaliar/analisar uma vaga colada, uma URL, uma URL do LinkedIn, uma postagem do LinkedIn
  ou uma vaga pelo ID único do Notion. Esta skill executa os comandos npm `intake:*`; nomes como
  `intake:notion-record` são comandos, não skills.
---

# Intake Orchestrator

## Escopo

Esta skill é a porta de entrada de toda vaga específica.

Ela transforma qualquer origem em um estado comum:

- descrição salva em `inbox/job_descriptions/`;
- `active_intake` registrado em `.career-state/workflow_state.json`;
- `.career-state/fit_map.draft.json` recriado;
- guard executado;
- `next_required_step` explícito;
- `delivery_plan` para CV, FERAS, carta, habilidades e Notion.

## Regra central

`intake:notion-record`, `intake:paste`, `intake:linkedin-job`, `intake:linkedin-post`, `intake:url` e `intake:resume`
são comandos npm. Não tentar carregá-los como skills.

Antes de executar esta skill, leia também `.agents/skills/career-system/SKILL.md`.

## Comandos

One-shot recomendado para avaliar vaga por ID do Notion:

```bash
npm run agent:evaluate-notion -- <id_unico>
```

Guard de conduta do agente:

```bash
npm run agent:guard
```

Notion por ID único:

```bash
npm run intake:notion-record -- <id_unico>
```

Texto colado ou arquivo:

```bash
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>
cat <arquivo> | npm run intake:paste -- --company "<empresa>" --role "<cargo>" --stdin
```

LinkedIn:

```bash
npm run intake:linkedin-job -- --url "<url-da-vaga>"
npm run intake:linkedin-post -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

URL genérica:

```bash
npm run intake:url -- --url "<url>" --company "<empresa>" --role "<cargo>"
```

Observação operacional:
- `intake:url` é o caminho canônico para portais externos não-LinkedIn como Gupy, InHire, Greenhouse, Lever, Ashby, Workday e páginas nativas de carreiras.
- `--company` e `--role` viram hints/fallback; quando o extrator da página trouxer metadados confiáveis, eles podem ser omitidos.
- se a extração externa falhar por descrição curta, metadado fraco ou página não carregável, declarar bloqueio objetivo e pedir texto bruto da vaga.

Retomada:

```bash
npm run intake:resume
```

## Regras duras

- Para “avalie vaga Notion <id>”, usar `npm run agent:evaluate-notion -- <id>` antes de qualquer fallback.
- Se houver interrupção, output truncado ou dúvida após o intake, executar `npm run agent:guard`.
- Se `agent:guard` retornar `allowed_next_action = fill_fit_map_draft`, a única próxima ação autorizada é preencher `.career-state/fit_map.draft.json`.
- Se o comando `intake:*` retornar `status = ready_for_model_analysis`, parar o intake e preencher `.career-state/fit_map.draft.json`.
- Se retornar `next_required_step = fill_fit_map_draft`, não entregar análise textual, não rodar Notion alternativo e não usar FIT_MAP antigo.
- Preencher o draft é responsabilidade do agente em execução: ler `career-fit-analysis/SKILL.md`, ler as referências obrigatórias e editar `.career-state/fit_map.draft.json`. Nunca pedir que o usuário abra editor, substitua marcadores, preencha campos ou rode esse passo manualmente.
- Nunca imprimir o template bruto do draft na conversa como substituto da edição. Se o draft ainda tiver placeholders, a próxima resposta deve ser acompanhada de edição real do arquivo ou declaração de bloqueio objetivo.
- Em modo multiagente/local pequeno, depois do intake gerar/ler o request compacto com `npm run multiagent:request -- fit-map`; seguir as `Operational Rules` antes de editar.
- Após editar `.career-state/fit_map.draft.json`, executar `npm run validate:fit-map:draft`; se falhar, corrigir e reexecutar antes de responder ao usuário.
- Se `intake:*` falhar, não fazer fallback para `.env`, `curl`, API pública do Notion, navegador genérico, `grep` ou cache local.
- Para falha, executar `npm run intake:resume` e relatar o erro objetivo. Se ainda bloquear, declarar execução bloqueada.
- Nunca ler `.env`, copiar `NOTION_TOKEN`, montar script temporário de Notion ou criar arquivo `fetch_*.py`/`query_*.py`.
- Para LinkedIn, o intake usa os extratores autenticados; se bloquear por sessão, rodar/solicitar `npm run linkedin:auth`.

## Fluxo para “avalie vaga Notion 270”

1. Executar:

```bash
npm run agent:evaluate-notion -- 270
```

2. Confirmar no JSON:

- `status = ok`
- `guard.allowed_next_action = fill_fit_map_draft`
- `intake.job_description_path` existe

3. Ler `career-fit-analysis/SKILL.md` e preencher `.career-state/fit_map.draft.json` por edição direta do arquivo. Não parar para orientar o usuário a editar o draft.

4. Rodar as validações do FIT_MAP:

```bash
npm run fit-map:check:extract
npm run fit-map:check:map-evidence
npm run fit-map:check:score-draft
npm run fit-map:check:complete-draft
npm run fit-map:finalize
npm run keywords:register
```

5. Usar `delivery_plan` do intake para próximos artefatos.

## Bloqueios

Se a execução for bloqueada, responder com:

- comando executado;
- exit code;
- erro objetivo;
- próximo comando permitido.

Nunca pedir login no site do Notion nem abrir `www.notion.so` para esse fluxo.
