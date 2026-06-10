---
name: feras-pitch
description: >
  Gera o pitch FERAS de Felipe Armel — narrativa em primeira pessoa para pitch oral (~2min),
  resumo de CV/Gupy (500–600 chars) ou seção "Sobre" do LinkedIn.
  Use esta skill SEMPRE que o usuário pedir: "gera o FERAS", "faz o pitch", "escreve o resumo para o Gupy",
  "como me apresento nessa vaga", "me conta minha história para essa vaga", "escreve o Sobre do LinkedIn",
  "como respondo 'me fale sobre você'", ou qualquer variação de pitch ou narrativa de apresentação.
  Requer FIT_MAP ativo (career-fit-analysis). Se não houver FIT_MAP, solicitar anúncio e executar análise primeiro.
---

# FERAS Pitch

## Governança da Skill

Manutenção canônica desta skill: `.opencode/skills/feras-pitch/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.opencode/skills/feras-pitch/SKILL.md`.

## Adaptação Local OpenCode

Leia também `../career-system/SKILL.md`. Use `.career-state/fit_map.json` como FIT_MAP ativo e referências em `../career-system/references/`. Após gerar o texto, acione `output-reviewer` antes de exibir ao usuário.

Metodologia de pitch e narrativa em primeira pessoa. Garante consistência com CV e carta de apresentação
consumindo o FIT_MAP produzido pela career-fit-analysis.

**F** → Formação
**E** → Experiência mais relevante para o cargo
**R** → Resultado relevante para a dor da vaga
**A** → Atualmente — o que busca, nomeando o contexto da empresa-alvo
**S** → Sonhos — ambição profissional com referência a família/independência financeira

---

## PRÉ-REQUISITO OBRIGATÓRIO

Verificar FIT_MAP ativo. Se não houver: solicitar anúncio e executar career-fit-analysis primeiro.

Regra de ouro: cada letra deve ser preenchida com a história de **maior aderência à vaga**,
não a mais impressionante da carreira. O FIT_MAP define isso — nunca ignorar.

---

## CRITÉRIOS DE SELEÇÃO POR LETRA

### F — Formação
- Mencionar apenas se agrega credibilidade para a vaga específica
- Priorizar o que o anúncio pede explicitamente
- Nunca mencionar duas formações se uma enfraquecer a outra
- Para vagas tech/marketplace: ILead FDC ou Green Belt podem ser mencionados brevemente
- Para vagas operacionais: Engenharia Química + MBA Corporate Strategy (BSP)
- Para Gupy/resumo curto: omitir ou 1 linha máximo

### E — Experiência
Escolher por sobreposição de escopo nesta ordem de prioridade:
1. Mesmo contexto de negócio (marketplace, SaaS, logística, fintech)
2. Mesmo escopo de função (operations, CS, supply chain, planning)
3. Mesmo estágio da empresa (startup, scale-up, corporativo)
4. Mais recente ganha o desempate

Usar `historias_selecionadas.principal` do FIT_MAP. Nunca sobrescrever com julgamento próprio.

### R — Resultado
- Escolher o que resolve a dor central da vaga (campo `dor_central` do FIT_MAP)
- Número obrigatório — validado em `perfil_restricoes.md` seção NÚMEROS CRÍTICOS
- O resultado mais aderente à vaga em primeiro
- O segundo resultado como prova de escala ou amplitude

Exemplos de âncora por tipo de vaga:
- Logística/marketplace → saving R$70M/ano (iFood) + expansão 400→800 cidades
- CX/SaaS → CSAT 85%→92% + custo por atendimento −13% (WeHandle)
- Supply Chain → GGF −R$8M + faturamento R$80M→R$120M (Trifil)
- Construção/startup → 15% margem bruta (WeHandle) + área CS do zero para 91 pessoas (VivaReal)

