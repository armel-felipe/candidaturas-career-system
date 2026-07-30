---
name: cv-generator
description: >
  Gera o CV de Felipe Armel em DOCX ou PDF, adaptado para uma vaga específica ou perfil-alvo.
  Use esta skill SEMPRE que o usuário pedir: "gera o CV", "faz o currículo", "adapta o CV para essa vaga",
  "qual persona de CV usar", "atualiza o CV", ou qualquer variação que implique produzir ou ajustar um currículo.
  Requer FIT_MAP ativo (gerado por career-fit-analysis). Se não houver FIT_MAP, solicite o anúncio e
  execute career-fit-analysis primeiro antes de gerar qualquer documento.
---

# CV Generator

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/cv-generator/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/cv-generator/SKILL.md`.

## Adaptação Local OpenCode

Leia também `../career-system/SKILL.md`. Substitua `<workspace>` pelo workspace local, `outputs` por `outputs/` e `entrega local em outputs/` por entrega local do arquivo gerado. Use `.career-state/fit_map.json` como FIT_MAP ativo. Os scripts locais ficam em `scripts/docx/`: `generate_custom_cv.js`, `validate_docx.py` e `convert_pdf.sh`.

Quando esta skill for acionada a partir do orquestrador de candidaturas:
- leia primeiro `generation_request.json/md` da candidatura;
- leia primeiro os arquivos apontados em `compact_inputs.primary_files`;
- produza somente os artefatos textuais pedidos, com `cv_content.json` como fonte principal do CV;
- não renderize DOCX, não rode ATS/reviewer e não atualize Notion;
- trate `fit_map.json`, `job_description.md` e referências longas como fallback, não como leitura inicial obrigatória.

Quando esta skill for acionada no fluxo manual/local fora do heartbeat:
- rode `npm run context:assert-active` antes de reaproveitar `FIT_MAP` ou `cv_content`;
- gere `cv_content.json` com `npm run cv:build-content`;
- valide o contrato com `npm run cv:validate-content`;
- só então renderize o DOCX com `npm run cv:docx`.

## GATE DE IDIOMA DO CV (obrigatório antes de `cv:docx`)

Vaga em inglês **NUNCA** pode gerar CV em português. Antes de cada `npm run cv:docx`:

1. **Detectar idioma da descrição**: se a descrição em `inbox/job_descriptions/<slug>.md` for predominantemente em inglês (heurística simples: presença de "the", "and", "experience", "responsibilities", "requirements" no primeiro parágrafo), a vaga é EN.
2. **Verificar fit_map**: rodar `jq '.idioma // "pt-BR"' .career-state/fit_map.json`. Se vaga é EN e o valor não é "en" (ou variante), setar `fit_map.json["idioma"] = "en"` antes de continuar.
3. **Verificar cv_content**: rodar `jq '.metadata.language // "missing"' .career-state/cv_content.json`. Se vaga é EN e o valor não é "en", **NÃO** prosseguir — apagar `cv_content.json` e rerodar `npm run cv:build-content` para que o serviço materialize as views `experiences` (EN) e `experiencias` (PT) com base no `fit_map.idioma` correto.
4. **Verificar sufixo `_en`**: `output_name` em `cv_content.json` deve terminar com `_en.docx` quando a vaga for EN. Validar com `echo "$OUTPUT_NAME" | grep -qE "_en\.docx$"`.
5. **Verificar conteúdo do DOCX final** após `cv:docx`: rodar `unzip -p outputs/<cv>_en.docx word/document.xml | grep -ic "fui responsável\|gerenciei\|liderei\|conduzi\|conectei"`. Se contagem > 0, **BLOQUEAR** entrega. As afinações de bullets DEVEM ser aplicadas em **ambos** os arrays `experiencias` (PT) e `experiences` (EN) — o `node generate_custom_cv.js` lê `experiences[].bullets[].text` quando `metadata.language = "en"`.

Esse gate existe porque o serviço `_cv_language(fit_map)` em `src/career/services/cv_content.py` retorna "en" **apenas** se `fit_map["idioma"]` começar com "en". Sem o campo, o default é "pt-BR", o que faz o CV sair em português mesmo para vaga em inglês.

Gera o CV de Felipe Armel em DOCX ou PDF, aderente a todas as regras do prompt v8, consumindo o FIT_MAP
produzido pela career-fit-analysis.

---

## PRÉ-REQUISITO OBRIGATÓRIO

Antes de escrever qualquer linha do CV:

1. Verificar se há FIT_MAP ativo na conversa.
   - Se sim: consumir diretamente.
   - Se não: solicitar o anúncio e executar career-fit-analysis antes de prosseguir.

2. Consultar `perfil_restricoes.md` → seção NÚMEROS CRÍTICOS antes de usar qualquer número.

3. **Definir o formato de saída** — DOCX ou PDF.
   - Se o usuário não tiver explicitado o formato, perguntar.
   - Se o formato já estiver explícito no pedido ou no contexto imediato, assumir o formato informado e seguir sem nova pergunta.
   - Nunca gerar HTML.

---

## PERGUNTA DE FORMATO — OBRIGATÓRIA

Antes de gerar o arquivo, perguntar ao usuário:

> "Prefere DOCX (editável) ou PDF?"

Só usar essa pergunta quando o formato ainda não estiver explicitado no pedido atual. Se o usuário já tiver pedido DOCX ou PDF, não perguntar de novo: executar o pipeline correspondente no mesmo turno.

---

## MODO DE ESCRITA DAS EXPERIÊNCIAS

O modo de escrita é independente da quantidade de experiências. Todo CV orientado por vaga deve respeitar a faixa de 4 a 8 experiências, salvo pedido explícito do usuário por versão reduzida. Mesmo em versão reduzida, nunca juntar experiências para caber.

### Modo conciso — padrão

Usar quando o usuário pedir CV sem especificar outro modo, ou quando pedir explicitamente "modo conciso".

Pedidos como "CV personalizado", "CV em DOCX", "adapte o currículo", "currículo para essa vaga" ou equivalentes continuam no modo conciso. Esses pedidos não autorizam 4+ bullets por experiência.

Cada experiência deve ter exatamente 3 bullets, usando o conceito de história completo:

1. **Fui responsável por** — escopo, time, responsabilidade principal e elemento mais aderente à vaga.
2. **Alavanca de reposicionamento (verbo de ação)** — mecanismo que explica diretamente o resultado e traduz a experiência para a vaga-alvo. Combinar, em prosa fluida, 1 método/rito de execução + 1 ferramenta/processo relevante + 1 competência transferível quando isso fortalecer a ponte para a vaga. Começar com verbo de ação em 1ª pessoa (liderei, estruturei, implantei, conduzi, apliquei, modelei, criei, desenvolvi, etc.) — nunca com o rótulo "Utilizando:" seguido de lista. Máximo 3 elementos narrativos.
3. **Resultado** — resultado com número, priorizando o impacto mais relevante para a vaga. Começar diretamente com verbo de resultado (reduzi, ampliei, elevei, alcancei, atingi, etc.) — nunca com o rótulo "Consegui:".

Este modo força síntese: uma história principal por experiência, com escopo → alavanca de reposicionamento → resultado.

**REGRA DE FLUIDEZ — NUNCA VIOLAR:**
- Nenhum bullet começa com rótulo seguido de dois-pontos ("Fui responsável por:", "Utilizando:", "Consegui:")
- Todo bullet é prosa fluida em 1ª pessoa — o leitor não vê o rótulo, vê a frase
- Concordância verbal obrigatória: sujeito implícito é sempre "Eu" — todos os verbos na 1ª pessoa do singular
- "Fui responsável por" aparece apenas como abertura do bullet 1, nunca como rótulo com ":"

### Modo expandido / bullet points

Usar somente quando o usuário pedir explicitamente "bullet points", "mais bullets", "não conciso", "expandido", "mais completo" ou especificar um número de bullets por experiência.

Regras:
- Manter o conceito de história, mas aplicado às entregas mais relevantes da experiência.
- Cada experiência deve começar com 1 bullet de síntese da história como um todo: escopo, contexto, time e tese de aderência à vaga.
- Depois, listar de 3 a X bullets de entregas, conforme o número solicitado pelo usuário.
- Se o usuário não especificar X, perguntar quantos bullets por experiência deseja antes de gerar.
- Ordenar as entregas por aderência à vaga, não por cronologia interna.
- Cada bullet de entrega deve ter evidência real e, sempre que possível, número defensável.
- Não transformar o modo expandido em lista genérica de responsabilidades; cada bullet deve provar uma competência ou keyword importante do FIT_MAP.

Formato recomendado no modo expandido:

1. **História da experiência** — "Assumi/estruturei/liderei..." com escopo e contexto.
2. **Entrega 1** — entrega mais aderente à dor central, com número.
3. **Entrega 2** — segunda entrega mais relevante, com número.
4. **Entrega 3** — cobertura de keyword ou competência crítica, com número.
5. **Entrega N** — somente se aumentar aderência sem diluir o argumento.

No modo expandido, não usar obrigatoriamente os rótulos "Fui responsável", "Utilizando" e "Consegui"; eles são exclusivos do modo conciso.

Regra de ambiguidade:
- se o pedido mencionar apenas DOCX/PDF, vaga, personalização ou ATS, manter modo conciso;
- se o pedido mencionar "bullet points" sem quantidade, interpretar como modo expandido e perguntar quantos bullets por experiência antes de gerar;
- se o usuário pedir "bullet points" e informar quantidade, usar exatamente essa quantidade, respeitando as demais validações.

### Validação com o usuário antes de modo expandido inferido

O agente pode identificar que uma vaga talvez se beneficie de modo expandido, mas isso não autoriza gerar o CV expandido automaticamente.

Cenários que podem justificar sugerir modo expandido:
- vaga sênior multiarea com muitas frentes obrigatórias;
- formulário/plataforma que exige copiar experiências em campos longos;
- candidatura por indicação, sponsor interno ou recrutador que vai defender o caso;
- reposicionamento para cargo novo;
- pedido de maximizar cobertura ATS aceitando CV mais longo;
- CV mestre/base de repertório.

Regra operacional:
- se o usuário pediu explicitamente "bullet points", "expandido", "mais completo" ou quantidade de bullets, seguir o modo expandido;
- se o agente apenas inferiu que modo expandido pode ser melhor, parar antes de gerar e validar com o usuário;
- a validação deve ser curta e objetiva: "Esta vaga parece candidata a modo expandido porque [motivo]. Mantenho o padrão conciso ou faço bullet points/expandido?";
- sem confirmação explícita do usuário, manter modo conciso.

---

## NOME DO ARQUIVO — REGRA FIXA

## IDIOMA DO CV — REGRA FIXA

O idioma do CV deve seguir o idioma predominante da descrição da vaga:
- descrição de vaga em inglês → CV em inglês, texto visível em inglês e sufixo `_en` no arquivo;
- descrição de vaga em português → CV em português e arquivo sem sufixo `_en`;
- não escolher idioma por preferência do modelo, por keywords ATS ou por idioma da empresa;
- em execução pelo orquestrador, obedecer `required_cv_language` salvo em `.career-state/applications/<ID>/manifest.json`.

Regra explicita para CV em ingles:
- nao basta traduzir resumo, bullets e formacao; os titulos de cargo das experiencias tambem devem aparecer em ingles visivel
- exemplos esperados: `Head of Operations`, `Director of Operations`, `S&OP Coordinator`, `Commercial Planning and Operations Manager`
- exemplos invalidos em CV `_en`: `Head de Operações`, `Diretor de Operações`, `Coordenador de S&OP`

Exceção somente com pedido explícito do usuário.

### Regra de labels de seção — CV em inglês

Em CV `_en` (inglês), todas as labels de seção visíveis no DOCX devem estar em inglês:

| Seção | PT-BR | EN |
|---|---|---|
| Resumo / Summary | (não tem label) | (não tem label) |
| Experiência | Experiência | Experience |
| Formação | Formação | Education |
| Stack técnica | Stack técnica | Technical Stack |
| Idiomas | Idiomas | Languages |

Esta regra é diferente da tradução de cargos/períodos/bullets. Mesmo que o conteúdo do bullet esteja em inglês, se a label da seção ficar em português o CV parece inconsistente.

Todos os arquivos gerados devem seguir o padrão:

```
felipe_armel_cv_[cargo]_[empresa].[ext]
felipe_armel_cv_[cargo]_[empresa]_en.[ext]   <- quando o CV for em inglês
```

- `[cargo]` = título da vaga em snake_case, sem acentos, sem caracteres especiais
  - Exemplos: `diretor_logistica_supply_chain`, `merchant_operations_manager`, `head_operacoes`
- `[empresa]` = nome da empresa em snake_case, sem acentos, sem caracteres especiais
  - Exemplos: `kraft_heinz`, `tiktok`, `mercado_livre`, `loggi`
- `_en` = sufixo obrigatório quando o CV for gerado em inglês — inserir antes da extensão
- `[ext]` = `docx` ou `pdf`
- Nunca usar nomes genéricos como `cv.docx`, `curriculo_felipe.docx` ou `cv_final.docx`

Derivar cargo e empresa do FIT_MAP (campos `cargo` e `empresa`). Se ambíguo, perguntar ao usuário.

---

## SELEÇÃO DE PERSONA E EXPERIÊNCIAS

### Personas disponíveis

| Persona | Foco | Ordem de experiências |
|---|---|---|
| A — Logística/Marketplace | iFood, Trifil, WeHandle | iFood Diretor → iFood Head → Trifil → WeHandle |
| B — SaaS/CX/Fintech | WeHandle, iFood, VivaReal | WeHandle → iFood Diretor → VivaReal → iFood Head |
| C — Supply Chain/Planning | iFood, Trifil S&OP | iFood Diretor → Trifil S&OP → Trifil Expedição |
| D — Melhoria Contínua | Trifil + iFood como prova de escala | Trifil S&OP + Expedição + iFood |
| Startup/early-stage | WeHandle na frente | WeHandle → iFood Diretor → iFood Head → Trifil |

### Seleção baseada no FIT_MAP

Use `dor_central` e `historias_selecionadas` para determinar:
1. Qual persona cobre melhor as keywords e competências da vaga
2. Quais 4–8 experiências incluir
3. A ordem que maximiza aderência

Se a vaga for startup/early-stage: WeHandle aparece primeiro.
Se for marketplace/logística: iFood Diretor aparece primeiro.
Se for SaaS/CX: WeHandle → iFood Diretor → VivaReal.

Declarar a persona escolhida e justificar antes de gerar.

### Faixa obrigatória de experiências

- Todo CV orientado por vaga deve trazer **no mínimo 4 e no máximo 8 experiências**.
- Não tratar 4 experiências como “CV longo demais” por padrão; priorizar síntese de bullets antes de cortar experiência relevante.
- Só ficar abaixo de 4 quando o usuário pedir explicitamente uma versão reduzida e aceitar o trade-off.
- Quando houver mais de 8 experiências potencialmente relevantes, cortar por aderência à dor central, requisitos obrigatórios, objeções críticas e top 8 keywords ATS.

### Cobertura obrigatória das top 8 keywords ATS

Antes de fechar o `cv_content.json`, mapear as 8 keywords-habilidade prioritárias do FIT_MAP para experiências e bullets defensáveis.

Regra operacional:
- cada keyword top 8 deve ficar associada a uma experiência real e a um bullet que a sustente;
- a cobertura principal deve acontecer nas experiências, não no resumo;
- quando a keyword couber de forma natural, preferir cobertura exata ou equivalente PT-BR canônico;
- quando a keyword não puder ser sustentada por fato real, registrar como gap declarado no mapeamento interno — nunca forçar wording artificial no CV;
- keyword crítica ausente sem explicação não pode ser tratada como detalhe estético; é defeito estrutural do CV.

### Ordem das experiências — REGRA FIXA

As experiências no CV seguem **sempre ordem cronológica inversa** — a mais recente primeiro, a mais antiga por último. Esta regra é inviolável independentemente da persona ou do FIT_MAP.

A seleção de quais experiências incluir e os ângulos narrativos são definidos pelo FIT_MAP. A ordem entre elas é sempre cronológica inversa.

### Consolidação de cargos — PROIBIDA

Regra dura de não consolidação:
- nunca agrupar cargos, empresas, fases, promoções ou escopos em uma única entrada de experiência;
- cada cargo, promoção ou fase distinta selecionada vira uma entrada própria, inclusive quando ocorreu dentro da mesma empresa;
- iFood Head e iFood Diretor são sempre entradas separadas quando ambos forem selecionados;
- cargos da Trifil são sempre entradas separadas quando mais de um cargo da Trifil for selecionado;
- nunca usar títulos compostos como "Head e Diretor", "Head + Diretor", "S&OP | Expedição | Supply Chain" ou equivalentes;
- nunca usar período agregado para múltiplos cargos, como Nov/2018 – Mar/2024 para iFood Head + Diretor ou Jan/2006 – Set/2014 para Trifil inteira;
- se a quantidade ou espaço entrar em conflito com a lista de cargos separados, cortar por aderência e explicar a seleção; não consolidar para caber;
- esta regra vale em qualquer circunstância, mesmo quando o usuário não pedir explicitamente "sem consolidar";
- em caso de conflito entre "persona padrão" e pedido explícito do usuário, prevalece sempre o pedido explícito do usuário, desde que não peça consolidação.

---

## ESTRUTURA DO CV

### Cabeçalho (nunca alterar)
```
Felipe Armel Dias da Silva
linkedin.com/in/felipearmel    ← link clicável
São Paulo, SP
(11) 98674-8218                ← link clicável (wa.me)
armelfelipe@gmail.com          ← link clicável (mailto)
```
- Nunca centralizar
- Nunca colocar dois dados na mesma linha
- Nunca usar emojis

### Resumo
- Máximo 480 caracteres (exceto quando o usuário autorizar extensão — até 1500 caracteres para CV de posicionamento)
- **TOM — regra central:** factual, direto, primeira pessoa real. Um executivo sênior conta o que fez com precisão e confiança. O resultado fala por si. Proibido: frases de efeito ("sou o que transforma", "conecto planejamento, execução e resultado"), autoproclamação, linguagem de coach. Correto: formação, contexto, o que fez, número, o que busca.
- **Naturalidade em português — regra central:** em CV PT-BR, keyword ATS nunca pode soar como metralhadora de termos em inglês no meio da prosa. Se a frase ficar artificial para um recrutador humano brasileiro, reescrever. ATS ajuda, mas legibilidade humana manda.
- Formato: [formação se agrega] + [contexto de carreira com número âncora] + [o que busca]
- Regras de abertura:
  - NUNCA abrir com o cargo da vaga se Armel não o exerceu com esse nome formalmente
  - Usar "Executivo Sênior" ou "Gerente Sênior" seguido das competências que fazem ponte
  - O título da vaga aparece apenas no fechamento ("Busco posição de X")
  - Exceção: quando o cargo é exatamente o que Armel exerceu (ex: "Diretor de Operações")
- Para startup: incluir sinal de preferência por ambiente de construção — em tom factual, não em proclamação
- **Sinalização de cargo no resumo — REGRA:**
  Os resultados citados no resumo devem identificar a empresa **e o cargo** de origem, na ordem de relevância para a vaga (não cronológica), para guiar o recrutador ao ponto certo do CV.
  - **Versão completa** (usar sempre que o limite de caracteres permitir):
    > "No iFood, como Diretor de Operações, reduzi... Como Head de Operações, gerei saving..."
  - **Versão comprimida** (usar quando o limite pressionar — sacrifica o cargo, nunca o número):
    > "No iFood, reduzi... e gerei saving..."
  - Regra de compressão: primeiro comprimir o cargo, depois comprimir a empresa se necessário. Nunca comprimir o número.

### Experiência — modo conciso: 3 bullets por experiência

**Bullet 1 — Fui responsável por**
- Responsabilidades + escopo + time
- Elemento mais relevante para a vaga em posição de destaque
- Máximo 1 camada de escopo

**Bullet 2 — Alavanca de reposicionamento (verbo de ação)**
- Começar com verbo em 1ª pessoa: liderei, estruturei, implantei, conduzi, apliquei, modelei, criei, desenvolvi, usei, automatizei — nunca com "Utilizando:"
- Explicar como o resultado do bullet 3 aconteceu e por que essa experiência é transferível para a vaga-alvo
- Combinar, quando útil: método/rito + ferramenta/processo + competência transferível
- Máximo 3 elementos narrativos integrados em prosa fluida
- Nunca listar toda a stack; nunca usar formato de lista separada por "·" sem frase que a anteceda
- Nunca repetir o escopo do bullet 1 com verbos genéricos sem mecanismo causal
- Para vagas de projetos, priorizar governança, coordenação cross-functional, dependências, stakeholders, riscos, rollout e cadência executiva
- Para vagas de operações, priorizar indicadores, capacidade, desenho operacional, SLAs, automação e eficiência
- Para vagas de planejamento, priorizar cenários, S&OP, forecast, orçamento e balanceamento de capacidade
- Para vagas de CX/SaaS, priorizar jornada, automação, integrações, backoffice e experiência do cliente
- Para vagas de Product/Revenue/BizOps, priorizar dados, pricing, priorização, roadmap e performance comercial

**Bullet 3 — Resultado**
- Começar com verbo de resultado em 1ª pessoa: reduzi, ampliei, elevei, alcancei, atingi, aumentei, gerei — nunca com "Consegui:"
- Resultado com número — obrigatório
- Resultado financeiro mais relevante como fechamento
- Todos os itens com número

Regras: sem número = bullet inválido · 1ª pessoa em todo o documento · negritar o número mais estratégico por experiência · nunca rótulo com ":" em nenhum bullet

### Passo 0.6 — Distribuição de keywords críticas nas experiências

Antes de considerar o `cv_content.json` concluído:

1. listar as top 8 keywords ATS por prioridade;
2. decidir em qual experiência cada keyword ficará ancorada;
3. verificar se o bullet escolhido traz evidência defensável real;
4. ajustar a redação para que a keyword apareça de modo natural no bullet ou por equivalente PT-BR canônico;
5. se não houver fato suficiente, marcar como gap declarado no mapeamento interno em vez de inflar o texto.

Checklist mínimo:
- [ ] O CV tem entre 4 e 8 experiências.
- [ ] As top 8 keywords ATS estão distribuídas nas experiências, não concentradas artificialmente no resumo.
- [ ] Cada keyword top 8 tem experiência-alvo e bullet defensável identificados.
- [ ] Keywords sem sustentação real não foram inseridas à força.

### Regra de keyword em PT-BR — NUNCA VIOLAR

Em CV em português:
- nao espalhar keywords-habilidade em ingles como se fossem lista de SEO no meio dos bullets
- no maximo 1 keyword-habilidade em ingles por bullet
- priorizar prosa natural em portugues para explicar a competencia; usar o termo em ingles apenas quando ele ja for rotulo de mercado realmente natural no Brasil
- exemplos geralmente naturais: `S&OP`, `OTIF`, `SLA`, `WMS`, `MRP`
- exemplos que exigem cuidado e normalmente pedem traducao ou reducao de uso: `Executive Governance`, `Operational Excellence`, `Data-driven Decision Making`, `Cross-functional Leadership`, `Inventory Management`
- se a keyword exata em ingles deixar a frase artificial, preservar a evidencia em portugues e usar o termo exato apenas onde couber naturalmente
- CV em ingles (`_en`) nao segue esta restricao; ai o objetivo e naturalidade em ingles

### Experiência — modo expandido / bullet points

- 4 a X bullets por experiência, somente quando pedido explicitamente pelo usuário.
- Primeiro bullet: síntese da história completa da experiência.
- Bullets seguintes: entregas específicas ordenadas por relevância para a vaga.
- Usar o FIT_MAP para decidir quais entregas entram, quais keywords são cobertas e quais resultados ficam em destaque.
- Se houver mais entregas fortes do que espaço, priorizar nesta ordem: dor central da vaga, requisito obrigatório, objeção crítica, keyword ATS prioritária, diferencial competitivo.
- Todo número deve ser validado contra `perfil_restricoes.md` e `autoconhecimento.md`.
- Se uma entrega forte não tiver número defensável, ela pode entrar apenas se for essencial para cobrir uma competência crítica; caso contrário, preferir entregas mensuráveis.

### Formação
- 1 bullet por formação, mais recente primeiro
- BSP: usar somente ano de conclusão, nunca faixa. Em português: "MBA Corporate Strategy — BSP Business School São Paulo (2017)". Em inglês: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)"
- **Engenharia Química em CV inglês (`_en`):** usar sempre `"B.Sc. in Chemical Engineering — Faculdades Oswaldo Cruz (2014)"`. Nunca usar `"Chemical Engineering"` sem o título acadêmico. A forma canônica está em `.agents/skills/career-system/references/candidate_cv_facts.json`.
- Incluir apenas o que agrega credibilidade para a vaga

### Stack Técnica
- Somente ferramentas relevantes para a vaga (filtrar pelo FIT_MAP)
- Formato: item · item · item

### Idiomas
- Usar `bullet()` — nunca `paragrafo()` — um bullet por idioma
- Formato de cada bullet: `[Idioma] — [Nível]`
- Português — Nativo
- Inglês — Avançado
- Nunca "Fluente" · Nunca incluir espanhol

---

## CHECKLIST DE REVISÃO — OBRIGATÓRIO ANTES DE GERAR

**Por bullet:**
- [ ] Modo conciso: os 3 bullets estão presentes e cumprem suas funções (escopo → alavanca → resultado)?
- [ ] Nenhum bullet começa com rótulo seguido de ":" ("Fui responsável por:", "Utilizando:", "Consegui:") — todos são prosa fluida em 1ª pessoa?
- [ ] Bullet 2 começa com verbo de ação em 1ª pessoa (liderei, estruturei, implantei, conduzi, etc.) — nunca com "Utilizando:"?
- [ ] Bullet 2 explica o mecanismo do resultado e ajuda no reposicionamento para a vaga, em vez de só listar ferramentas ou repetir escopo?
- [ ] Bullet 3 começa com verbo de resultado em 1ª pessoa (reduzi, ampliei, elevei, alcancei, etc.) — nunca com "Consegui:"?
- [ ] Concordância verbal consistente em 1ª pessoa do singular em todos os bullets?
- [ ] Modo expandido: há 1 bullet de história geral e os demais bullets são entregas priorizadas pela vaga?
- [ ] Cada bullet prova uma competência, keyword, entrega ou mitigação de objeção relevante?
- [ ] Os números foram validados e o resultado financeiro mais relevante ficou visível?

**Cobertura geral:**
- [ ] Budget coberto? Saving em R$ ou %? Ganhos de escala? Criação de área? Interface C-level?

**Narrativas protegidas:**
- [ ] VivaReal CS: "arquiteto da área" (nunca "gestor")?
- [ ] Fill rate: atribuído à Trifil (nunca VivaReal)?
- [ ] WeHandle margem bruta: 15%?
- [ ] WeHandle custo por atendimento: R$4,14→R$3,61 (−13%)?
- [ ] iFood saving: R$70MM/ano?
- [ ] iFood budget: R$300MM/ano?
- [ ] Espanhol: ausente?
- [ ] Inglês: "Avançado"?

**Teste de leitura rápida (10 segundos):**
- [ ] O argumento mais forte para a vaga ficou visível em cada experiência?

---

## PIPELINE DE GERAÇÃO — DOCX

### Regra crítica de fonte — NUNCA VIOLAR

```javascript
const pt = n => n * 2; // half-points — NUNCA n * 20 (twips)
// 9pt = 18 | 12pt = 24 | 6pt = 12 | 8pt = 16
```

### Tipografia

| Elemento | Tamanho | Estilo |
|---|---|---|
| Nome | 12pt | negrito |
| Títulos de seção | 12pt | normal, sem negrito |
| Texto geral | 9pt | normal |
| Períodos | 9pt | normal |

Títulos de seção: sentence case — "Experiência", "Formação", "Stack técnica", "Idiomas"

### Margens A4

```javascript
properties: {
  page: {
    margin: { top: 720, right: 504, bottom: 720, left: 504 }
  }
}
// 720 DXA ≈ 1cm | 504 DXA ≈ 0.7cm
```

### Configuração de seção — obrigatória

```javascript
sections: [{
  properties: {
    page: {
      margin: { top: 720, right: 504, bottom: 720, left: 504 }
    }
  },
  children: [/* conteudo */]
}]
```

Regras críticas:
- nunca usar `properties: { type: "A4" }`
- nunca usar `margins:` diretamente no nível da section
- tamanho da página é resolvido pelo `docx`; o ajuste obrigatório aqui é `properties.page.margin`

### Estilos obrigatórios

```javascript
styles: {
  default: { document: { run: { font: "Arial", size: pt(9) } } },
  paragraphStyles: [
    { id: "Normal", name: "Normal", quickFormat: true,
      run: { font: "Arial", size: pt(9) },
      paragraph: { spacing: { after: 0 } } },
    { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
      run: { font: "Arial", size: pt(9) },
      paragraph: { spacing: { after: 0 } } }
  ]
}
```

### Funções auxiliares obrigatórias

```javascript
// Linha de seção com borda inferior
function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

