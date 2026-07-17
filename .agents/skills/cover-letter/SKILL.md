---
name: cover-letter
description: >
  Gera a carta de apresentação de Felipe Armel seguindo o modelo e diretrizes de diretrizes_carta_de_apresentacao.md.
  Use esta skill SEMPRE que o usuário pedir: "faz a carta", "escreve a carta de apresentação", "carta para essa vaga",
  "cover letter", ou qualquer variação que implique produzir uma carta de candidatura.
  Requer FIT_MAP ativo (career-fit-analysis) quando há vaga específica. Se não houver FIT_MAP, solicitar anúncio
  e executar análise primeiro. Se não houver vaga nem empresa, gerar com placeholders conforme diretrizes.
---

# Cover Letter

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/cover-letter/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/cover-letter/SKILL.md`.

## Adaptação Local OpenCode

Leia também `../career-system/SKILL.md`. Use `.career-state/fit_map.json` como FIT_MAP ativo quando houver vaga e `../career-system/references/diretrizes para carta de apresentação.md` como referência da carta. Após redigir, acione `output-reviewer` antes de entregar.

Gera a carta de apresentação de Felipe Armel. Consome o FIT_MAP da career-fit-analysis para garantir
consistência com CV e FERAS — mesmas histórias, mesmos números, mesmo ângulo narrativo.

---

## PRÉ-REQUISITO

Antes de gerar:

1. Verificar se há anúncio da vaga. Se sim: usar FIT_MAP ativo ou executar career-fit-analysis.
2. Verificar se há dados da empresa (nome, propósito, iniciativas relevantes).
   - Se não houver dados da empresa: solicitar antes de gerar OU manter placeholders.
3. Consultar `diretrizes_carta_de_apresentacao.md` para o modelo exato.

Regra: se não tiver vaga E não tiver empresa → gerar com todos os placeholders preenchíveis.
Se tiver vaga mas não tiver empresa → gerar com dados da vaga e placeholder para empresa.
Se houver dados suficientes para avançar, não parar para perguntas opcionais: escrever e revisar.

---

## MODELO OBRIGATÓRIO

```
Carta de Apresentação — Felipe Armel Dias da Silva

Felipe Armel Dias da Silva
linkedin.com/in/felipearmel
(11) 98674-8218
armelfelipe@gmail.com


Prezada equipe da {Nome-Da-Empresa},

[PARÁGRAFO 1 — ABERTURA COM CONTEXTO E RESULTADO]
Com [X] anos de experiência em {Área-Chave}, tendo resultados como [Resultado-Chave com número],
gostaria de compartilhar meu interesse na posição de {Título-Vaga}.

[PARÁGRAFO 2 — CONEXÃO COM A EMPRESA]
O que me atrai na {Nome-Da-Empresa} é {Propósito-Chave}. Iniciativas como {Iniciativa-Da-Empresa}
mostram um caminho que faz sentido para mim — e é exatamente em {Atividade-Chave} que acredito
poder contribuir de forma mais direta.

[PARÁGRAFO 3 — DIFERENCIAL ESPECÍFICO]
Minha experiência em {Requisito-Chave} — especificamente na {Empresa-Referência}, onde {Resultado
com número} — se conecta diretamente com o que a vaga exige. {Diferencial-Chave}.

[PARÁGRAFO 4 — FECHAMENTO]
Fico à disposição para conversar sobre como minha trajetória pode contribuir para a {Nome-Da-Empresa}.
Segue o currículo em anexo.


Atenciosamente,

