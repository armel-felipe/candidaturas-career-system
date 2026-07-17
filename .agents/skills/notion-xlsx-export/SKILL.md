---
name: notion-xlsx-export
description: >
  Exportar listas filtradas do tracker de candidaturas do Notion para planilha `.xlsx`, com artefatos auxiliares `.json`,
  `.csv` e relatório `.json`, sempre usando os scripts locais do projeto. Use esta skill sempre que o usuário pedir para
  gerar, refazer, replicar ou variar uma extração/tabulação/planilha do Notion com o mesmo layout de saída, especialmente
  quando mencionar filtros por campos como `empresa_int`, `tipo de empresa_int`, `Etapa Funil`, `Canal de aplicacao` ou
  quando quiser “uma planilha do Notion”, “um xlsx das vagas” ou “a mesma exportação com outro filtro”.
---

# Notion XLSX Export

## Escopo

Esta skill cria uma extração filtrada do banco de candidaturas do Notion e grava quatro artefatos no `outputs/`:

- `<base>.json`
- `<base>.csv`
- `<base>.xlsx`
- `<base>_report.json`

O layout de saída é fixo e segue o padrão já validado neste projeto:

1. `ID`
2. `Vaga`
3. `empresa_int`
4. `tipo de empresa_int`
5. `Etapa Funil`
6. `Tipo de Vaga`
7. `Data Aplicação`
8. `Canal de aplicacao`
9. `URL`
10. `Avaliacao de aderencia claude`
11. `Descricao da Vaga`

## Dependências canônicas

Antes de executar, ler também:

1. `.opencode/skills/career-system/SKILL.md`
2. `.opencode/skills/notion-transactions/SKILL.md`
3. `.opencode/skills/xlsx/SKILL.md`

Motivo:

- `career-system` define regras globais de contexto compacto.
- `notion-transactions` define o canal único de leitura do Notion.
- `xlsx` reforça que a entrega principal é uma planilha.

## Regras duras

- Nunca usar MCP, browser genérico, `curl`, token manual ou `.env` diretamente.
- Nunca escrever no Notion; esta skill é somente leitura/exportação.
- Não usar `applications_cache.json` como fonte primária quando o pedido for uma extração nova; ler do Notion via script canônico.
- Não improvisar formato de saída; manter sempre as 11 colunas padrão acima.
- Não responder só com tabela no chat quando o pedido exigir planilha; persistir o `.xlsx`.

## Comando canônico

Usar sempre:

```bash
npm run notion:export-xlsx -- --where "<campo>=<valor>" --output-base outputs/<nome_base>
```

Filtros múltiplos são permitidos e funcionam em `AND`:

```bash
npm run notion:export-xlsx -- \
  --where "tipo de empresa_int=50 Empresas para trabalhar" \
  --where "Etapa Funil=Aplicação andamento" \
  --output-base outputs/notion_50_empresas_aplicacao_andamento
```

Para filtros de texto com “contém qualquer um destes termos”, usar:

```bash
npm run notion:export-xlsx -- \
  --contains-any "Vaga=CEO|COO|Diretor|Director|Head|Gerente Senior|Gerente SR|Senior Manager" \
  --output-base outputs/notion_lideranca_keywords
```

## Workflow operacional

1. Confirmar o filtro a partir do pedido do usuário.
   - igualdade exata: `--where`
   - contém qualquer termo: `--contains-any`
2. Escolher um `output_base` descritivo em `outputs/`.
3. Executar `npm run notion:export-xlsx -- ...`.
4. Validar que o `.xlsx` existe.
5. Validar a integridade estrutural do `.xlsx` com:

```bash
unzip -t outputs/<nome_base>.xlsx
```

6. Responder com:
   - filtros aplicados
   - quantidade de linhas exportadas
   - caminhos dos artefatos gerados

## Saída esperada

Sempre citar, no mínimo:

- arquivo `.xlsx` principal
- quantidade de vagas exportadas
- filtro efetivamente usado

Quando útil, citar também os auxiliares:

- `.json`
- `.csv`
- `_report.json`

## Exemplo

Pedido do usuário:

`gere a mesma planilha das 50 empresas para trabalhar`

Execução:

```bash
npm run notion:export-xlsx -- \
  --where "tipo de empresa_int=50 Empresas para trabalhar" \
  --output-base outputs/notion_vagas_50_empresas_para_trabalhar
```

## Critério de conclusão

Só considerar concluído quando:

- o comando canônico tiver sido executado;
- o `.xlsx` existir em `outputs/`;
- `unzip -t` tiver confirmado integridade do arquivo;
- a resposta final refletir o filtro e a contagem reais.