// Espaçador
function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// Cargo com período alinhado à direita
function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" })
    ],
    spacing: { after: 0 }
  });
}

// Bullet com suporte a array de runs [{text, bold}]
function bullet(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) }
  });
}
```

### Bullets — NUNCA usar unicode manual

```javascript
// CORRETO — sempre via numbering config
numbering: {
  config: [{
    reference: "bullets",
    levels: [{
      level: 0, format: LevelFormat.BULLET, text: "\u2022",
      alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 180 } } }
    }]
  }]
}
```

### Espaçamento entre blocos

```javascript
espaco(8)  // entre seções
espaco(6)  // entre experiências
espaco(3)  // entre título de seção e primeiro item
```

### Pipeline de execução — SEGUIR NESTA ORDEM, SEM PULAR PASSOS

**Passo 0 — Extrair e validar datas de `autoconhecimento.md` — OBRIGATÓRIO ANTES DE QUALQUER CÓDIGO**

Antes de escrever uma linha do script Node.js, ler `autoconhecimento.md` e **exibir na conversa** a tabela de datas de cada experiência que será incluída no CV. A tabela deve aparecer no chat antes de qualquer código — se não foi exibida, o passo não foi executado.

| Experiência | Cargo | Data início | Data fim |
|---|---|---|---|
| [empresa] | [cargo exato] | [mês/ano do arquivo] | [mês/ano do arquivo] |

Regras obrigatórias:
- **Nunca usar data de memória, estimativa ou sessão anterior** — toda data vem do arquivo
- Se o arquivo tiver datas conflitantes ou ambíguas para um cargo, **parar e perguntar ao usuário** antes de prosseguir
- Nunca consolidar experiências em bloco único; cada linha da tabela deve corresponder a um cargo/fase real selecionado e ao período próprio desse cargo/fase
- A tabela validada é o único input aceito para os campos de período no script — qualquer data hardcoded que não esteja nessa tabela é erro de execução
- Após montar a tabela, verificar que a ordem cronológica inversa das experiências está consistente com as datas extraídas — se houver divergência entre a ordem pretendida e as datas reais, **sinalizar ao usuário antes de gerar**

Esta etapa não é opcional. Pular o Passo 0 invalida toda a execução subsequente.

---

**Passo 0.5 — Garantir presença de keywords-habilidade ATS nos bullets**

Antes de escrever os bullets do CV, consumir `keywords_habilidade_ats` do FIT_MAP:

Referências obrigatórias para CV em PT-BR:
- `.career-state/derived/keyword_ats_registry.json`
- `.agents/skills/career-system/references/keyword_translation_registry.json`
- `.career-state/derived/keyword_translation_candidates.json`

Uso correto dessas referências:
- `keyword_translation_registry.json` é a fonte canônica de equivalentes PT-BR aceitos pelo reviewer.
- `keyword_translation_candidates.json` é derivado do histórico de candidaturas e ajuda a escolher quais termos em inglês valem tradução prioritária. O caminho canônico é `.career-state/derived/keyword_translation_candidates.json`.
- quando uma keyword-habilidade em inglês de duas ou mais palavras soar artificial em prosa PT-BR, priorizar o equivalente canônico em português antes de insistir no termo exato.
- termos consagrados no mercado brasileiro como `S&OP`, `OTIF`, `WMS`, `MRP` e equivalentes similares podem continuar em inglês/sigla se soarem naturais.

1. **Para as 8 keywords de maior prioridade (1–8):** garantir cobertura real no CV, mas sem sacrificar a naturalidade humana
   - `covered_cv`: termo exato aparece naturalmente no texto
   - `covered_similar_cv`: a competencia aparece com wording natural equivalente em portugues
   - `gap`: nao ha evidencia suficiente; nao forcar o termo
2. Em CV em português:
   - usar o termo exato em ingles apenas quando ele ja for um rotulo natural de mercado ou quando couber organicamente na frase
   - se o termo exato em ingles ficar artificial, preferir cobertura por wording natural equivalente em portugues
   - se houver equivalente no `keyword_translation_registry.json`, ele conta como cobertura defensável no reviewer e deve ser preferido quando reduzir o efeito de "keyword shotgun"
   - limitar a **no maximo 5 ocorrencias** de keywords-habilidade em ingles com duas ou mais palavras em todo o corpo de prosa do CV (resumo + experiencias)
   - nunca colocar duas keywords-habilidade em ingles com duas ou mais palavras na mesma frase
   - nunca enxertar termo ingles em sintaxe portuguesa ruim apenas para bater ATS, como `Conduzi experimentation...`
3. **Para as keywords 9–15:** inserir quando o encaixe for natural, sem forçar
4. **Após escrever todos os bullets e antes de gerar o script:** exibir a tabela de cobertura na conversa — se não foi exibida, o passo não foi executado:

| # | Keyword | Presente? | Onde (experiência + bullet) | Termo exato? |
|---|---|---|---|---|
| 1 | [keyword] | ✅/❌ | [empresa — Responsável/Utilizando/Consegui/Resumo/Stack] | sim/não |

5. Se alguma das 8 primeiras estiver ausente sem cobertura real (`covered_cv` ou `covered_similar_cv`): **reescrever o bullet** correspondente antes de prosseguir para o Passo 1
6. Nunca inserir keyword que não tenha evidência real na base — keyword sem experiência defensável fica como gap declarado, não como termo forçado
7. Separar matching de redação: normalização sem acento pode existir nos scripts de comparação ATS, mas nunca deve vazar para o texto visível do CV em português
8. Teste final desta etapa: se um recrutador humano ler o resumo e os bullets e sentir "metralhadora de keyword em ingles", reescrever antes de gerar o DOCX

**Passo 0.6 — Ancorar o resumo nas experiências selecionadas**

Antes de fechar o `cv_content.json`, verificar que todo fato específico do resumo executivo esteja explicitamente sustentado por pelo menos uma experiência incluída no próprio CV.

Regras obrigatórias:
- o resumo não pode trazer número, escala, sigla operacional, ativo regulatório, cidade, budget, saving, POP, KPI ou claim factual cuja experiência de origem não esteja selecionada no CV;
- o resumo não pode usar `historias_selecionadas` do FIT_MAP como atalho para citar resultados de experiências que ficaram fora do documento final;
- toda frase factual do resumo deve apontar para uma experiência e bullet defensáveis dentro de `cv_content.json`;
- se uma evidência forte do FIT_MAP não couber nas 4–8 experiências escolhidas, a ação correta é remover essa evidência do resumo, não deixá-la “solta” no topo do CV;
- quando houver dúvida entre “ficou ótimo no resumo” e “está de fato endossado pelas experiências visíveis”, prevalece sempre a segunda opção.

Checklist mínimo antes do DOCX:
- [ ] cada claim factual do resumo aparece novamente, de forma literal ou claramente equivalente, em uma experiência selecionada;
- [ ] nenhum item do resumo depende de experiência omitida;
- [ ] o resumo continua executivo e curto, mas sem promessas ou números órfãos.

---

**Fase A — Planejar os bullets de forma compacta antes de gerar o script**

Antes de escrever qualquer linha de código Node.js, registrar na conversa um mapa compacto das experiências e dos bullets, sem transformar essa etapa em um bloco longo de prosa. Use o formato:

```
[Empresa — Cargo — Período]
• Fui responsável por [texto — escopo, time, responsabilidade]
• [Verbo de ação] [texto — ferramentas/métodos que explicam o resultado]
• [Verbo de resultado] [texto com número]
```

O objetivo desta fase é validar a seleção e a ordem das experiências sem desperdiçar contexto em texto redundante. Se o contexto estiver curto ou o plano já estiver claro, vá direto para o script após esse mapa compacto.

Exemplo correto:
```
iFood — Diretor de Operações — Abr 2022 – Mar 2024
• Fui responsável por gerir as operações logísticas com equipe de ~240 pessoas e budget de R$300MM/ano.
• Conduzi o planejamento com S&OP executivo mensal, modelagem em Python, SQL e Databricks.
• Ampliei cobertura de 400 para 800 cidades, reduzi custo logístico comparável em 3% YoY e mantive SLA em 30M pedidos/mês.
```

Exemplo ERRADO — nunca fazer:
```
• Fui responsável por: [texto]     ← proibido ":"
• Utilizando: Grafana · SQL         ← proibido rótulo + ":"
• Consegui: Reduzi o custo...       ← proibido rótulo + ":"
```

Pular a Fase A e ir direto para o código continua sendo erro de execução, mas a fase agora deve ser compacta e não um bloqueio de contexto.

---

**FORMATAÇÃO — REGRAS INVIOLÁVEIS DO SCRIPT**

Estas regras se aplicam a cada linha do script Node.js. Violar qualquer uma delas é erro de execução — corrigir e reexecutar antes de prosseguir.

**Fonte:**
- Todo `TextRun` deve declarar `font: "Arial"` explicitamente — sem exceção
- Todo `TextRun` deve declarar `size: pt(N)` usando a função `pt` — nunca valor numérico direto sem `pt()`
- `pt = n => n * 2` — NUNCA `n * 20`; verificar a definição no topo do script antes de escrever qualquer `size`
- Tamanhos permitidos: `pt(12)` para nome e títulos de seção; `pt(9)` para todo o restante

**Espaçamento:**
- Todo `Paragraph` deve declarar `spacing: { after: 0 }` — nunca omitir
- Os únicos espaçamentos entre blocos são via `espaco()` com os valores fixos: `espaco(8)` entre seções, `espaco(6)` entre experiências, `espaco(3)` entre título de seção e primeiro item
- Nunca usar `spacing.before` ou `spacing.after` maior que 0 fora da função `secao()` e `espaco()`

**Bullets:**
- `bullet()` SEMPRE recebe array de runs `[{ text, bold }]` — nunca string única
- O número mais estratégico de cada experiência deve estar em run separado com `bold: true`
- Seção Idiomas: usar `bullet()` por idioma — nunca `paragrafo()`

**Datas:**
- Datas sempre via `cargoParagraph()` com tab direito — nunca como parágrafo separado
- Formato obrigatório: `Mmm AAAA – Mmm AAAA` (ex: `Mai 2024 – Fev 2026`) — primeira letra maiúscula, restante minúscula, separador `–` (en dash, não hífen `-`)

---

**Passo 1 — Escrever script Node.js completo**

Salvar em `<workspace>/outputs/_tmp/generated_scripts/cv_[escopo].js`. O script deve:
- Ter `const pt = n => n * 2` no topo — verificar antes de qualquer `size`
- Incluir todas as funções auxiliares (secao, espaco, cargoParagraph, bullet)
- Ter numbering config com LevelFormat.BULLET
- Ter styles com Normal e ListParagraph declarados explicitamente
- Usar page size A4 com margens corretas
- Usar ExternalHyperlink para todos os links do cabeçalho
- Output intermediário: `Packer.toBuffer(doc).then(buffer => { fs.writeFileSync("<workspace>/outputs/_tmp/cv_[escopo].docx", buffer); console.log("ok"); })`

Regra de caminho:
- `scripts/generated/` é legado histórico do projeto; não criar novos `.js` ali
- geração futura de scripts intermediários deve ficar em `outputs/_tmp/generated_scripts/`
- se a pasta não existir, criar antes de salvar o script

**Passo 2 — Executar**

```bash
cd <workspace> && node outputs/_tmp/generated_scripts/cv_[escopo].js
```

Verificar que stdout retornou "ok". Se erro: corrigir e re-executar antes de prosseguir.

**Passo 3 — Validar**

```bash
python3 scripts/docx/validate_docx.py <workspace>/outputs/_tmp/cv_[escopo].docx
```

Verificar "All validations PASSED!". Se falhar: desempacotar, inspecionar XML, corrigir, reempacotar.

**Passo 4 — Injetar theme Arial**

```bash
python scripts/docx/inject_arial_theme.py <workspace>/outputs/_tmp/cv_[escopo].docx <workspace>/outputs/felipe_armel_cv_[escopo].docx
```

**Passo 5 — Validar DOCX final**

```bash
python scripts/docx/validate_docx.py <workspace>/outputs/felipe_armel_cv_[escopo].docx
```

Verificar validação sem erros antes de prosseguir.

Regra de housekeeping:
- `outputs/_tmp/` é área temporária de geração.
- Depois que o DOCX final em `outputs/` estiver validado, revisado e com ATS registrado, os arquivos correspondentes em `outputs/_tmp/` devem ser excluídos na mesma execução.
- A limpeza do temporário só pode acontecer depois de verificar que o comando de registro ATS rodou com sucesso usando o DOCX final em `outputs/`.
- Nunca tratar `outputs/_tmp/` como fonte final de verdade.
- A limpeza não depende do modelo: usar `python scripts/docx/cleanup_tmp.py` ou `npm run docx:tmp:clean` quando houver resíduos.

**Passo 6 — Registrar cobertura ATS**

Atualizar o registro persistente de keywords com o DOCX final em `outputs/`:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv <workspace>/outputs/felipe_armel_cv_[escopo].docx --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json
```

