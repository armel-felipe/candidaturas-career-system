# Documentação do Projeto — Sistema de Busca de Emprego Executivo
**Felipe Armel Dias da Silva**
*Versão: maio/2026*

---

## O QUE É ESTE PROJETO

Este é um sistema automatizado de candidatura a vagas executivas (Head, Diretor, C-level) construído dentro do Claude.ai como um "projeto" — um ambiente com memória persistente, arquivos de referência e skills instaladas que funcionam como sub-rotinas especializadas.

O objetivo central é garantir que **todos os documentos gerados em uma candidatura sejam consistentes entre si**: o CV, o pitch oral, a carta de apresentação e o resumo na plataforma Gupy falam com as mesmas histórias, os mesmos números e o mesmo ângulo narrativo.

---

## ESTRUTURA GERAL — VISÃO DO TOPO

```
ENTRADA: Anúncio de vaga colado pelo usuário
         ↓
ANÁLISE: career-fit-analysis → produz o FIT_MAP (mapa interno de aderência)
         ↓
PRODUÇÃO (paralela ou sequencial, conforme necessidade):
  ├── cv-generator     → CV em DOCX ou PDF
  ├── feras-pitch      → Pitch oral / resumo Gupy / Sobre LinkedIn
  ├── cover-letter     → Carta de apresentação
  ├── habilidades-chave → habilidades ranqueadas + resumo para plataforma ATS
  └── networking-message → Mensagem de abordagem no LinkedIn
         ↓
REVISÃO: output-reviewer → valida TODOS os documentos antes da entrega
         ↓
SAÍDA: Arquivos entregues ao usuário (present_files)
```

O **FIT_MAP** é o elemento central do sistema. É um mapa de aderência interno construído pela skill `career-fit-analysis` e consumido por todas as outras skills. Sem ele, nenhum documento de candidatura é gerado.

---

## OS ARQUIVOS DE REFERÊNCIA

Estes arquivos são a "memória de longo prazo" do projeto. Nenhum dado é inventado — qualquer bullet, número ou narrativa precisa ter correspondência em ao menos um deles.

### `autoconhecimento.md`
**O quê:** Diário completo da carreira do Felipe, de 1998 a 2026. Contém todas as responsabilidades, escopos, times, ferramentas e resultados — empresa por empresa, cargo por cargo.
**Quando é usado:** É a fonte primária de validação. Toda vez que um número ou contexto precisa ser confirmado, este é o arquivo consultado. Nenhuma data de experiência pode ser usada sem antes ler este arquivo — é uma regra de peso total.

### `palavras_chave_carreira.md`
**O quê:** Índice organizado por tema (Liderança, Planejamento, Logística, Dados, etc.) que mostra, para cada palavra-chave, qual empresa, qual cargo e qual história a sustenta. A Seção 15 é o "painel de métricas" — todos os números quantitativos defensáveis da carreira.
**Quando é usado:** É o primeiro lugar que a skill `career-fit-analysis` consulta ao cruzar os termos da vaga com o perfil. Também guia a construção de bullets no CV.

### `dicionario_palavras_chave_mercado.md`
**O quê:** Dicionário de tradução entre o vocabulário das vagas e a base de conhecimento real.
- **Seção 1 — Pode usar:** termos com evidência defensável + frase pronta para o CV
- **Seção 2 — Não pode usar:** termos que aparecem em vagas mas não têm experiência real
- **Seção 3 — Sinônimos validados:** quando a vaga usa um termo e o CV usa outro (ex: "AHT" = "TME"), indica qual versão usar conforme o idioma do CV
**Quando é usado:** Toda vez que uma keyword da vaga precisa ser cruzada com a experiência real. Nenhum bullet é escrito sem consultar este dicionário.

