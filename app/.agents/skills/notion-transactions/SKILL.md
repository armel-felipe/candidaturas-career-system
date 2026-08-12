---
name: notion-transactions
instruction_modules: [runtime-core, notion-email]
description: >
  Operar a integração local com Notion para candidaturas: listar vagas, pesquisar/ler registro por ID único,
  preparar análise a partir de Notion, criar registro de vaga, atualizar descrição, atualizar registro com FIT_MAP
  e sincronizar o cache local. Use sempre que o usuário pedir qualquer leitura, criação, atualização ou consulta
  relacionada ao tracker de candidaturas no Notion.
---

# Notion Transactions

## Escopo

Esta skill é a camada operacional de Notion. A implementação canônica continua nos scripts locais:

- `scripts/notion_sync.py`
- `scripts/notion_query.py`
- comandos `npm run notion:*` definidos em `package.json`

Não mover scripts para dentro da skill: eles são compartilhados pelo heartbeat, services, CLI estruturada e fluxos manuais.

## Regras duras

- Nunca usar MCP/ferramentas externas de Notion (`notion-fetch`, `notion-search`, `notion-update-page`, `notion-create-pages` etc.).
- Nunca ler `.env`, copiar `NOTION_TOKEN`, montar `curl` manual ou chamar a API pública diretamente.
- Os scripts locais carregam `.env` e resolvem token, database/data source, propriedades, paginação, templates e validação de payload.
- Escrita real no Notion exige pedido explícito do usuário, exceto no maintenance path de governança (`notion:memory:sync`, heartbeat e backfill automático), que pode atualizar somente os campos de governança autorizados para manter o Notion como memória operacional do projeto.
- Mesmo quando a escrita real for autorizada, automações deste projeto nunca devem promover `Etapa Funil` acima de `Aplicação andamento`; `Aplicação Feita` é reservado para decisão/manual humano fora do pipeline.
- Para criação/atualização de registro, executar `--dry-run` antes da escrita real e mostrar o resumo do payload sem segredos.
- Quando o usuário disser `Notion <número>`, tratar o número como o campo único `ID`, não como `page_id`.
- Nunca usar `--allow-mismatch` para contornar descrição/FIT_MAP incompatível.
- Todo texto enviado ao Notion deve permanecer UTF-8 legível, sem mojibake.
- Fluxo padrão para vaga nova: `análise -> FIT_MAP final -> decisão de prosseguir -> Notion`.
- Criar página nova no Notion antes do FIT_MAP é exceção; só fazer isso quando o usuário pedir explicitamente capturar/registrar cedo a vaga antes da análise final.

## Configuração

As variáveis ficam em `.env`, mas agentes não devem abrir nem imprimir esse arquivo em tarefas de Notion.

Chaves usadas pelos scripts:

- `NOTION_TOKEN`
- `NOTION_APPLICATIONS_DATABASE_ID`
- `NOTION_APPLICATIONS_DATA_SOURCE_ID`
- `NOTION_APPLICATIONS_TEMPLATE_ID`
- `NOTION_APPLICATIONS_TEMPLATE_TIMEZONE`

Para validar configuração, executar um comando oficial de leitura, por exemplo:

```bash
npm run notion:list
```

## Comandos principais

Avaliar/analisar vaga por ID único do Notion:

```bash
npm run agent:evaluate-notion -- <id_unico>
npm run intake:notion-record -- <id_unico>
```

`agent:evaluate-notion` é o comando preferencial quando o pedido envolve análise, FIT_MAP, CV, FERAS, carta ou atualização posterior da mesma vaga. Ele resolve o ID, salva a descrição, recria o template do FIT_MAP, registra `active_intake`, roda o guard de conduta e devolve a próxima ação autorizada.

Listar candidaturas:

```bash
npm run notion:list
npm run notion:list-filtered -- --filter "Etapa Funil Fila Agente"
```

Consulta filtrada conversacional:

- pedidos como `traga vagas com Etapa Funil Fila Agente` usam consulta ao vivo no Notion e não usam cache local;
- é obrigatório informar pelo menos um filtro; combinações usam `E` e os campos/valores são validados pelo schema ativo;
- a lista curta retorna ID, cargo, empresa, Etapa Funil, aderência e link;
- quando o usuário responder com uma ID listada, encaminhar diretamente para `agent:evaluate-notion -- <id_unico>`.

Obter link do registro por ID único sem varrer cache:

```bash
npm run notion:link-record -- <id_unico>
```

Ler schema/templates:

```bash
npm run notion:schema
npm run notion:templates
```

Preparar análise a partir do campo único `ID`:

```bash
npm run notion:prepare-record -- <id_unico>
```

Atualizar a descrição de uma vaga existente, sempre com dry-run antes:

```bash
python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>" --dry-run
python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>"
```

Criar registro a partir do FIT_MAP ativo, sempre com dry-run antes quando a operação exigir preview:

```bash
npm run notion:create-current -- --dry-run
npm run notion:create-current
npm run notion:create-current -- --dry-run --extra-artifact outputs/<arquivo>.md --extra-note "Contexto complementar"
```

Criar registro a partir de descrição salva, sempre com dry-run antes:

```bash
python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run
python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>"
```

Atualizar o registro existente com FIT_MAP ativo, sempre com dry-run antes:

```bash
npm run notion:update-record-current -- <id_unico> --dry-run
npm run notion:update-record-current:compact -- <id_unico> --dry-run
npm run notion:update-record-current -- <id_unico>
npm run notion:update-record-current -- <id_unico> --dry-run --extra-artifact outputs/<arquivo>.md --extra-note "Memória complementar"
```