Esse passo marca quais keywords apareceram como string exata no CV, quais ficaram faltando e quais devem alimentar bullets futuros do LinkedIn.

Antes de prosseguir, verificar explicitamente:
- que o comando terminou com sucesso;
- que o caminho passado no `--cv` foi o DOCX final em `outputs/`, nunca o arquivo de `outputs/_tmp/`.

**Passo 7 — Revisão obrigatória**

Antes de qualquer `entrega local em outputs/`, chamar a skill `output-reviewer` e executar o gate objetivo:

```bash
python scripts/review_output.py --kind cv --artifact <workspace>/outputs/felipe_armel_cv_[escopo].docx --fit-map .career-state/fit_map.json --registry .career-state/derived/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
```

Gate local/diagnóstico:

```bash
npm run cv:approve -- --artifact outputs/felipe_armel_cv_[escopo].docx
```

Quando o agente gerar um CV final e a entrega OneDrive/rclone estiver configurada, usar o comando composto seguro como encerramento do pipeline:

```bash
npm run cv:deliver -- --artifact outputs/felipe_armel_cv_[escopo].docx
```

`cv:deliver` reexecuta o gate de aprovação e só chama `deliver:artifact` quando `approved_for_delivery=true` e o polimento não tem blockers.

Regras obrigatórias:
- passar o arquivo gerado como input para a skill `output-reviewer`
- aguardar `approved_for_delivery=true`
- se qualquer comando acima retornar erro, `Approved for delivery: no`, `approved_for_delivery=false`, ou listar blockers, tratar como revisão reprovada; corrigir o documento, rerodar `register_keywords.py --cv` e rerodar a revisão
- warnings não bloqueiam entrega sozinhos; registrar os warnings no bloco final quando existirem
- `pt_cv_keyword_shotgun_control` é blocker em CV PT-BR quando o gate detectar cluster artificial de keywords em inglês; se aparecer em blockers, reescrever o CV, rerodar `register_keywords.py --cv` e rerodar a revisão
- o `output-reviewer` deve executar polimento textual obrigatório em todo CV PT-BR, mesmo quando `pt_cv_keyword_shotgun_control` não disparar; se o polimento alterar resumo ou bullets, regenerar o DOCX, registrar ATS e revisar novamente
- se o reviewer reprovar top 8 por `missing_unexplained` e o CV já tiver equivalente PT-BR defensável, corrigir `keyword_translation_registry.json` antes de recorrer a keyword exata em inglês; não resolver falta de equivalência criando shotgun
- política ATS top 8: `covered_exact=1,0`, `covered_similar=0,8`, `declared_gap=0`, `missing_unexplained=0`; aprovação mínima exige score >= 5,2/8 e zero `missing_unexplained`; ótimo exige >= 6,2/8
- nunca aprovar por autoavaliação textual; o relatório `outputs/_tmp/output_review_report.json` é evidência obrigatória