### `perfil_restricoes.md`
**O quê:** Arquivo de regras fixas do candidato. Contém:
- Dados de contato e perfil geral
- **Números críticos** — os valores exatos que nunca podem ser alterados (ex: WeHandle margem bruta = 15%, iFood saving = R$70MM/ano)
- **Narrativas protegidas** — histórias que têm uma forma certa e uma forma errada de ser contadas (ex: VivaReal CS = "arquiteto da área", nunca "gestor")
- **Seleção de experiências por tipo de CV** — qual ordem de empresas usar para cada posicionamento
**Quando é usado:** Como checklist final antes de gerar qualquer documento. O `output-reviewer` também o consulta na revisão.

### `diretrizes_carta_de_apresentacao.md`
**O quê:** Template e regras da carta de apresentação — estrutura de 4 parágrafos, tom proibido, modo de geração (estruturado ou fluido).
**Quando é usado:** Exclusivamente pela skill `cover-letter`.

### `habilidades_gupy.json`

**O quê:** Lista das 30 habilidades disponíveis para seleção na plataforma Gupy (campo `habilidades`). O sistema só pode escolher habilidades que existam neste arquivo.
**Quando é usado:** Pela skill `habilidades-chave` no modo Gupy. Ler o arquivo antes de selecionar — nunca usar lista de memória.

### `habilidades_mercado_livre.json`

**O quê:** Catálogo derivado da imagem de habilidades anexada pelo usuário. A skill usa esta lista como fonte fechada quando o pedido for do tipo "traga x habilidades mercado livre".
**Quando é usado:** Pela skill `habilidades-chave` no modo Mercado Livre.

### `competencias_matrix.json` e `competencias_por_experiencia.json`

**O quê:** Mapeamento de competências em JSON — `competencias_matrix.json` é a matriz amplitude da carreira (53 competências × 16 experiências com evidências marcadas); `competencias_por_experiencia.json` é o refinamento com top competências por experiência.
**Quando é usado:** Em análises comparativas de competências e quando o usuário pede diagnóstico de aderência por perfil de mercado.

### `competencias_linkedin.json`

**O quê:** Lista de 85 habilidades do perfil LinkedIn, com status `ativo` (true = já marcado no perfil).
**Quando é usado:** Quando o usuário pede para atualizar ou consultar as habilidades do LinkedIn.

---

## AS SKILLS — O QUE CADA UMA FAZ

As skills são "rotinas instaladas" que o sistema executa quando acionadas. Cada uma tem seu arquivo `SKILL.md` que deve ser **lido antes da execução** — é uma regra inviolável, porque as skills são atualizadas com frequência.

---

### SKILL 1 — `career-fit-analysis`
**Papel:** Pré-requisito obrigatório de todas as outras skills de candidatura. Produz o FIT_MAP.

**Quando acionar:**
- Usuário cola ou descreve uma vaga para análise
- Pede "analisa essa vaga", "como me encaixo", "qual meu fit"
- Solicita CV, pitch, carta ou seleção Gupy (a análise vem antes de qualquer documento)
- Quer saber quais cargos são mais aderentes ao perfil
- Quer construir posicionamento para um cargo novo

**3 modos de operação:**

**Modo 1 — Vaga específica (mais comum)**
O usuário cola o anúncio. A skill executa 8 passos em sequência:

1. **Extração dupla:** separa "keywords" (termos para o ATS detectar) de "competências" (o que a vaga exige que o candidato saiba fazer). São listas diferentes.
2. **Dor central:** identifica em 1–2 frases o problema principal que a empresa quer resolver contratando essa posição. Essa frase norteia tudo que vem depois.
3. **Cruzamento com a base:** para cada keyword e competência extraída, consulta os 4 arquivos de referência em ordem e classifica como:
   - **DIRETO** — Felipe tem a experiência exata, usa a frase pronta do dicionário
   - **REPOSICIONAMENTO** — Felipe tem a experiência, mas o ângulo precisa mudar para ressoar com a dor da vaga
   - **GAP** — não há experiência defensável; o gap é declarado, nunca coberto com narrativa forçada
