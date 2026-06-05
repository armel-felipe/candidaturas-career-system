---
name: habilidades-chave
description: >
  Seleciona e ranqueia habilidades defensáveis para uma vaga já analisada, usando o FIT_MAP ativo e histórias reais
  sem repetição. Use esta skill SEMPRE que o usuário pedir algo como "traga x habilidades mercado livre", "quais
  habilidades devo selecionar", "habilidades Gupy", "aplicar pelo sistema", "top habilidades para essa vaga" ou
  "resumo ATS", especialmente quando a saída precisa casar habilidade + experiência + história curta e defensável.
  Requer FIT_MAP ativo de `career-fit-analysis`; se não houver, executar a análise antes.
---

# Habilidades-Chave

## Governança da Skill

Manutenção canônica desta skill: `.opencode/skills/habilidades-chave/SKILL.md`.

Se precisar alterar gatilhos, referência da imagem, formato de saída ou regra de ranqueamento, editar sempre este arquivo
e os recursos dentro de `.opencode/skills/habilidades-chave/`.

## Objetivo Operacional

Esta skill substitui o pipeline antigo de seleção de habilidades do Gupy e também cobre o caso de catálogos externos,
como a lista da imagem de Mercado Livre transformada em arquivo útil.

Mercado Livre e Gupy são tratados como catálogos diferentes.

- Mercado Livre usa os rótulos exatamente como aparecem na imagem convertida em arquivo
- Gupy usa os rótulos exatamente como aparecem em `habilidades_gupy.json`
- uma habilidade de uma plataforma não deve ser renomeada para parecer a da outra
- sem equivalência automática, sem tradução livre e sem padronização cruzada de texto

Ela entrega uma lista ranqueada de habilidades com quatro campos por item:

- habilidade
- cargo
- empresa
- história defensável entre 500 e 700 caracteres

O princípio central é simples: cada habilidade precisa ser sustentada pela experiência mais recente e mais relevante
disponível, sem reciclar a mesma história como se fossem evidências diferentes.

## Pré-requisito

Antes de qualquer seleção:

1. Ler `../career-system/SKILL.md`.
2. Confirmar que `.career-state/fit_map.json` existe e corresponde à vaga atual.
3. Se não existir FIT_MAP ativo, executar `career-fit-analysis` primeiro.

## Comandos Obrigatórios

Antes de gerar a resposta ou gravar artefatos desta skill, executar:

```bash
npm run habilidades:check
```

Depois de gerar o arquivo final de habilidades, validar o artefato conforme a plataforma:

```bash
# Gupy
npm run habilidades:validate:gupy -- <arquivo_habilidades_gupy.md>

# Mercado Livre / catálogo externo
npm run habilidades:validate:mercado-livre -- <arquivo_habilidades_mercado_livre.md>
```

No heartbeat v2, os caminhos esperados são `.career-state/applications_v2/<ID>/habilidades_gupy.md` e `.career-state/applications_v2/<ID>/habilidades_mercado_livre.md`; ambos são validados localmente antes do DOCX e da finalização.

Se o validador falhar, a skill está incompleta. Corrigir o arquivo e rodar novamente o comando de validação; não substituir o gate por checklist textual.

## Referências Obrigatórias

Ler nesta ordem:

1. `../career-system/references/dicionario_palavras_chave_mercado.md`
2. `../career-system/references/palavras_chave_carreira.md`
3. `../career-system/references/autoconhecimento.md`
4. `../career-system/references/perfil_restricoes.md`
5. `.career-state/fit_map.json`
6. **`references/story-building-template.md`** — Template obrigatório para construção de histórias com 500-700 caracteres

Depois escolher a fonte de habilidades conforme o modo:

- `mercado_livre` ou catálogo externo: `references/habilidades_mercado_livre.json`
- `gupy`: `../career-system/references/habilidades_gupy.json`

## Regra de Compatibilidade por Plataforma

Antes de selecionar qualquer habilidade, identificar a plataforma alvo.

### Mercado Livre

- usar somente `references/habilidades_mercado_livre.json`
- preservar o texto exatamente como está no arquivo
- não reescrever `Warehouse Operations` como `Gestão Operacional`
- não reescrever `People Management` como `Gestão de Pessoas`
- não reescrever `Planning` como `Planejamento Estratégico`
- se o rótulo parecer estranho, duplicado ou pouco elegante, ainda assim manter o texto original da fonte