**Passo 8 — Limpar temporários**

Excluir o arquivo correspondente em `outputs/_tmp/` na mesma execução, somente após validação final, revisão aprovada e confirmação de que o registro ATS foi atualizado com o final em `outputs/`.

Exemplo:

```bash
rm <workspace>/outputs/_tmp/cv_[escopo].docx
```

Se houver PDF, manter apenas o artefato final em `outputs/`.

**Passo 9 — Entregar**

O arquivo final já deve estar em `outputs/`.

Se a entrega OneDrive/rclone estiver configurada, confirmar que `cv:deliver` foi executado com `status=delivered` no relatório `outputs/_tmp/delivery_report.json`. Se a entrega remota falhar mas `cv:approve` tiver aprovado o DOCX, declarar execução parcial: arquivo local aprovado em `outputs/`, entrega remota bloqueada.

---

## PIPELINE DE GERAÇÃO — PDF

Quando o usuário escolher PDF:

**Passo 1 — Gerar DOCX primeiro**
Seguir todos os 6 passos do pipeline DOCX acima, incluindo validação e theme.
O DOCX aprovado serve como base para conversão.

**Passo 2 — Converter para PDF via LibreOffice**

```bash
sh scripts/docx/convert_pdf.sh --docx-path <workspace>/outputs/felipe_armel_cv_[escopo].docx --output-dir outputs
# O PDF gerado fica no mesmo diretório com o mesmo nome base
```