4. **Conexão com a dor:** para cada história selecionada, constrói a ponte: "esta experiência resolve a dor X porque Y, usando a keyword Z".
5. **Objeções:** identifica 3–5 objeções que o recrutador vai levantar, classifica (forte/média/fraca) e propõe mitigação com evidência real. Objeções recorrentes do perfil: gap de senioridade iFood→WeHandle, amplitude excessiva da carreira, inglês não fluente, educação formal sem universidade de ponta.
6. **Nota de aderência:** calcula a nota 0–10 em 4 dimensões com pesos fixos:
   - Requisitos obrigatórios (40%)
   - Responsabilidades principais (30%)
   - Ausência de gaps críticos (20%)
   - Diferenciais/desejáveis (10%)
   Cada item recebe 1,0 (cobertura plena), 0,5 (parcial/reposicionamento) ou 0,0 (gap). O cálculo é detalhado e mostrado item a item — nunca estimado.
7. **Seleção de histórias:** escolhe as 3 histórias principais para CV, FERAS e carta, com base em sobreposição com a dor central, número mais defensável e cobertura das keywords mais críticas.
8. **Montagem do FIT_MAP:** estrutura interna com todos os dados acima, que será consumida pelas demais skills.

**Modo 2 — Pesquisa de mercado (sem vaga)**
Quando o usuário quer saber quais cargos são mais aderentes ao seu perfil sem uma vaga específica. A skill busca vagas no tracker do Notion e pesquisa na web por vagas dos perfis-alvo (Head/Diretor de Operações Logísticas, Head de Customer/SaaS Operations, etc.) e entrega por cargo: fit atual, o que Felipe tem, o que falta, keywords cobertas/sem cobertura.

**Modo 3 — Perfil reverso**
Quando o usuário quer construir posicionamento para um cargo novo. A skill pesquisa vagas reais desse cargo, extrai competências e keywords mais frequentes, propõe um mapa para validação do usuário — e só após validação gera qualquer documento.

**O que aparece para o usuário:** dor central, tabela de aderência com cálculo detalhado, ajustes narrativos aplicados, gaps sem cobertura, objeções do recrutador, lista de 15 keywords para ATS, próximos passos sugeridos.

---

### SKILL 2 — `cv-generator`
**Papel:** Gera o CV em DOCX ou PDF, consumindo o FIT_MAP.

**Quando acionar:** Usuário pede "gera o CV", "faz o currículo", "adapta o CV para essa vaga".

**Fluxo de execução:**

**Pré-requisito:** verificar FIT_MAP ativo. Se não houver, executar `career-fit-analysis` primeiro. Antes de qualquer coisa, perguntar: **DOCX ou PDF?** — nunca assumir formato.

**Seleção de persona:** com base na dor central e nas histórias selecionadas do FIT_MAP, a skill determina qual persona (combinação de experiências e ordem) melhor atende a vaga:

| Persona | Foco | Ordem das experiências |
|---|---|---|
| A — Logística/Marketplace | iFood, Trifil, WeHandle | iFood Diretor → iFood Head → Trifil → WeHandle |
| B — SaaS/CX/Fintech | WeHandle, iFood, VivaReal | WeHandle → iFood Diretor → VivaReal → iFood Head |
| C — Supply Chain/Planning | iFood, Trifil S&OP | iFood Diretor → Trifil S&OP → Trifil Expedição |
| Startup/early-stage | WeHandle na frente | WeHandle → iFood Diretor → iFood Head → Trifil |

A ordem dentro do CV é sempre **cronológica inversa** — a mais recente primeiro. A seleção de quais experiências incluir é guiada pelo FIT_MAP.

**Regra fixa de experiências:** não juntar experiências, cargos, promoções, fases ou escopos em uma única entrada de CV. Quando houver limite de espaço, a decisão é selecionar/cortar experiências separadas por aderência, nunca consolidar.