### Gupy

- usar somente `../career-system/references/habilidades_gupy.json`
- preservar o texto exatamente como está no arquivo
- não trocar `Gestão Operacional` por `Operations Management`
- não trocar `Gestão de Pessoas` por `People Management`
- não trocar `Planejamento Estratégico` por `Strategy` ou `Planning`
- como a compatibilidade com a plataforma depende do rótulo selecionável, nunca adaptar o texto para ficar "mais bonito"

Se a mesma ideia existir nas duas plataformas com nomes diferentes, tratar como habilidades distintas de catálogos
distintos. A escolha deve seguir a plataforma pedida, não a semelhança semântica.

## Modos de Execução

### Modo 1 — Mercado Livre / Catálogo Externo

Use este modo quando o usuário pedir algo como:

- `traga x habilidades mercado livre`
- `traga 8 habilidades para essa vaga`
- `quais habilidades desse catálogo fazem mais sentido`

Regras:

- usar somente habilidades do arquivo `references/habilidades_mercado_livre.json`
- preservar o texto exatamente como aparece na fonte
- respeitar a quantidade pedida pelo usuário
- se o usuário não informar quantidade, usar `10`
- priorizar aderência literal ao FIT_MAP e defensabilidade em entrevista

### Modo 2 — Gupy

Use este modo quando o usuário pedir algo como:

- `habilidades gupy`
- `aplicar pelo sistema`
- `seleciona as habilidades da plataforma`

Regras:

- usar somente `../career-system/references/habilidades_gupy.json`
- preservar o texto exatamente como aparece na fonte
- selecionar exatamente `10` habilidades
- manter aderência ao FIT_MAP e às regras históricas do projeto
- devolver no mesmo formato desta skill: habilidade + cargo + empresa + história

### Modo 3 — Gupy com resumo ATS

Se o pedido mencionar `resumo ATS`, `resumo Gupy` ou equivalente, depois da lista ranqueada gerar também um resumo
entre 500 e 600 caracteres.

Regras do resumo:

- framing com `Gerente Sênior`
- incluir pelo menos 3 keywords de `keywords_para_ats`
- incluir pelo menos 2 números validados em `perfil_restricoes.md`
- manter consistência com `historias_selecionadas` do FIT_MAP

## Critério de Ranqueamento

Ordenar do maior para o menor peso combinando:

1. criticidade da habilidade na vaga
2. aderência literal ao FIT_MAP e às keywords da vaga
3. força da evidência real disponível
4. recência da experiência, em caso de empate
5. poder competitivo da história contra candidatos genéricos

## Regra de Não Repetição de Histórias

Cada habilidade precisa ter uma história própria.

Trate como repetição indevida quando dois itens reaproveitam o mesmo núcleo narrativo:

- mesmo problema central
- mesmo contexto de negócio
- mesmo resultado principal
- mesma defesa causal da habilidade

Pode reutilizar a mesma empresa apenas se a história mudar de forma material, com outro desafio, outro recorte e outro
resultado.

Se não houver histórias únicas suficientes para preencher a quantidade solicitada:

- reduzir a lista ao número defensável
- declarar explicitamente quais habilidades ficaram de fora por falta de evidência distinta

## Como Escolher a Melhor Evidência

Para cada habilidade candidata:

1. procurar a experiência mais recente que tenha prova real da habilidade
2. comparar com a experiência mais aderente à dor central da vaga
3. escolher a que melhor equilibra recência, relevância e força numérica
4. registrar cargo e empresa dessa experiência

Nunca inventar ferramenta, escopo, time, budget ou resultado.

## Formato da História

Cada história deve ter entre `500` e `700` caracteres.

**Regra obrigatória: nenhuma história pode ser entregue abaixo de 500 caracteres.** Se a evidência disponível não permitir construir 500 caracteres com os 4 elementos abaixo, declarar como gap.

A história segue o Template de Story-Building (`references/story-building-template.md`) com 4 elementos obrigatórios:

1. **Contexto** — Onde Felipe estava, cargo, período, escopo da operação
2. **Problema ou Missão** — O desafio operacional ou de negócio
3. **Ação** — O que Felipe fez (verbo no passado, método, ferramenta, abordagem)
4. **Resultado mensurável** — Número concreto: saving, %, SLA, tempo, receita, volume, etc.