Memória complementar opcional:
- quando o usuário pedir para registrar outputs fora do pacote padrão, anexar `--extra-artifact <arquivo>` e/ou `--extra-note "<texto>"`
- esses extras entram no corpo da página do Notion na seção `Memória complementar`
- usar isso para hipóteses, listas alternativas de habilidades, sugestões de outro runtime/projeto ou observações humanas que valham como base de conhecimento
- a fonte oficial continua sendo o arquivo local; o Notion recebe uma cópia resumida/legível no corpo da página

Sincronizar histórico/cache antes de consultar candidaturas anteriores:

```bash
npm run notion:sweep:refresh
npm run notion:memory:sync -- --refresh missing
npm run notion:memory:sync -- --refresh full
```

Uso recomendado:

- `notion:sweep:refresh`: quando o objetivo é apenas atualizar o espelho bruto do Notion e o cache consolidado.
- `notion:memory:sync -- --refresh missing`: caminho padrão de manutenção, pois além do sweep incremental também reconstrói o registry técnico local, a memória compacta e executa o backfill automático de governança no Notion.
- `notion:memory:sync -- --refresh full`: usar quando houver suspeita de drift maior entre Notion e espelho local, ou quando for necessário auditar cobertura total do sweep; o backfill automático de governança continua fazendo parte do ciclo.

## Fluxos

### Avaliar vaga por ID do Notion

1. Executar `npm run agent:evaluate-notion -- <id_unico>`.
2. Se `guard.allowed_next_action = fill_fit_map_draft`, preencher `.career-state/fit_map.draft.json`.
3. Se o comando bloquear por descrição curta, pedir descrição/URL da vaga.
4. Depois do FIT_MAP finalizado, usar o `delivery_plan` retornado para CV, FERAS, carta, habilidades ou update do Notion.

Não usar `npm run notion:list`, `grep`, cache local ou `prepare-record` isolado como substituto do intake em pedido de avaliação.

Para pedidos como “traga o link do registro Notion <id>”, usar `npm run notion:link-record -- <id_unico>`.
Não procurar o link com `grep -r` em `applications_cache.json`, `applications_sweep` ou payloads salvos quando o ID único estiver disponível.

### Atualizar registro com descrição extraída

1. Confirmar que existe arquivo real de descrição em `inbox/job_descriptions/`.
2. Executar `update-description-record ... --dry-run`.
3. Se o dry-run resolver o `resolved_record_id` correto e `description_chars` for coerente, pedir aprovação para escrita real quando o usuário ainda não tiver autorizado.
4. Executar sem `--dry-run` apenas após autorização explícita.

### Criar registro novo

Fluxo padrão:

1. Confirmar que o `FIT_MAP` final da vaga já existe e pertence à vaga ativa.
2. Executar `npm run notion:create-current -- --dry-run` quando precisar de preview.
3. Validar título, status, template, score e campos consolidados que voltarão ao Notion.
4. Executar `npm run notion:create-current` apenas após autorização explícita.

Pitfall — `notion:create-current` pode retornar output vazio:
- Se `npm run notion:create-current -- --dry-run` retornar output vazio (exit 0), o script pode estar falhando silenciosamente
- Workaround: usar o script direto `./scripts/python.sh scripts/notion_sync.py create-from-fit-map --fit-map .career-state/fit_map.json --job-description <path> --dry-run`
- Antes de chamar o script direto, verificar se o heading do arquivo de descrição em `inbox/job_descriptions/` inclui o nome da empresa (ex: `# Manager, Supply Chain – Brazil — Invenergy` em vez de `# Manager, Supply Chain – Brazil`)
- Se o heading estiver sem empresa, corrigir com `patch` no `.md` antes de rodar o script

Exceção deliberada:

1. Confirmar pedido explícito de criação precoce no Notion antes do FIT_MAP final.
2. Confirmar empresa, cargo e arquivo de descrição.
3. Executar `create-description-record ... --dry-run`.
4. Validar título, status, template e tamanho da descrição no payload.
5. Executar sem `--dry-run` apenas após autorização explícita.

### Atualizar registro com FIT_MAP

1. Confirmar que `.career-state/fit_map.json` pertence à mesma vaga.
2. Executar `npm run notion:update-record-current -- <id_unico> --dry-run`.
   - Em modelo local, preferir `npm run notion:update-record-current:compact -- <id_unico> --dry-run`.
3. Se houver mismatch, corrigir origem/FIT_MAP/descrição; não forçar.
4. Executar escrita real apenas após autorização explícita.

## Resposta final esperada

Informar de forma objetiva:

- comando executado;
- ID/page resolvido;
- arquivo de descrição ou FIT_MAP usado;
- se foi dry-run ou escrita real;
- próximos bloqueios, quando houver.

## Execucao Multiagente

Quando acionada pelo maestro, esta skill deve operar como `notion-agent`.

Entrada obrigatoria:
- ler primeiro `.career-state/agent_requests/notion-update_request.json` ou `.career-state/agent_requests/notion-update_request.md`
- usar somente `scripts/notion_sync.py`, `scripts/notion_query.py` e comandos `npm run notion:*` permitidos no request

Saida obrigatoria:
- produzir dry-run primeiro
- informar ID/page resolvido, fonte da descricao/FIT_MAP e se houve mismatch
- executar escrita real somente quando o usuario tiver pedido explicitamente ou aprovado o preview

Proibido neste modo:
- usar MCP de Notion, `.env`, token, curl ou API publica direta
- varrer caches locais com grep/rg amplo para resolver ID que possui comando canônico
- usar `--allow-mismatch`
- criar ou atualizar pagina sem aprovacao explicita
- criar scripts temporarios na raiz