**Estrutura do CV:**
- **Cabeçalho fixo:** nome, LinkedIn, cidade, telefone, e-mail — nunca centralizado, nunca emojis, um dado por linha
- **Resumo:** máximo 480 caracteres, factual, primeira pessoa real. Abre com "Executivo Sênior" ou "Gerente Sênior", fecha com "Busco posição de X". Proibido: frases de efeito, linguagem de coach, autoproclamação.
- **Experiência — modo conciso, padrão de escrita:**
  - Bullet 1 "Fui responsável por": escopo + time + elemento mais relevante para a vaga em destaque
  - Bullet 2 "Utilizando": somente as ferramentas/competências que explicam diretamente o resultado. Máximo 3 itens.
  - Bullet 3 "Consegui": resultado com número — obrigatório. Sem número, bullet é inválido.
- **Experiência — modo expandido / não conciso:**
  - 1 bullet de síntese da história da experiência como um todo
  - 3 a X bullets de entregas, conforme número especificado pelo usuário
  - entregas ordenadas por aderência à vaga, cobrindo dor central, requisitos, objeções e keywords ATS
  - cada entrega deve ter evidência real e, sempre que possível, número defensável
- **Formação:** cronológica inversa, apenas o que agrega para a vaga
- **Stack técnica:** filtrada pelo FIT_MAP — somente o que é relevante para a vaga
- **Idiomas:** Português Nativo, Inglês Avançado — nunca "Fluente", nunca espanhol

**Pipeline de geração DOCX (6 passos obrigatórios, em ordem):**
1. Escrever script Node.js usando a biblioteca `docx` (npm)
2. Executar o script e verificar que rodou sem erros
3. Validar o arquivo gerado com `validate.py`
4. Desempacotar o DOCX e injetar o tema Arial (via `theme1.xml`)
5. Reempacotar com `pack.py --original`
6. Chamar `output-reviewer` antes de entregar

**Regra crítica de fonte:** `pt = n * 2` (half-points). 9pt = 18, 12pt = 24. Usar `n * 20` é erro grave (twips em vez de half-points).

**Para PDF:** gerar DOCX primeiro, converter com LibreOffice, entregar o PDF.

**Nomenclatura obrigatória de arquivo:**
```
felipe_armel_cv_[cargo]_[empresa].docx
felipe_armel_cv_[cargo]_[empresa]_en.docx   ← quando em inglês
```
Nunca nomes genéricos como `cv_final.docx`.

Após entrega: chamar `output-reviewer`. Exibir bloco de ajustes narrativos aplicados e keywords cobertas/não cobertas.

---

### SKILL 3 — `feras-pitch`
**Papel:** Gera a narrativa de apresentação pessoal — pitch oral (~2 min), resumo para Gupy (500–600 chars) ou seção "Sobre" do LinkedIn.

**Quando acionar:** "gera o FERAS", "faz o pitch", "como me apresento", "me fale sobre você", "resumo para o Gupy", "escreve o Sobre do LinkedIn".

**O que é o FERAS:**
Metodologia de pitch estruturada em 5 letras:
- **F** — Formação (só se agrega credibilidade para a vaga específica)
- **E** — Experiência mais relevante para o cargo (não a mais impressionante — a mais aderente à dor central)
- **R** — Resultado relevante para a dor da vaga (número obrigatório, validado em `perfil_restricoes.md`)
- **A** — Atualmente — o que busca, nomeando o contexto da empresa-alvo
- **S** — Sonhos — ambição profissional com referência a família/independência financeira

A seleção de qual experiência e qual resultado usar é ditada pelo `historias_selecionadas.principal` do FIT_MAP — nunca pela preferência do sistema.

**3 formatos de saída:**
- **Pitch oral completo:** ~2 minutos, todas as 5 letras, tom conversacional, com marcadores de pausa
- **Resumo de CV/Gupy:** 500–600 chars, direto, sem saudação, apenas F+E+R condensados
- **Seção Sobre do LinkedIn:** 3–5 parágrafos — quem sou / trajetória com número / como opero / ambição

Após geração: chamar `output-reviewer` antes de exibir ao usuário.

---