**Passo 3 — Entregar**

Chamar `entrega local em outputs/` com `outputs/felipe_armel_cv_[escopo].pdf`.

---

## BLOCO DE AJUSTES VISÍVEL AO USUÁRIO

Após entregar o arquivo, exibir:

```
Ajustes narrativos aplicados neste CV:
• [Empresa] "[resultado]" reposicionado como resposta à dor "[dor_central]"
• [Empresa] ângulo "[faceta]" ativado — [motivo]
• [Narrativa protegida aplicada]: [qual e onde]

Keywords do anúncio cobertas no CV: [lista]
Keywords do anúncio sem cobertura: [lista]
```

---

## PITFALLS RECENTES (adicione aqui conforme descobertas)

| Pitfall | Sintoma | Correção |
|---------|---------|----------|
| Links do cabeçalho incompletos | Apenas LinkedIn com hyperlink, telefone e email são texto puro | Aplicar `ExternalHyperlink` em TODOS os contatos: LinkedIn (`https://linkedin.com/in/felipearmel`), WhatsApp (`https://wa.me/5511986748218`), Email (`mailto:armelfelipe@gmail.com`) |
| Renault com 2 bullets | Experiência da Renault aparece com apenas 2 bullets | Sempre 3 bullets no modo conciso. O terceiro bullet deve cobrir estruturação do modelo escalável de CS |
| Renault fora de sequência cronológica | Renault (jan/2018-out/2018) aparece depois de VivaReal (2015-2017), quebrando ordem cronológica inversa | Verificar datas de TODAS as experiências no autoconhecimento.md antes de montar a ordem. A sequência correta é: WeHandle → iFood Diretor → iFood Head → Renault → VivaReal → Trifil |
| Tom do resumo genérico | Resumo termina com frase de efeito ("Trajetória que une métricas, dashboards e colaboração multifuncional...") | Frases de efeito e autoproclamação são PROIBIDAS. O resumo deve ser factual: contexto + o que fez + número. Sem linguagem de coach. |
| Seção Competências questionada | Usuário pergunta de onde veio a seção Competências com as tags ATS | A seção Competências é intencional e especificada no AGENTS.md: estratégia de duas camadas (keywords ATS nas tags sem poluir bullets em português). O `review_output.py` aprova com 11/11 minors e ATS 8.0/8 justamente por essa cobertura. |

