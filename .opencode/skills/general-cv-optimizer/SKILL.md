---
name: general-cv-optimizer
description: >
  Gera e valida o pacote de posicionamento geral de Felipe Armel para CV mestre DOCX, LinkedIn, Gupy e Mercado Livre.
  Use quando o usuário pedir CV geral, currículo geral, CV para sites de emprego, otimização ATS ampla, LinkedIn para busca
  ativa, revisão de competências gerais, habilidades Gupy gerais ou habilidades Mercado Livre gerais.
---

# General CV Optimizer

## Governança da Skill

Manutenção canônica desta skill: `.opencode/skills/general-cv-optimizer/SKILL.md`.

Antes de executar, leia também `../career-system/SKILL.md`. Esta skill não substitui `cv-generator` para vagas específicas;
ela cria o CV mestre e os relatórios de plataforma para busca ativa e reposicionamento geral.

## Primeira Decisão Obrigatória

Antes de rodar a estratégia, perguntar se o usuário quer:

1. **Usar dados existentes** — padrão recomendado para ganhar tempo. Consome `.career-state/memory/`,
   `inbox/notion/applications_cache.json` e os registries já gerados.
2. **Atualizar antes** — executar `npm run notion:sweep:refresh`, `npm run keywords:translations:build` e
   `npm run memory:build` antes de montar a estratégia.

Se o usuário não responder e o pedido for operacional, usar dados existentes. Se cache, memória ou registry estiverem
ausentes ou vazios, bloquear e recomendar atualização.

## Modos de Escrita do CV Geral

### Geral conciso — padrão

Usar quando o usuário pedir `CV geral`, `CV para sites`, `CV ATS geral`, ou não especificar modo.

Regras do modo conciso:
- `mode = concise`
- `dominant_cluster = operacoes_supply_logistica` quando o usuário não informar outro foco
- usar 3 bullets por experiência no padrão atual do `cv-generator`
- escolher keywords do cluster dominante e adjacências essenciais, sem tentar cobrir todos os clusters no CV
- manter experiências separadas; se o cluster dominante pedir foco, selecionar menos experiências, nunca consolidar cargos

### Geral expandido / bullet points

Usar somente quando o usuário pedir explicitamente `bullet points`, `expandido`, `não conciso`, `mais completo` ou especificar número de bullets por experiência.

Se o agente apenas inferir que o CV geral poderia se beneficiar de versão expandida, validar com o usuário antes de executar. Sem confirmação explícita, manter `mode=concise`.

Regras:
- `mode = expanded`
- `bullet_count = 8` por padrão
- aceitar `bullet_count` entre 4 e 8 quando o usuário especificar
- quando houver margem, preferir sempre o máximo de bullets
- cada experiência, cargo, promoção ou fase selecionada deve aparecer como entrada própria; nunca juntar experiências para criar um CV geral mais curto
- cada bullet deve ser uma frase única entre 270 e 330 caracteres
- cada frase integra responsabilidade, alavanca usada e resultado/efeito mensurável
- usar clusters como arquitetura interna, cobrindo núcleo forte e adjacências defensáveis

Clusters aceitos:
- `operacoes_supply_logistica` — Operações / Supply Chain / Logística
- `planejamento_sop_capacity` — Planejamento / S&OP / Capacity Planning
- `transformacao_eficiencia` — Transformação / Eficiência / Melhoria Contínua
- `cx_saas_operations` — CX / SaaS Operations
- `product_revenue_business_ops` — Product / Revenue / Business Operations

## Comandos

Gerar estratégia no modo padrão conciso:

```bash
npm run general-cv:strategy
```

Gerar estratégia expandida com número específico de bullets:

```bash
npm run general-cv:strategy -- --mode expanded --bullet-count 5
```

Gerar conciso por cluster:

```bash
npm run general-cv:strategy -- --mode concise --dominant-cluster operacoes_supply_logistica
```

Gerar expandido quando o usuário pedir bullet points:

```bash
npm run general-cv:strategy -- --mode expanded --bullet-count 8
```

Validar conteúdo antes do DOCX:

```bash
npm run general-cv:validate-content -- --path .career-state/general_cv_content.json
```

Gerar DOCX geral a partir do conteúdo validado:

```bash
npm run general-cv:docx
```

Aprovar DOCX final:

```bash
npm run general-cv:approve -- --artifact outputs/felipe_armel_cv_geral_operacoes_supply_chain.docx
```

## Entregas

- `outputs/felipe_armel_cv_geral_operacoes_supply_chain.docx`
- `outputs/general_cv_strategy.md`
- `outputs/linkedin_competencias_gerais.md`
- `outputs/gupy_habilidades_revisao.md`
- `outputs/mercado_livre_habilidades_revisao.md`

## Validações Obrigatórias

- CV geral sem modo explícito deve usar `mode=concise`, `bullet_count=3` e `dominant_cluster=operacoes_supply_logistica`.
- CV geral expandido com menos de 4 ou mais de 8 bullets deve bloquear.
- CV geral conciso com quantidade diferente de 3 bullets por experiência deve bloquear.
- Bullet narrativo expandido fora de 270–330 caracteres deve bloquear.
- Bullet sem evidência defensável deve bloquear.
- Cluster sem evidência defensável não pode ser coberto por keyword forçada.
- Gupy usa apenas `../career-system/references/habilidades_gupy.json`.
- Mercado Livre usa apenas `references/habilidades_mercado_livre.json` de `habilidades-chave`.
- O DOCX final só pode ser entregue após `general-cv:approve` retornar `approved_for_delivery=true`.

## Regras Críticas

- Nunca inventar dados, números, experiências, ferramentas ou certificações.
- Nunca juntar experiências, cargos, promoções ou fases em uma única entrada de CV, em nenhuma circunstância.
- Nunca usar keyword para reposicionamento se ela não tiver evidência real.
- LinkedIn pode ser mais amplo que o CV; o CV deve continuar legível e consistente.
- Em português, preferir equivalentes naturais do `keyword_translation_registry.json` quando a keyword em inglês soar artificial.
- O modo conciso é o padrão de CV; o modo expandido serve apenas quando o usuário pedir bullet points ou versão mais completa.