### SKILL 4 — `cover-letter`
**Papel:** Gera a carta de apresentação seguindo o modelo e tom das `diretrizes_carta_de_apresentacao.md`.

**Quando acionar:** "faz a carta", "carta de apresentação", "cover letter".

**Pré-requisito:** FIT_MAP ativo quando há vaga. Sem vaga e sem empresa: gerar com placeholders.

**Antes de gerar, sempre perguntar:** modo **estruturado** (segue os 4 blocos do template) ou **fluido** (mesma lógica, escrita corrida sem divisão rígida)?

**Estrutura da carta (4 parágrafos):**
1. **Abertura:** anos de experiência + resultado-chave com número + interesse na posição
2. **Conexão com a empresa:** o que atrai na empresa + iniciativa relevante + onde pode contribuir
3. **Evidência:** competência exigida pela vaga + empresa de referência + resultado com número + diferencial
4. **Fechamento:** disponibilidade para conversa + CV em anexo

**Tom proibido em qualquer parte da carta:**
- "Espero que estejam bem"
- "minha paixão por"
- "me impulsiona a"
- "estou ansioso para contribuir"
- "acredito que posso fazer a diferença"
- qualquer frase que soe a formulário de RH ou linguagem de coach

Após geração: chamar `output-reviewer` antes de entregar.

---

### SKILL 5 — `habilidades-chave`
**Papel:** Seleciona e ranqueia habilidades defensáveis para catálogos externos ou Gupy, sempre ligando cada habilidade a cargo, empresa e história única. Quando pedido, também gera resumo ATS de 500–600 chars.

**Quando acionar:** usuário menciona Gupy, pede seleção de habilidades, pede resumo para plataforma ATS ou pede algo como "traga x habilidades mercado livre".

**Pré-requisito:** FIT_MAP ativo.

**Parte 1 — Seleção de 10 habilidades:**
No modo Gupy, usa exclusivamente as 30 habilidades disponíveis em `habilidades_gupy.json` e seleciona exatamente 10. No modo Mercado Livre, usa exclusivamente `habilidades_mercado_livre.json` e respeita a quantidade pedida pelo usuário. Em ambos os casos, cada habilidade precisa ser defendida por uma história própria, sem repetição de núcleo narrativo.

**Parte 2 — Resumo ATS:**
500–600 caracteres. Tom direto, factual. Não é uma cópia do resumo do CV — é otimizado para o algoritmo da plataforma. Contém as keywords mais críticas da vaga de forma natural.

Após geração: chamar `output-reviewer`.

---

### SKILL 6 — `output-reviewer`
**Papel:** Revisora automática de qualidade. Roda obrigatoriamente após toda skill de produção, antes de qualquer entrega ao usuário. É o "portão de qualidade" do sistema.

**Quando acionar:** automaticamente após `cv-generator`, `cover-letter`, `feras-pitch` e `habilidades-chave`. Também quando o usuário pede "revisa o CV", "confere a carta", "está bom?".

**2 categorias de critérios:**

**Peso total — qualquer falha bloqueia a entrega:**
- Datas extraídas de `autoconhecimento.md` (nunca de memória ou sessão anterior)
- As 8 keywords de maior prioridade do FIT_MAP aparecem como termos exatos no CV
- Todos os números validados contra `perfil_restricoes.md` seção NÚMEROS CRÍTICOS
- Narrativas protegidas: VivaReal CS = "arquiteto da área", fill rate = Trifil, margem bruta WeHandle = 15%, saving iFood = R$70MM/ano, budget iFood = R$300MM/ano
- Tom: sem frases de efeito, sem linguagem de coach, sem formulário de RH
- Movimento iFood→WeHandle: apresentado pelos fatos (o que foi feito, com quantas pessoas, qual resultado) — nunca por justificativa motivacional