## Execucao Multiagente

Quando acionada pelo maestro, esta skill deve operar como `cv-agent`.

Entrada obrigatoria:
- ler primeiro `.career-state/agent_requests/cv_request.json` ou `.career-state/agent_requests/cv_request.md`
- usar `.career-state/fit_map.json` como fonte de aderencia
- respeitar somente os arquivos e comandos permitidos no request

Saida obrigatoria:
- gerar o DOCX em `outputs/`
- rodar `npm run validate:docx`
- rodar `npm run cv:deliver -- --artifact outputs/<cv>.docx` quando a entrega OneDrive/rclone estiver configurada
- usar `npm run cv:approve -- --artifact outputs/<cv>.docx` apenas como gate local/diagnóstico ou quando a entrega remota estiver indisponível

Proibido neste modo:
- aprovar CV por leitura visual ou por inspeção do script gerador
- limpar `outputs/_tmp/` antes do gate objetivo aprovar o DOCX final
- alterar numeros criticos, idioma ou narrativas protegidas para aumentar matching
- criar scripts temporarios na raiz

## REGRAS CRÍTICAS — NUNCA VIOLAR

- **Formato de saída: sempre perguntar DOCX ou PDF antes de gerar. Nunca HTML. Nunca assumir.**
- **Nome do arquivo: padrão obrigatório `felipe_armel_cv_[cargo]_[empresa].[ext]` — acrescentar `_en` antes da extensão quando o CV for em inglês. Exemplos: `felipe_armel_cv_diretor_logistica_supply_chain_kraft_heinz.docx` | `felipe_armel_cv_merchant_operations_manager_keeta_en.docx`. Nunca usar nomes genéricos como `cv_final`, `cv_armel` ou similar.**
- **Font size: `pt = n * 2` (half-points). NUNCA `n * 20` (twips). 9pt=18, 12pt=24.**
- **Pipeline DOCX: executar todos os passos em ordem, incluindo limpeza obrigatória de `outputs/_tmp/`. Não pular validação nem theme.**
- **Nunca limpar `outputs/_tmp/` antes de confirmar que o histórico ATS já foi atualizado a partir do DOCX final em `outputs/`.**
- **Pipeline PDF: sempre gerar DOCX primeiro, converter depois.**
- **`outputs/_tmp/` nunca é diretório de entrega. Os intermediários devem ser removidos antes do encerramento da execução.**
- Sem número = bullet inválido
- Nunca inventar dados, experiências, ferramentas ou certificações
- Nunca afirmar P&L total — usar alavanca operacional real
- Nunca posicionar VivaReal CS como gestão — sempre arquitetura
- Nunca usar fill rate para VivaReal
- Nunca incluir espanhol
- Nunca usar "Fluente" para inglês
- Nunca usar emojis no cabeçalho
- Nunca centralizar o cabeçalho
- Nunca dois dados de contato na mesma linha
- Resumo máximo 480 caracteres
- BSP em português: "MBA Corporate Strategy — BSP Business School São Paulo (2017)"
- BSP em inglês: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)"
- **Todos os contatos do cabeçalho com ExternalHyperlink: LinkedIn, WhatsApp (wa.me/5511986748218), Email (mailto:armelfelipe@gmail.com)**
- **Antes de escrever o script, verificar datas de todas as experiências no autoconhecimento.md para garantir ordem cronológica inversa correta**
- **Seção Competências com tags ATS é parte do pipeline, não erro — não remover**