Cada história precisa conter:

- contexto da experiência
- problema ou missão
- ação de Felipe Armel
- resultado mensurável ou efeito operacional
- conexão explícita com a habilidade defendida
- **citação da fonte no formato `(Fonte: autoconhecimento.md:linhas X-Y)`**

Evite texto genérico. A habilidade deve ficar evidente pela ação e pelo resultado, não por adjetivo solto.

**Processo de construção (ordem obrigatória para cada história):**

1. Selecionar a habilidade do catálogo
2. Localizar no FIT_MAP qual termo_vaga corresponde
3. Extrair o bloco literal do `autoconhecimento.md` (não resumir de cabeça)
4. Construir a história com os 4 elementos
5. Contar caracteres. Se < 500, adicionar contexto, problema mais específico, ação detalhada ou segundo resultado
6. Verificar checklist da seção 2 do story-building-template
7. Escrever a fonte no formato `(Fonte: autoconhecimento.md:linhas X-Y)`

## Formato de Saída

Use esta estrutura:

```text
Habilidades-chave para [cargo] — [empresa]
Modo: [mercado_livre | gupy | gupy_com_resumo]

1. Habilidade: [nome]
Cargo: [cargo]
Empresa: [empresa]
História ([N] caracteres): [texto entre 500 e 700 caracteres]

2. Habilidade: [nome]
Cargo: [cargo]
Empresa: [empresa]
História ([N] caracteres): [texto entre 500 e 700 caracteres]
```

Quando houver gaps:

```text
Habilidades não selecionadas por falta de evidência distinta:
- [habilidade] — [motivo]
```

Quando o modo incluir resumo:

```text
Resumo ATS ([N] caracteres):
[texto]

Keywords cobertas no resumo: [lista]
```

## Checklist Pré-Entrega

- [ ] `npm run habilidades:check` executou com sucesso
- [ ] Validação do arquivo final executou com sucesso (`npm run habilidades:validate:gupy -- <arquivo>` ou `npm run habilidades:validate:mercado-livre -- <arquivo>`)
- [ ] FIT_MAP ativo corresponde à vaga atual
- [ ] Fonte de habilidades correta para o modo pedido
- [ ] Quantidade correta de habilidades
- [ ] Ordem ranqueada da mais relevante para a menos relevante
- [ ] Nenhuma história repete o mesmo núcleo narrativo
- [ ] **Cada história tem entre 500 e 700 caracteres (contado, não estimado)**
- [ ] **Nenhuma história foi entregue abaixo de 500 caracteres**
- [ ] **Cada história contém os 4 elementos: Contexto + Problema + Ação + Resultado**
- [ ] **Cada história tem resultado numérico concreto**
- [ ] **Cada história cita a fonte no formato `(Fonte: autoconhecimento.md:linhas X-Y)`**
- [ ] Cargo e empresa batem com a experiência escolhida
- [ ] Nenhum dado inventado
- [ ] **Nenhuma história usa resumo de cabeça — todas partiram de bloco literal extraído**
- [ ] Se houver resumo ATS, ele tem entre 500 e 600 caracteres

## Regras Críticas

- nunca usar habilidade fora da fonte do modo selecionado
- nunca renomear uma habilidade para aproximá-la do catálogo da outra plataforma
- nunca misturar rótulos de Mercado Livre e Gupy na mesma saída
- nunca repetir a mesma história como se defendesse habilidades diferentes
- nunca preferir uma história mais antiga se existir evidência mais recente com aderência equivalente
- nunca trocar defensabilidade por similaridade semântica
- **nunca escrever uma história sem antes ter extraído o bloco literal de `autoconhecimento.md` — não resumir "de cabeça"**
- **nunca entregar história com menos de 500 caracteres — se não houver material para 500, declarar gap**
- **a cada história deve constar a citação `(Fonte: autoconhecimento.md:linhas X-Y)`**
- no modo Gupy, respeitar exatamente 10 habilidades
- após gerar a saída, acionar `output-reviewer` antes da entrega final
- nunca considerar a skill concluída se `npm run habilidades:check` ou a validação do artefato final falhar