**Menor peso — tolerância até 10% de falhas:**
- Keywords do FIT_MAP aparecem naturalmente (sem forçar)
- Ordem de resultados no bullet "Consegui" prioriza o mais relevante para a vaga
- Resumo dentro do limite de caracteres
- Stack técnica filtrada para a vaga
- Cobertura dos ativos obrigatórios: budget, saving, escala, criação de área, interface C-level

**Fluxo:** avalia peso total → se houver falha, corrige e reavalia (sem limite de rodadas) → avalia menor peso → se < 90%, corrige e reavalia → somente após aprovação em ambos, chama `present_files`.

**O que aparece para o usuário:** bloco de revisão com critérios aprovados, taxa de aprovação e lista de correções executadas.

---

### SKILL 7 — `networking-message`
**Papel:** Gera mensagens de LinkedIn personalizadas para abordagem de recrutadores, gestores ou pares.

**Quando acionar:** "escreve a mensagem de networking", "mensagem para o recrutador", "mensagem para o gestor", "quero me conectar com alguém dessa vaga", "faz a nota de conexão".

**Pré-requisito:** sempre perguntar o perfil do destinatário antes de gerar (recrutador de RH / gestor direto da vaga / par/colega da empresa). Usa FIT_MAP quando disponível.

**4 templates base:**
1. **Inscrevi na vaga — RH:** confirma candidatura, pergunta se é responsável pela vaga, oferece mais informações
2. **Inscrevi na vaga — Gestor:** confirma candidatura, sinaliza interesse em chegar à etapa de entrevista
3. **Inscrevi na vaga — Pares:** confirma candidatura, pede indicação de quem é o responsável pela vaga
4. **Gostei da empresa — geral:** networking proativo sem vaga específica, com gancho de resultado relevante

**Tom:** natural, fluido, humano. Fechamento sempre aberto e conversacional, nunca uma pergunta direta e pressionante. O limite de caracteres é sempre especificado pelo usuário — nunca imposto pelo sistema.

---

## O FLUXO COMPLETO — CANDIDATURA PASSO A PASSO

Quando o usuário cola uma vaga e quer todos os materiais, o sistema executa nesta ordem:

```
PASSO 1: career-fit-analysis
         ↓ produz FIT_MAP com: dor central, mapa de aderência, nota, objeções,
           3 histórias selecionadas, 15 keywords para ATS

PASSO 2: cv-generator
         ↓ consome FIT_MAP → seleciona persona → escreve CV
         ↓ pipeline DOCX: script → execução → validação → theme Arial → reempacotamento
         ↓ output-reviewer: verifica todos os critérios → corrige até aprovação
         ↓ present_files → arquivo entregue ao usuário

PASSO 3: feras-pitch
         ↓ consome FIT_MAP → seleciona formato (oral / resumo Gupy / LinkedIn)
         ↓ preenche FERAS com histórias do FIT_MAP
         ↓ output-reviewer → aprovação → exibe ao usuário

PASSO 4: cover-letter
         ↓ pergunta modo (estruturado ou fluido)
         ↓ consome FIT_MAP → preenche 4 parágrafos do template
         ↓ output-reviewer → aprovação → entrega

PASSO 5: habilidades-chave
         ↓ consome FIT_MAP → seleciona habilidades do catálogo ativo (`habilidades_gupy.json` ou `habilidades_mercado_livre.json`)
         ↓ gera resumo ATS 500–600 chars
         ↓ output-reviewer → aprovação → exibe ao usuário

PASSO 6: networking-message
         ↓ pergunta perfil do destinatário
         ↓ consome FIT_MAP → adapta template ao contexto da vaga
         ↓ entrega mensagem com limite de caracteres especificado pelo usuário
```

**Todos os passos usam as mesmas 3 histórias, os mesmos números e o mesmo ângulo narrativo** — garantido pelo FIT_MAP compartilhado.

---

## REGRAS QUE NUNCA MUDAM

Estas regras são aplicadas em todo e qualquer documento gerado:

### Números críticos — nunca alterar
| Empresa | Métrica | Valor correto |
|---|---|---|
| WeHandle | Impacto na margem bruta | **15%** |
| WeHandle | Custo por atendimento | R$ 4,14 → R$ 3,61 (−13%) |
| iFood | Saving simulador | **R$ 70 MM/ano** |
| iFood | Budget OPEX logístico | **R$ 300 MM/ano** |
| iFood | Cobertura geográfica | **400 → 800 cidades** |
| iFood | Indisponibilidade de frota | **5% → 0,5%** |
| VivaReal | Conversão SDR inbound | **18% → 50%** |
| VivaReal | Área de CS escalada para | **91 pessoas** |
| Trifil | Redução de GGF | **R$ 8 MM** |
| Trifil | Faturamento | **R$ 80 MM → R$ 120 MM/ano** |

### Narrativas protegidas
- **VivaReal CS:** sempre "arquiteto da área", nunca "gestor de CS"
- **iFood → WeHandle:** apresentar pelos fatos (escopo, time, resultado), nunca por justificativa motivacional nos documentos escritos. O tema é tratado oralmente na entrevista.
- **P&L total:** nunca afirmar responsabilidade total. Usar sempre a alavanca real: custo logístico, margem bruta, OPEX, eficiência operacional.
- **Fill rate:** pertence à Trifil — nunca atribuir à VivaReal
- **Inglês:** sempre "Avançado" — nunca "Fluente"
- **Espanhol:** nunca incluir como competência
- **BSP em português:** "MBA Corporate Strategy — BSP Business School São Paulo"
- **BSP em inglês:** "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo" — nunca "MBA in Corporate Strategy"
- **wehandle:** sempre em minúsculas — nunca "WeHandle", "Wehandle" ou qualquer variante

### Tom proibido em qualquer documento
- Frases de efeito: "sou o que transforma", "conecto planejamento, execução e resultado"
- Linguagem de coach: "minha paixão por", "me impulsiona a", "estou ansioso para"
- Formulário de RH: "Espero que estejam bem", "Obrigado pela consideração"
- Justificativa no lugar de evidência

### Regras técnicas — DOCX
- Fonte: `pt = n * 2` (half-points). 9pt = 18, 12pt = 24. **Nunca** `n * 20`.
- Pipeline DOCX: sempre 6 passos em ordem — nunca pular validação nem injeção de tema
- Nomes de arquivo: sempre `felipe_armel_cv_[cargo]_[empresa].[ext]` — nunca nomes genéricos
- Datas de experiência: sempre lidas de `autoconhecimento.md` imediatamente antes da geração — nunca de memória ou sessão anterior

---

## COMO O SISTEMA DECIDE O QUE FAZER

O sistema usa gatilhos linguísticos para identificar qual skill acionar. Abaixo os principais:

| O que o usuário diz | Skill acionada |
|---|---|
| "analisa essa vaga" / cola anúncio | `career-fit-analysis` |
| "gera o CV" / "adapta o currículo" | `career-fit-analysis` → `cv-generator` |
| "faz o pitch" / "me fale sobre você" / "FERAS" | `career-fit-analysis` → `feras-pitch` |
| "faz a carta" / "cover letter" | `career-fit-analysis` → `cover-letter` |
| "seleciona habilidades" / "resumo para Gupy" / "traga x habilidades mercado livre" | `career-fit-analysis` → `habilidades-chave` |
| "escreve a mensagem de networking" | `networking-message` |
| "revisa o CV" / "confere a carta" / "está bom?" | `output-reviewer` |
| "quais vagas combinam comigo" | `career-fit-analysis` (Modo 2) |
| "como me posiciono para o cargo X" | `career-fit-analysis` (Modo 3) |

**Regra de execução:** antes de executar qualquer skill, o sistema **deve** ler o arquivo `SKILL.md` correspondente via ferramenta `view`. Nunca executa de memória. Se começar a executar sem ter feito a leitura, deve interromper, ler o arquivo e reiniciar.

---

## O QUE O SISTEMA NUNCA FAZ