### A — Atualmente
- Nomear o contexto específico da empresa-alvo (não só o cargo genérico)
- Para startups early-stage: usar a experiência wehandle como evidência de capacidade de construção — nunca como justificativa do movimento iFood → wehandle
  → Correto: descrever o que foi feito e o resultado. "Na wehandle, assumi escopo completo em uma operação que não existia — criei as áreas, contratei a liderança, estruturei os processos. O resultado foi 15% de impacto na margem bruta. Esse histórico de construção é o que me traz até [empresa-alvo]."
  → Proibido: explicar por que saiu do iFood, mencionar "escolha consciente", "autonomia", "impacto percentual maior" — são justificativas que levantam a objeção em vez de derrubar com evidência
- Para empresas estabelecidas: governança, escala, interface com C-level

### S — Sonhos
- Para startups: construir, impactar, autonomia, legado
- Para corporativo: ser referência em liderança em escala, impacto no negócio
- Sempre fechar com referência a família/independência financeira (pitch oral) ou adaptar ao espaço (escrito)

---

## FORMATOS DE SAÍDA

### Pitch oral (~2 minutos)
- Abertura: direta, sem fórmula — começar pelo que é relevante para o interlocutor, não por protocolo
  - Exemplos defensáveis: apresentar formação + contexto de carreira em 1 frase, ou já entrar na experiência mais relevante
  - Nunca usar "Como você deve ter visto no meu LinkedIn" — artificial e desnecessário
- Fechamento: referência a ambição e família quando o contexto permitir — nunca forçar se soar artificial
- Tom: primeira pessoa, factual, narrativo — nunca lista de conquistas, nunca frases de efeito
- Regra de ouro de tom: um executivo sênior conta o que fez com precisão e confiança. O resultado fala por si. Sem autoproclamação, sem linguagem de coach.
- Entrega obrigatória em **duas camadas**:
  1. `FERAS estruturado` — com `F`, `E`, `R`, `A`, `S` separados para inspeção lógica.
  2. `Pitch fluido para fala/leitura` — em parágrafos naturais, sem rótulos `F/E/R/A/S`, sem barras, sem sensação de checklist.
- A versão fluida deve conectar as partes com transições reais entre formação, trajetória, resultado, aderência e motivação. Ela precisa soar falável, não como colagem de bullet points.
- Estrutura: F (1 frase) → E (2–3 frases contexto + escopo) → R (2 resultados com número) →
  A (1–2 frases nomeando empresa) → S (1–2 frases, fechar com ambição/família quando couber)
- Keywords: incorporar naturalmente **3 a 5 keywords de maior valor** do FIT_MAP, priorizando termos ligados a requisitos críticos da vaga. Não tentar cobrir tudo; naturalidade e defensabilidade prevalecem sobre volume.
- Auditoria obrigatória ao final:
  - `Keywords incorporadas naturalmente` — listar as keywords realmente refletidas no texto.
  - `Keywords relevantes não usadas` — listar as principais omitidas e justificar brevemente por que ficaram fora do FERAS.

### Resumo CV / Gupy (500–600 caracteres)
- Sem abertura com LinkedIn
- Sem fechamento com família (ou adaptar em 1 frase se couber)
- Formato denso: cada palavra conta
- Incluir 2–3 keywords críticas do FIT_MAP
- Estrutura: [F resumido] + [E com escopo] + [R com número] + [A nomeando empresa/contexto]

### Sobre LinkedIn / Perfil LinkedIn
- Seguir modelo semelhante ao CV, em **4 a 8 bullet points**.
- Ler `.career-state/derived/keyword_ats_registry.json` quando existir.
- Priorizar keywords com `status = covered_cv` e `linkedin_use = recommended`.
- Cada bullet deve combinar: keyword/capacidade + escopo real + número validado.
- Não usar keyword marcada como `gap`.
- Não gerar texto em parágrafos longos, exceto se o usuário pedir explicitamente.
- Estrutura recomendada:
  1. Headline/posicionamento curto
  2. 4 a 8 bullets com capacidades e resultados
  3. Fechamento curto de ambição, sem linguagem de coach
  4. O que busco (A calibrado)
  5. Ambição + família (S)

---

## CHECKLIST PRÉ-ENTREGA — OBRIGATÓRIO