Felipe Armel Dias da Silva
```

## MODO DE GERAÇÃO — SELEÇÃO AUTOMÁTICA

Antes de gerar a carta:
- Se o usuário já tiver pedido um modo específico, obedecer ao pedido.
- Se o usuário não tiver especificado modo, usar **modo estruturado** por padrão.
- Não interromper o fluxo para perguntas de preferência quando a intenção já estiver clara.
- Se faltar dado da empresa, continuar com placeholders defensáveis em vez de travar a geração.

---

## PREENCHIMENTO DOS PLACEHOLDERS

Quando houver FIT_MAP ativo, preencher com:

**{Área-Chave}** → área principal da vaga (ex: "operações logísticas", "customer operations", "supply chain")

**{Resultado-Chave}** → `historias_selecionadas.principal.resultado` do FIT_MAP
- Número validado em `perfil_restricoes.md`
- O resultado que mais resolve a dor central da vaga

**{Título-Vaga}** → cargo exato do anúncio

**{Nome-Da-Empresa}** → nome da empresa (solicitar se não fornecido)

**{Propósito-Chave}** → missão/propósito da empresa (pesquisar se necessário)

**{Iniciativa-Da-Empresa}** → produto, projeto ou característica da empresa que ressoa com o perfil
- Pesquisar site/LinkedIn da empresa se não fornecido
- Nunca inventar — se não encontrar, usar placeholder

**{Atividade-Chave}** → a responsabilidade principal da vaga que Armel cobre com maior aderência

**{Stakeholders-Chave}** → quem são os stakeholders relevantes da vaga (clientes, entregadores, parceiros, times de produto etc.)

**{Requisito-Chave}** → o requisito mais importante do anúncio que Armel atende com evidência real

**{Diferencial-Chave}** → o que diferencia Armel especificamente para esta vaga
- Para startups: "construir operações do zero com autonomia real e impacto direto no resultado"
  + narrativa WeHandle como padrão de comportamento
- Para marketplace/logística: "operar em escala com data-driven e saving mensurável"
- Para CX/SaaS: "transformar operações de atendimento com IA e dados gerando eficiência estrutural"

---

## CASAMENTO ANÚNCIO × EXPERIÊNCIAS

Quando o anúncio for fornecido, o Parágrafo 3 deve:
1. Usar keywords exatas do anúncio (da lista `keywords_para_ats` do FIT_MAP)
2. Referenciar a história que resolve a dor central da vaga
3. Conectar explicitamente: "minha experiência em [X] na [Empresa] — onde [resultado com número] —
   se conecta diretamente com [responsabilidade ou desafio da vaga]"

Quando o anúncio NÃO for fornecido:
- Usar competências de maior aderência ao perfil-alvo
- Contar a história no formato narrativo (não lista de bullets)
- Priorizar resultados mais expressivos e defensáveis

---

## NARRATIVA STARTUP (MODO ESPECIAL)

Quando a empresa-alvo for startup, early-stage ou scale-up em construção:
Usar a experiência wehandle no Parágrafo 3 como evidência de capacidade de construção — nunca como justificativa do movimento iFood → wehandle.

Correto: descrever o que foi feito e o resultado gerado.
> "Na wehandle, assumi escopo completo em uma operação que não existia — estruturei suporte, CX e dados do zero, com 30 pessoas, e o resultado foi 15% de impacto na margem bruta. É esse histórico que se conecta diretamente com o desafio da {Nome-Da-Empresa}."

Proibido: mencionar "saí conscientemente", "escolha por autonomia", "impacto percentual maior", "aprendizado mais profundo" — são justificativas que sinalizam a objeção em vez de derrubar com evidência. Objeção se neutraliza com histórias e números, não com explicação de motivação.

---

## CONSISTÊNCIA COM CV E FERAS

- O resultado no Parágrafo 1 é o mesmo `historias_selecionadas.principal.resultado` do FIT_MAP
- O diferencial no Parágrafo 3 usa o mesmo ângulo narrativo definido no FIT_MAP
- As keywords que aparecem na carta são as mesmas do `keywords_para_ats` do FIT_MAP
- Tom consistente com o resumo do CV e o pitch FERAS

---

## CHECKLIST PRÉ-ENTREGA

- [ ] Resultado no P1 tem número validado em `perfil_restricoes.md`?
- [ ] P2 referencia algo real da empresa (não inventado)?
- [ ] P3 usa keyword exata do anúncio?
- [ ] P3 conecta história à dor central da vaga?
- [ ] Para startup: narrativa WeHandle presente no P3?
- [ ] Nenhum placeholder esquecido (se dados disponíveis)?
- [ ] Sem "gestor de CS" para VivaReal?
- [ ] Sem espanhol?
- [ ] Inglês não mencionado como fluente?
- [ ] BSP correto?
- [ ] Tom fluido, narrativo — não lista de conquistas?

---

## REVISÃO OBRIGATÓRIA ANTES DE ENTREGAR

Após redigir a carta e antes de exibir ao usuário, chamar a skill `output-reviewer`:
- Passar o texto completo da carta como input
- Aguardar aprovação (zero falhas de peso total + ≥90% menor peso)
- Executar todas as correções necessárias
- Somente após aprovação: exibir a carta na conversa e/ou gerar arquivo

## BLOCO DE AJUSTES VISÍVEL AO USUÁRIO

```
Carta gerada para: [cargo] — [empresa]

Casamentos anúncio × experiência aplicados:
• P1: resultado "[número]" — conecta à dor "[dor_central]"
• P3: keyword "[termo do anúncio]" → evidência "[história + número]"
• P3: ângulo "[faceta narrativa]" — [motivo]

Dados pesquisados sobre a empresa: [o que foi encontrado / o que ficou como placeholder]

Ajustes narrativos:
• [ajuste 1]
• [ajuste 2]
```

---

## REGRAS CRÍTICAS — NUNCA VIOLAR

- **TOM — regra central:** factual, direto, primeira pessoa real. Proibido: "Espero que estejam bem", "minha paixão por", "me impulsiona a", "estou ansioso para", "acredito que posso fazer a diferença" — todas são frases de formulário ou linguagem de coach. A carta deve soar como um profissional escrevendo, não como um template preenchido.
- Nunca inventar iniciativas, propósitos ou dados da empresa
- Nunca usar resultado não validado em `perfil_restricoes.md`
- Nunca afirmar P&L total
- Nunca "gestor de CS" para VivaReal
- Nunca espanhol
- Inglês "avançado" (nunca "fluente")
- BSP: sempre "MBA Corporate Strategy — BSP Business School São Paulo" (PT)
- WeHandle → iFood: sempre escolha consciente, nunca retrocesso
- Tom narrativo, nunca robotizado ou genérico