- Inventar experiências, escopos, ferramentas, certificações ou números que não existem na base
- Cobrir um gap com narrativa forçada — gap é declarado com clareza
- Gerar qualquer documento de candidatura sem FIT_MAP ativo
- Entregar qualquer documento sem aprovação do `output-reviewer`
- Usar dados de memória ou de sessão anterior sem validar em `autoconhecimento.md`
- Afirmar responsabilidade total por P&L
- Declarar espanhol como competência
- Declarar inglês como "Fluente"
- Atribuir fill rate à VivaReal
- Posicionar VivaReal CS como "gestão"
- Usar `n * 20` para tamanho de fonte em DOCX

---

## TRACKER DE CANDIDATURAS — NOTION

O projeto se conecta ao banco de dados "Aplicações" no Notion por scripts locais, nunca por MCP. A skill operacional é `.opencode/skills/notion-transactions/SKILL.md`, e a implementação canônica fica em `scripts/notion_sync.py`, `scripts/notion_query.py` e nos comandos `npm run notion:*`. Cada vaga tem um registro com ID numérico no campo único `ID`.

**Regra operacional:** quando precisar avaliar/analisar uma vaga específica, usar `npm run intake:notion-record -- <id_unico>`. Para leitura simples, criação, atualização de descrição, atualização de FIT_MAP ou sincronização de histórico, seguir `.opencode/skills/notion-transactions/SKILL.md`. Não ler `.env`, não copiar `NOTION_TOKEN`, não fazer `curl` manual e não chamar endpoints do Notion diretamente.

Toda vaga específica entra pelo orquestrador `intake:*`, que salva a descrição, registra `active_intake`, recria `.career-state/fit_map.draft.json` e devolve `next_required_step`.

---

## HISTÓRICO DE CANDIDATURAS EM ANDAMENTO

| Empresa | Cargo | Fit | Status | Observação |
|---|---|---|---|---|
| Keeta | On-Time Delivery & Capacity Strategy Expert | 7,69/10 | CV gerado (inglês) | — |
| DHL Supply Chain | Gerente de Transportes, Startup | 6,21/10 | CV gerado (Persona A) | — |
| Trivium Group | Senior Operations Manager (remote USD) | 5,95/10 | CV + carta gerados | Culture Index concluído |
| COO via WiseTalent | COO | 8,5–9,0/10 | Prioridade máxima | CV enviado para Helen Brugnara |
| Contabilizei | Head de Atendimento | 8,5/10 | Aguardando recrutador | Não aplicar direto — contato via recrutador |
| Hays | National Logistics Manager | — | CV entregue | Contato: Ricardo Ribas |

---

## GLOSSÁRIO DE TERMOS DO PROJETO

| Termo | Significado |
|---|---|
| **FIT_MAP** | Mapa de aderência interno produzido pela `career-fit-analysis`. Alimenta todas as outras skills. |
| **Persona A/B/C** | Seleções de experiências separadas e ordem de apresentação no CV, definidas pelo tipo de vaga |
| **Dor central** | O problema principal que a empresa quer resolver contratando a posição. Define o ângulo narrativo de todos os documentos. |
| **Peso total** | Critérios do `output-reviewer` que, se violados, bloqueiam a entrega — sem exceção |
| **FERAS** | Formação, Experiência, Resultado, Atualmente, Sonhos — estrutura de pitch oral |
| **ATS** | Applicant Tracking System — sistema que filtra CVs por keywords antes de chegar ao recrutador humano |
| **Half-points** | Unidade de tamanho de fonte no DOCX via biblioteca `docx` (npm). 9pt = 18 half-points. |
| **Narrativa protegida** | Histórias com versão certa e errada de ser contadas, documentadas em `perfil_restricoes.md` |
| **DIRETO / REPOSICIONAMENTO / GAP** | Classificação de aderência de cada keyword da vaga ao perfil real |
| **Gupy** | Principal plataforma ATS de candidaturas no Brasil — tem lista própria de habilidades selecionáveis |