- [ ] O **E** escolhido é o de maior sobreposição com a vaga (não o mais impressionante)?
- [ ] O **R** resolve a dor central da vaga com número defensável de `perfil_restricoes.md`?
- [ ] O **R** mais aderente está em primeiro; o segundo funciona como prova de escala?
- [ ] O **A** nomeia o contexto da empresa-alvo, não só o cargo genérico?
- [ ] Para startups: narrativa de escolha por construção (WeHandle como padrão) está presente?
- [ ] O **S** está calibrado para a cultura da empresa?
- [ ] A narrativa flui em primeira pessoa como história (não lista de conquistas)?
- [ ] Pitch oral: entrega **FERAS estruturado** e **pitch fluido para fala/leitura**?
- [ ] Pitch oral: a versão fluida não expõe rótulos `F/E/R/A/S`, barras ou costuras mecânicas?
- [ ] Pitch oral: fecha com ambição/família quando isso couber ao contexto?
- [ ] Resumo escrito: dentro do limite de caracteres sem perder F-E-R-A-S?
- [ ] Keywords críticas do FIT_MAP aparecem naturalmente no texto, com foco em requisitos da vaga?
- [ ] Pitch oral: há auditoria explícita de `Keywords incorporadas naturalmente` e `Keywords relevantes não usadas`?
- [ ] Para LinkedIn: 4 a 8 bullets, usando keywords cobertas no CV e sem keywords marcadas como gap no registry?
- [ ] Números validados contra `perfil_restricoes.md`?

---

## CONSISTÊNCIA COM CV E CARTA

As histórias usadas no FERAS são as mesmas do FIT_MAP (`historias_selecionadas`).
Os números são idênticos aos do CV.
O ângulo narrativo de cada história é o mesmo nos três documentos.
A dor central norteia o tom e a seleção em todos os formatos.

---

## REGRAS CRÍTICAS — NUNCA VIOLAR

- **TOM — regra central:** narrativa factual em primeira pessoa. Um executivo sênior conta o que fez com precisão e confiança. O resultado fala por si. Proibido: frases de efeito, autoproclamação, linguagem de coach ("sou o que transforma", "minha paixão por", "me impulsiona a", "tenho vocação para"). Permitido: fatos, números, contexto, consequência.
- Nunca usar o resultado mais impressionante se não for o mais aderente à vaga
- Nunca posicionar WeHandle → iFood como retrocesso — sempre escolha consciente
- Nunca afirmar P&L total — usar alavanca operacional real
- Nunca "gestor de CS" para VivaReal — sempre "arquiteto da área"
- Nunca declarar espanhol
- Inglês: sempre "avançado" (nunca "fluente") — mencionar apenas se relevante para a vaga
- BSP: "MBA Corporate Strategy — BSP Business School São Paulo" (PT) /
  "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo" (EN)
- Nunca inventar dados, escopo, ferramentas ou certificações
- Números: sempre validados em `perfil_restricoes.md`

---

## REVISÃO OBRIGATÓRIA ANTES DE ENTREGAR

Após gerar o pitch/resumo e antes de exibir ao usuário, chamar a skill `output-reviewer`:
- Passar o texto completo do FERAS como input
- Aguardar aprovação (zero falhas de peso total + ≥90% menor peso)
- Executar todas as correções necessárias
- Somente após aprovação: exibir na conversa

## BLOCO DE AJUSTES VISÍVEL AO USUÁRIO

Após gerar o FERAS, exibir:

```
FERAS gerado para: [cargo] — [empresa]
Formato: [pitch oral / resumo Gupy / Sobre LinkedIn]

Quando o formato for pitch oral:
1. FERAS estruturado
2. Pitch fluido para fala/leitura
3. Keywords incorporadas naturalmente
4. Keywords relevantes não usadas e justificativa

Seleções feitas:
• F: [o que foi mencionado e por quê]
• E: [experiência escolhida] — [critério de seleção]
• R: [resultado 1] + [resultado 2] — [como resolve a dor central]
• A: [como a empresa foi nomeada] — [startup ou corporativo]
• S: [calibração cultural]

Ajustes narrativos:
• [ajuste 1 — ex: narrativa WeHandle ativada]
• [ajuste 2 — ex: ângulo X reposicionado]
```
