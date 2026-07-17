---
name: application-keyword-table
description: Gera a tabela de candidatura no formato `keyword coberta | empresa | história`, com as keywords mais importantes da vaga que Felipe Armel realmente cobre. Use quando o usuário pedir uma tabela de keywords cobertas para concluir candidatura, Gupy, formulário manual, ATS ou resumo de aderência por keyword. Se houver FIT_MAP ativo para a vaga, consumir esse FIT_MAP. Se o usuário colar uma vaga nova e ainda não houver FIT_MAP, executar antes a skill `career-fit-analysis`. Se o usuário pedir a tabela sem colar vaga e sem indicar uma vaga já analisada, listar as vagas registradas usando a documentação/tracker antes de prosseguir.
---

# Application Keyword Table

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/application-keyword-table/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/application-keyword-table/SKILL.md`.

Leia também `../career-system/SKILL.md` antes de executar. Esta skill existe para produzir uma saída curta, útil para formulário de candidatura, com foco nas keywords mais relevantes que já têm evidência real na base.

## Fluxo de decisão

1. Verificar se o pedido aponta para uma vaga específica já analisada.
2. Se houver FIT_MAP ativo e ele corresponder à vaga pedida, usar diretamente `.career-state/fit_map.json`.
3. Se o usuário colar uma vaga nova ou pedir análise de uma vaga sem FIT_MAP:
   - executar `career-fit-analysis` primeiro;
   - só depois montar a tabela.
4. Se o usuário pedir a tabela sem colar vaga e sem identificar claramente uma vaga já analisada:
   - listar as vagas registradas via `python scripts/notion_sync.py list`;
   - devolver a lista para o usuário escolher uma.

## Fontes obrigatórias

Usar nesta ordem:

1. `.career-state/fit_map.json`
2. `../career-system/references/palavras_chave_carreira.md`
3. `../career-system/references/autoconhecimento.md`
4. `../career-system/references/perfil_restricoes.md`

Nunca inventar keyword coberta, experiência, número, cargo ou contexto.

## Como selecionar as linhas

Selecionar somente keywords que atendam aos critérios abaixo:

1. Estão entre as mais importantes da vaga:
   - priorizar `keywords_habilidade_ats` por ordem de prioridade;
   - depois usar `keywords_para_ats` e `keywords_vaga` apenas se agregarem.
2. Têm cobertura real:
   - origem `ja selecionada` ou equivalente defensável;
   - nunca usar item marcado como `gap sem cobertura`.
3. Conseguem ser ancoradas em uma única experiência com evidência forte.

Prioridade de seleção:

1. Keywords 1–8 de `keywords_habilidade_ats`
2. Keywords ligadas à dor central
3. Keywords que mitigam objeções fortes do recrutador
4. Keywords com melhor número defensável

Se o usuário não pedir quantidade, usar de 5 a 8 linhas. Preferir menos linhas fortes do que muitas linhas fracas.

## Como escolher empresa e história

Para cada keyword:

1. Escolher a empresa com a evidência mais forte e mais direta.
2. Usar o cargo exato daquela época.
3. Construir a coluna `história` como um único parágrafo de até 500 caracteres.
4. A história pode usar experiência que não entrou no CV, desde que pertença à base real do candidato.

## Regra de escrita da história

A coluna `história` deve:

1. Começar contextualizando cargo + empresa de forma natural.
2. Mostrar a principal entrega associada à keyword.
3. Fechar com o número ou efeito mais forte, quando houver.
4. Permanecer em um único parágrafo, direto e factual.

### Frases proibidas

Nunca escrever:

- `A história central`
- `A história mais forte`
- `A história mais relevante`

Substituir por construções mais naturais, por exemplo:

- `A principal entrega foi...`
- `O que mais se destacou foi...`
- `Para isso, conduzi...`
- `Nessa posição, liderei...`
- `Como [cargo], estruturei...`
- `Como [cargo], reduzi...`

Também é válido simplesmente abrir com verbo em primeira pessoa:

- `Como Diretor de Operações no iFood, ampliei...`
- `Como Coordenador de Expedição na Trifil, implantei...`

## Formato de saída

Entregar sempre uma tabela Markdown exatamente com estas colunas:

| keyword coberta | empresa | história |
|---|---|---|

Regras:

1. `keyword coberta` = termo da vaga ou keyword ATS priorizada.
2. `empresa` = uma única empresa.
3. `história` = um único parágrafo, até 500 caracteres.
4. Não adicionar texto antes ou depois da tabela, a menos que:
   - seja necessário informar que falta escolher a vaga;
   - seja necessário listar vagas registradas;
   - exista gap impeditivo.

## Quando listar vagas registradas

Se não houver vaga colada e a vaga não estiver identificada na conversa:

1. Rodar `python scripts/notion_sync.py list`
2. Entregar lista curta com:
   - título da vaga
   - `page_id`
   - URL quando útil
3. Pedir ao usuário para escolher uma vaga da lista.

## Regras críticas

- Nunca usar keyword marcada como gap.
- Nunca inventar equivalência sem base em `palavras_chave_carreira.md` ou `autoconhecimento.md`.
- Nunca omitir o cargo da época dentro da história.
- Nunca usar linguagem de coach.
- Nunca transformar a história em bullet list.
- Nunca ultrapassar 500 caracteres na coluna `história`.
- Nunca usar VivaReal como “gestor de CS”.
- Nunca alterar números críticos de `perfil_restricoes.md`.
