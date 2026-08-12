---
name: career-fit-analysis
instruction_modules: [runtime-core, intake-fit-map]
description: >
  Análise de aderência entre o perfil de Felipe Armel e uma vaga, cargo-alvo ou perfil de mercado.
  Use esta skill SEMPRE que: (1) uma descrição de vaga for fornecida para análise, candidatura ou geração de documentos;
  (2) o usuário pedir quais vagas ou cargos são mais aderentes ao seu perfil; (3) o usuário quiser construir
  posicionamento para um perfil novo sem vaga específica. Esta skill é pré-requisito obrigatório para cv-generator,
  feras-pitch, cover-letter e gupy-optimizer — todas as outras skills consomem o FIT_MAP produzido aqui.
  Ative também quando o usuário usar expressões como "analisa essa vaga", "como me encaixo nessa vaga",
  "quais vagas combinam comigo", "cria um posicionamento para", "qual cargo devo mirar".
---

# Career Fit Analysis

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/career-fit-analysis/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/career-fit-analysis/SKILL.md`.

## Adaptação Local OpenCode

Carregue os módulos declarados no front matter para regras globais e equivalência de caminhos. As referências ficam em `../career-system/references/`. Ao concluir a análise, não grave o FIT_MAP final manualmente. Gere primeiro um draft JSON estruturado no caminho canônico `.career-state/fit_map.draft.json`, valide o draft, e só então canonize com `scripts/build_fit_map.py`, validando em seguida com `scripts/validate_fit_map.py`.

Quando esta skill for acionada a partir do orquestrador de candidaturas:
- leia primeiro `analysis_request.json/md` da candidatura;
- produza somente `fit_map.draft.json`;
- não execute pipeline completo, não atualize Notion e não siga para geração de CV;
- trate referências longas como fallback, não como leitura inicial obrigatória.

Contrato operacional dos scripts locais:

- `scripts/build_fit_map.py` deve operar em modo **fail-closed**: se o draft vier com shape parcial, campo-placeholder, lista simplificada onde a skill exige objeto estruturado, ou conteúdo que perderia informação na canonização, o script deve falhar com erro objetivo em vez de preencher vazio ou degradar silenciosamente
- `scripts/validate_fit_map_draft.py` deve falhar se o draft ainda contiver placeholders, enums ambíguos ou shape inválido para canonização
- `scripts/validate_fit_map.py` deve validar não só schema, mas também **completude operacional mínima** do FIT_MAP final
- se qualquer script aceitar conteúdo incompleto e produzir falso positivo de conclusão, isso deve ser tratado como bug da stack e corrigido antes de considerar a skill confiável

Esta skill produz o FIT_MAP — output estruturado interno que alimenta todas as outras skills do projeto.
Nunca gere CV, FERAS, carta ou seleção Gupy sem ter o FIT_MAP construído primeiro.

Regra dura: esta skill não é apenas analítica. Ela é operacional. Ler este arquivo sem executar os scripts obrigatórios e sem atualizar `.career-state/fit_map.json` conta como execução incompleta.

Critério de conclusão desta skill:

- draft estruturado do FIT_MAP produzido
- `scripts/validate_fit_map_draft.py` executado com sucesso
- `scripts/build_fit_map.py` executado com sucesso
- `scripts/score_fit_map.py` executado com sucesso
- `scripts/validate_fit_map.py` executado com sucesso
- `.career-state/fit_map.json` atualizado para a vaga analisada
- `scripts/register_keywords.py` executado com sucesso
- descrição bruta da vaga preservada pelo mecanismo definido nesta skill
- bloco visível `Validação operacional da execução` preenchido com status real de cada etapa obrigatória

Se qualquer item acima não acontecer, a skill não foi concluída integralmente.

Comportamentos proibidos nesta skill:

- parar após leitura das referências e entregar apenas análise textual
- afirmar que construiu o FIT_MAP sem persisti-lo
- afirmar nota final se a matemática não estiver refletida no draft estruturado e no estado salvo
- salvar a descrição da vaga por atalho manual quando a skill exigir script específico
- oferecer geração de CV, pitch, carta ou Gupy antes da conclusão integral desta skill
- preencher a validação operacional com base em intenção, plano ou leitura da skill em vez de comandos realmente executados
- estimar ou declarar nota final antes da execução bem-sucedida de `scripts/score_fit_map.py`
- tentar ler ou inventar arquivo bruto presumido por nome, como `*_raw.txt`, sem que ele tenha sido realmente criado no runtime
- reutilizar `fit_map.json` ativo como resposta final quando a vaga foi colada na conversa e ainda não passou por novo `save_job_description.py` nesta execução

---

## MODOS DE OPERAÇÃO

Identifique o modo antes de qualquer passo:

**Modo 1 — Vaga específica**
Anúncio fornecido pelo usuário (texto colado, link, page_id do Notion, ou campo "Descrição da Vaga" do Notion).
→ Executar fluxo completo de extração + cruzamento + FIT_MAP.

**Modo 2 — Pesquisa de mercado (sem vaga)**
Usuário quer saber quais cargos são mais aderentes, sem vaga específica.
→ Puxar descrições do Notion (campo "Descrição da Vaga" do tracker "Aplicações", collection `3130003f-9481-80b9-a281-000b7782b9f8`) + pesquisa web por vagas dos 3 perfis-alvo.
→ Entregar output acionável por cargo: fit atual / o que você tem / o que falta / o que fazer.

**Modo 3 — Perfil reverso**
Usuário quer construir posicionamento para um cargo ou perfil novo, sem vaga real.
→ Pesquisar web por vagas desse cargo para extrair competências e keywords esperadas pelo mercado.
→ Propor mapa de competências e keywords para validação do usuário ANTES de gerar qualquer documento.
→ Somente após validação, o mapa aprovado substitui o FIT_MAP e alimenta as outras skills.

---

## FLUXO — MODO 1 (VAGA ESPECÍFICA)

### Passo -1 — Intake obrigatório

Antes de executar análise de vaga, normalizar a origem com o orquestrador:

```bash
npm run intake:notion-record -- <id_unico>
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>
cat <arquivo> | npm run intake:paste -- --company "<empresa>" --role "<cargo>" --stdin
npm run intake:linkedin-job -- --url "<url-da-vaga>"
npm run intake:linkedin-post -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
npm run intake:url -- --url "<url>" --company "<empresa>" --role "<cargo>"
npm run intake:resume
```

Se o intake retornar `next_required_step = fill_fit_map_draft`, a próxima ação é preencher `.career-state/fit_map.draft.json`.
Não usar `notion:list`, `grep`, cache local, URL aberta no navegador genérico ou FIT_MAP antigo como substituto do intake.

### Bloqueador crítico — Verificação de vaga ativa (anti-reuse)

**Falha operacional grave:** entregar análise, score ou resumo de vaga ANTERIOR quando o usuário forneceu vaga nova.

Sintomas do erro (já ocorreu em produção):
- `npm run fit-map:summary` retorna cargo/empresa de vaga antiga
- `.career-state/fit_map.json` tem `matches_active_job = false` mas o agente ignora
- Agente declara "FIT_MAP finalizado" com score de vaga que não é a atual

**Protocolo obrigatório de verificação antes de qualquer análise ou entrega:**

```bash
# 1. Verificar se FIT_MAP ativo corresponde à vaga atual
npm run fit-map:status

# 2. Se matches_active_job = false, o FIT_MAP é STALE — bloquear e re-analisar
# 3. Se draft tem placeholders > 0, a vaga ativa ainda não foi analisada
```

Regras duras:
- Se `fit_map.json.matches_active_job = false`, **NÃO** entregar score, **NÃO** usar `.career-state/fit_map.json` como base, **NÃO** prosseguir para CV/FERAS/carta
- Se `draft.placeholder_count > 0`, a próxima ação obrigatória é editar `.career-state/fit_map.draft.json` — não entregar análise textual
- Se o usuário reclamar que a análise não é da vaga correta, executar imediatamente `npm run fit-map:status` e `npm run intake:resume` para diagnosticar drift
- Nunca confiar em estado de sessão anterior sem revalidar fingerprint da descrição ativa
- Quando houver dúvida sobre qual vaga está ativa, ler `.career-state/workflow_state.json` e `inbox/job_descriptions/` para confirmar o path da descrição salva
O campo `delivery_plan` do intake orienta as próximas skills: CV, FERAS, carta, habilidades e update no Notion.
Nesta etapa, o agente deve editar o draft no filesystem. É execução parcial/falha operacional responder com o template do JSON, pedir que o usuário preencha campos, sugerir `nano`/editor, ou listar passos para preenchimento sem persistir o arquivo.
Em modo multiagente/local pequeno, gerar/ler `.career-state/agent_requests/fit-map_request.md` com `npm run multiagent:request -- fit-map` e seguir as `Operational Rules` antes de editar.
Depois de qualquer edição de `.career-state/fit_map.draft.json`, executar `npm run validate:fit-map:draft`. Se o JSON estiver inválido ou a validação falhar, corrigir e reexecutar antes de responder ao usuário.

Regra de contexto compacto:
- editar e validar `.career-state/fit_map.draft.json` no filesystem; não colar o draft, FIT_MAP ou diff completo na conversa
- `npm run validate:fit-map:draft` e `npm run validate:fit-map` retornam resumo compacto por padrão; usar `--full` apenas em manutenção explícita
- após `npm run fit-map:finalize`, rodar `npm run fit-map:summary` e `npm run validate:fit-map:quality` antes de entregar análise feita por modelo local
- em sessão direta Hermes/OpenCode/Codex fora do `HarnessSupervisor`, análise de vaga não termina no intake, extração, template, guard, leitura de request ou `validate:fit-map:draft`; continuar até `fit_map.json` final validado, resumo oficial e menu de próximos passos
- quando precisar inspecionar JSON, usar campos específicos ou projeções pequenas; nunca `cat` no FIT_MAP/draft/registry/cache
- a resposta ao usuário deve citar paths, contagens, nota e blockers, não payloads internos

### Primeiras 5 ações obrigatórias

Quando a vaga vier por texto colado em chat, a ordem inicial e obrigatória e esta:

1. Executar `npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>` ou `--stdin`, que salva o texto bruto, recria o template e registra `active_intake`. O uso direto de `scripts/save_job_description.py` fica como fallback manual.
2. Ler os 4 arquivos de referencia obrigatorios:
   - `../career-system/references/dicionario_palavras_chave_mercado.md`
   - `../career-system/references/palavras_chave_carreira.md`
   - `../career-system/references/autoconhecimento.md`
   - `../career-system/references/perfil_restricoes.md`
3. Extrair keywords, competencias da vaga e dor central.
4. Gerar o template canônico com `npm run fit-map:template` e preencher `.career-state/fit_map.draft.json`.
5. Validar o draft com `npm run validate:fit-map:draft`.
6. Canonizar, pontuar e validar o FIT_MAP; so depois registrar keywords ATS e fechar a associacao final da descricao da vaga com `--fit-map`, se necessario.

Regra anti-loop:
- depois de carregar esta skill, a proxima resposta deve executar uma acao concreta do passo atual; nao repetir o workflow completo
- em respostas como `continue`, retomar do ultimo passo nao executado; nunca reiniciar do passo 1 sem necessidade
- depois de salvar a vaga e ler as 4 referencias obrigatorias, a proxima acao deve ser `npm run fit-map:template`; nao explorar ajuda de script, schema antigo, drafts velhos ou caminhos alternativos nesse ponto

Politica anti-travamento:
- depois do Passo 1, nao gastar mais de 1 bloco de resposta apenas analisando texto sem executar o proximo comando concreto
- se a vaga ja estiver salva e as 4 referencias obrigatorias ja tiverem sido lidas, a proxima acao obrigatoria e preencher `.career-state/fit_map.draft.json`; nao ficar recalculando nota em texto livre antes disso
- a nota de aderencia pode ser preparada como classificacao item a item no draft, mas a nota final oficial so existe depois do pipeline `validate draft -> build -> score -> validate`; nao refazer a matematica repetidamente na conversa
- antes de preencher `.career-state/fit_map.draft.json`, nao escrever subtotais nem nota final na conversa; classificar itens, evidencias e severidades diretamente no draft
- em caso de duvida sobre retomada ou estado misto, executar `npm run fit-map:status` e seguir exatamente `next_required_step`
- se `next_required_step` for `preencher .career-state/fit_map.draft.json`, executar `npm run fit-map:resume` e então editar o draft; nao entregar mais uma análise textual antes da persistência
- se a vaga veio de seleção numérica da lista salva do LinkedIn, resolver a URL salva, executar `npm run intake:linkedin-job -- --url "<url>"` e seguir até FIT_MAP final; não pedir confirmação adicional para prosseguir
- se o draft foi lido e ainda tem placeholders, não resumir o template para o usuário; usar a descrição salva e as referências obrigatórias para substituir os placeholders no próprio arquivo
- se o draft ficar com JSON inválido por patch parcial, executar `npm run fit-map:template`, regenerar o request se necessário e recomeçar a edição a partir do template válido
- depois de `npm run fit-map:template`, executar `npm run fit-map:guard`; se retornar `guard=blocked`, a próxima ação deve ser o `required_next_command`, sem explicar o workflow nem continuar análise em texto livre
- nessa etapa, nao consultar `--help` dos scripts nem reutilizar draft de outra vaga como ponto de partida; o ponto de partida obrigatorio e o template canônico recem-gerado
- se houver erro objetivo de arquivo, caminho ou comando, corrigir e reexecutar imediatamente no mesmo fluxo; nao transformar o erro em longa explicacao
- se o agente passar 2 respostas consecutivas sem avancar de etapa, ele deve interromper a exposicao, declarar `execucao parcial/bloqueada` e rodar o proximo comando ou informar o bloqueio real
- quando o usuario escrever `continue`, `ta rodando?` ou equivalente, responder com o ultimo passo executado e a proxima acao concreta em 1-2 frases, depois executar

### Passo 0 — Origem da vaga

Se a vaga vier do Notion, usar o intake:

```bash
npm run intake:notion-record -- <id_unico>
```

Fallback técnico de leitura, apenas quando o intake estiver indisponível:

```bash
python scripts/notion_sync.py read-page <page_id> --save
python scripts/notion_sync.py prepare-analysis-from-page <page_id>
python scripts/notion_sync.py prepare-analysis-from-record <id_unico>
```

Extrair a descrição da vaga do payload salvo em `inbox/notion/` e do markdown persistido em `inbox/job_descriptions/`, então executar a análise normalmente.

Regra: leitura do Notion pode alimentar FIT_MAP, keywords, cobertura e gaps. Criação/atualização de registro no Notion não acontece nesta skill, a menos que o usuário peça explicitamente em mensagem separada. Quando isso acontecer e a origem tiver sido `page_id` ou `ID` único da tabela, a saída preferencial é atualizar a mesma página via `update-from-fit-map` ou `update-from-fit-map-record`, não criar uma página duplicada. A nota de aderência não altera essa decisão: score alto continua exigindo update quando a origem foi Notion.
Quando o usuário escrever `Avalie vaga Notion 218` ou equivalente, interpretar `218` como o valor do campo único `ID` da tabela.

Se a vaga vier de texto colado no chat, preservar o texto bruto imediatamente antes de qualquer leitura longa de referencias:

```bash
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo_com_texto_bruto_da_vaga>
python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo_com_texto_bruto_da_vaga>
```

Se o texto bruto ainda nao estiver em arquivo e vier direto da conversa/pipe, usar:

```bash
cat <<'EOF' | python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --stdin
<texto bruto da vaga>
EOF
```

`--fit-map` e opcional neste momento. Use `--company` e `--role` quando o FIT_MAP ainda nao existir. Se a empresa ou o cargo ainda estiverem provisórios, use o melhor nome defensável disponivel e, se necessario, rode o script de novo no Passo 10 com `--fit-map` para fechar a associacao final.

Regra dura deste passo:
- para vaga colada no chat, o agente nao deve tentar ler nenhum arquivo bruto deduzido por nome
- a unica origem persistida valida do texto bruto e o arquivo efetivamente salvo via `scripts/save_job_description.py`
- `--text-file` exige um caminho real; `--text-file -` nao usa stdin neste script
- para texto vindo direto da conversa, preferir `--stdin`
- se precisar reler a vaga, reler o arquivo salvo em `inbox/job_descriptions/` ou usar o proprio texto ainda presente no contexto; nunca presumir `_raw.txt`
- mesmo que exista `fit_map.json` ativo com empresa/cargo iguais, a vaga colada exige nova persistencia do bruto nesta execucao antes de qualquer reuso de estado

### Passo 1 — Extração dupla do anúncio

Extraia separadamente:

**A) Keywords da vaga** — os termos exatos que aparecem no texto do anúncio:
- Do título do cargo
- Dos requisitos obrigatórios
- Das responsabilidades
- Dos diferenciais / desejáveis
- Registre a origem de cada termo (título / requisitos / responsabilidades / diferenciais)

**B) Competências da vaga** — o que a vaga exige que o candidato SAIBA FAZER:
- Hard skills (técnicas, metodologias, ferramentas)
- Soft skills (comportamentos, liderança, comunicação)
- Ferramentas específicas (sistemas, plataformas)
- Conhecimento de setor (logística, marketplace, SaaS, fintech etc.)

Keywords ≠ Competências. Keywords são os termos para ATS. Competências são as capacidades exigidas.
Mantenha as duas listas separadas no FIT_MAP.

### Passo 2 — Identificar a dor central

Antes de cruzar com a base, identifique em 1–2 frases o problema principal que a empresa quer resolver contratando essa posição. Esta frase guia toda a seleção de histórias e ângulos narrativos nas etapas seguintes.

Exemplos de dor central:
- "Empresa em crescimento acelerado precisa estruturar operações logísticas que ainda são manuais e não escalam"
- "Marketplace consolidado precisa reduzir custo logístico sem sacrificar nível de serviço"
- "SaaS B2B com operação de atendimento cara e reatência precisa de transformação via automação e dados"

### Passo 3 — Cruzamento com a base de conhecimento

Para cada keyword e competência extraída, consulte os arquivos de referência nesta ordem:

1. `dicionario_palavras_chave_mercado.md` → Seção 1 (pode usar) / Seção 2 (não pode usar) / Seção 3 (sinônimos)
2. `palavras_chave_carreira.md` → localizar empresa, cargo e história correspondente
3. `autoconhecimento.md` → validar contexto, número e defensabilidade
4. `perfil_restricoes.md` → verificar narrativas protegidas e números críticos

Para cada item, classifique o tipo de ajuste:

**DIRETO** — Armel tem a experiência exata e o termo casa diretamente (via sinônimo validado ou termo igual).
Ação: usar a frase pronta do dicionário, adaptada ao contexto.

Regra dura de `DIRETO`:
- só usar `DIRETO` quando houver equivalência literal suficiente de **contexto**, **escopo** e **objeto operacional** do item pedido
- mudança relevante de setor, canal, tipo de operação, tipo de ativo operado, ambiente regulatório, malha logística ou natureza do parceiro elimina `DIRETO` por padrão
- se a cobertura depender de tradução entre contextos, o item não é `DIRETO`; ele cai para `REPOSICIONAMENTO` ou `GAP`
- em caso de dúvida entre `DIRETO` e `REPOSICIONAMENTO`, usar `REPOSICIONAMENTO`

**REPOSICIONAMENTO** — Armel tem a experiência mas o ângulo precisa mudar para ressoar com a dor da vaga.
Ação: identificar qual aspecto da história colocar na frente; registrar o ajuste feito em `ajustes_feitos`.
Regra: nunca inventar — só escolher qual faceta real da história enfatizar.

**GAP** — Não há experiência defensável na base para este item.
Ação: registrar em `gaps_sem_cobertura`. Nunca tentar cobrir com narrativa forçada.
Se for gap crítico (requisito obrigatório da vaga): sinalizar como objeção forte.

Teste curto de classificacao:
- se nao existe experiencia real comprovada na base, e `GAP`
- se existe experiencia real e ela e igual ou quase igual ao que a vaga pede, e `DIRETO`
- se existe experiencia real, mas ela nao e igual ao que a vaga pede e precisa de traducao honesta para caber na vaga, e `REPOSICIONAMENTO`

Regra dura de reposicionamento:
- `REPOSICIONAMENTO` nunca vira `DIRETO` por causa de narrativa forte, escrita boa ou analogia convincente
- o modelo so pode usar `REPOSICIONAMENTO` quando conseguir defender a frase:
  `Nao fiz exatamente X, mas fiz Y, que transfere parcialmente para X porque Z.`
- se essa frase nao puder ser defendida com fato real, empresa e resultado, o item nao e reposicionamento; e `GAP`

Teste de defensabilidade por tipo:
- `DIRETO`: ha prova real na base, o escopo e equivalente e a cobertura nao depende de analogia forte
- `REPOSICIONAMENTO`: ha prova real na base, mas a cobertura depende de transferencia parcial, mudanca de contexto ou combinacao de experiencias
- `GAP`: falta prova real, falta equivalencia suficiente ou o salto seria grande demais

Exemplos que por padrao **nao** autorizam `DIRETO` sem prova literal adicional:
- `gestao de parceiros logísticos` nao vira automaticamente `gestao de contratos com prestadores`
- `automacao industrial` ou `automacao com IA` nao vira automaticamente `automacao logistica`
- `operacao digital`, `last mile` ou `marketplace` nao vira automaticamente `operacao de CD fisico especializado`
- `lideranca de times` nao vira automaticamente `gestao direta de supervisores` quando o anuncio pede uma camada hierarquica especifica
- experiencia forte em setor nao regulado nao vira automaticamente cobertura direta para setor regulado ou contexto sanitario/farmaceutico

### Passo 4 — Conectar histórias à dor do contratante

Para cada história selecionada (ajuste direto ou reposicionamento), construa a ponte explícita:

> "Esta experiência resolve a dor [dor_central] porque [motivo específico com evidência], usando exatamente [keyword/competência da vaga]."

Este texto não vai para o CV diretamente — é o raciocínio que guia QUAL resultado colocar na frente e QUAL keyword usar no bullet.

### Passo 5 — Construir as objeções

Identifique 3 a 5 objeções que o recrutador vai levantar. Para cada uma:

| Campo | O que preencher |
|---|---|
| Objeção | O que o recrutador pensa |
| Classificação | forte / média / fraca |
| Por que surge | contexto que gera a objeção |
| Mitigação | como endereçar com evidência real |
| Evidência real | história + número da base |

Objeções recorrentes do perfil (sempre verificar):
- Gap de senioridade iFood → WeHandle (endereçar com narrativa de escolha consciente)
- Amplitude excessiva da carreira (endereçar com foco no escopo da vaga)
- Inglês não fluente (declarar avançado; não minimizar)
- Educação formal sem universidade de ponta (não inventar; reforçar BSP + FDC + resultados)
- Leitura de "executor operacional" vs "executivo de negócio" (endereçar com P&L, S&OP, interface C-level)

### Passo 6 — Calcular nota de aderência

**REGRA: nunca estimar. Sempre calcular item a item conforme o protocolo abaixo.**

A nota final é composta por 4 dimensões com pesos fixos:

| Dimensão | Peso |
|---|---|
| Requisitos obrigatórios | 40% = 4,0 pontos |
| Responsabilidades principais | 30% = 3,0 pontos |
| Ausência de gaps críticos | 20% = 2,0 pontos |
| Diferenciais / desejáveis | 10% = 1,0 ponto |

#### Protocolo de cálculo por dimensão

**1. Listar todos os itens da dimensão** extraídos do anúncio no Passo 1.

**2. Atribuir nota por item** usando escala obrigatória:
- **1,0** = cobertura plena e direta (DIRETO no mapa de ajuste)
- **0,5** = cobertura parcial ou por reposicionamento (REPOSICIONAMENTO no mapa de ajuste)
- **0,0** = sem cobertura defensável (GAP no mapa de ajuste)

**3. Calcular % de cobertura da dimensão:**
```
% cobertura = soma das notas dos itens / contagem total de itens
```

**4. Calcular pontos da dimensão:**
```
pontos = % cobertura × peso da dimensão (em pontos)
```

**5. Nota máxima possível por item:**
```
nota_maxima_item = peso_dimensao / contagem_itens_dimensao
```
Este valor representa quanto cada item vale se a cobertura for 1,0.

**6. Ponderação por item:**
```
ponderacao_item = (nota_item / 1,0) × nota_maxima_item
```

**7. Somar pontos de todas as dimensões → nota final em escala 0–10.**

#### Regras de preenchimento

- Todo item extraído do anúncio deve aparecer no cálculo — nenhum pode ser omitido
- Itens ambíguos (sem evidência clara) recebem 0,5, nunca 1,0 por benefício da dúvida
- A dimensão "ausência de gaps críticos" é calculada inversamente: cada gap crítico (🔴) desconta 1,0; cada gap médio (🟡) desconta 0,5; gap leve (🟢) desconta 0,0 — aplicado sobre o máximo de 2,0 pontos
- Mostrar o cálculo completo no output — nunca suprimir
- Nota 1,0 só é permitida quando houver evidência direta e literal na base para aquele item; analogia, repertório semelhante ou equivalência operacional recebem no máximo 0,5
- `REPOSICIONAMENTO` pontua no máximo 0,5 mesmo quando a história for excelente; narrativa forte nao converte cobertura parcial em cobertura plena
- Para itens sensíveis como `motoristas/ajudantes`, `combustível/pedágio/horas extras` e `distribuição de alimentos/perecíveis`, ausência de prova literal deve gerar gap explícito
- Para gaps de contexto material, o default deve ser conservador: setor regulado, operação física especializada, CD setorial, operação sanitária/farmacêutica, tipo de malha muito específica e requisito explícito de contexto setorial nao podem ser marcados como `leve` por conveniência; na ausência de prova literal, classificar como `medio` ou `forte` e justificar
- Gap material reconhecido em `gaps_sem_cobertura` ou em `ausencia_gaps_criticos` deve ter reflexo real na nota; nao registrar gap material em texto e manter cobertura de gaps em 100%
- Nota final em faixa de excelência (`9,5+`) exige ausência de gap material nao coberto literalmente; se houver gap setorial, regulatório ou operacional-chave, a nota deve ficar abaixo dessa faixa, salvo justificativa explícita e defensável no draft

#### Estrutura obrigatória para o draft da nota

Ao montar o draft, `nota_aderencia` não deve ser apenas um número solto. Ela deve vir como objeto com os itens já classificados, para que o script faça a matemática:

```json
{
  "final": null,
  "dimensoes": {
    "requisitos_obrigatorios": {
      "itens": [
        { "item": "texto do item", "tipo": "DIRETO", "evidencia": "empresa + historia", "resultado": "numero", "nota": 1.0, "prova_literal": true, "fonte_base": "autoconhecimento.md:L123-L126" }
      ]
    },
    "responsabilidades_principais": {
      "itens": [
        { "item": "texto do item", "tipo": "REPOSICIONAMENTO", "evidencia": "empresa + historia", "resultado": "numero", "nota": 0.5, "prova_literal": false, "fonte_base": "autoconhecimento.md:L210-L216" }
      ]
    },
    "ausencia_gaps_criticos": {
      "gaps": [
        { "gap": "texto do gap", "severidade": "forte" }
      ]
    },
    "diferenciais_desejaveis": {
      "itens": [
        { "item": "texto do item", "tipo": "DIRETO", "evidencia": "empresa + historia", "resultado": "numero", "nota": 1.0, "prova_literal": true, "fonte_base": "autoconhecimento.md:L180-L186" }
      ]
    }
  }
}
```

O modelo define os itens, notas e severidades. O script calcula `final`, pontos e cobertura.

### Passo 7 — Selecionar histórias para os documentos

Selecione as 3 histórias principais que serão usadas em CV, FERAS e carta. Critério de seleção:
1. Maior sobreposição com a dor central da vaga
2. Número mais defensável e relevante para o cargo
3. Cobertura das keywords mais críticas do anúncio

Registre para cada história:
- Empresa de origem
- Resultado principal (número validado em `perfil_restricoes.md`)
- Keywords da vaga que esta história cobre
- Ângulo narrativo sugerido (qual aspecto colocar na frente)
- Ajustes feitos (lista explícita)

### Passo 7.5 — Mapa de keywords-habilidade para ATS

Após selecionar as histórias e antes de montar o FIT_MAP, construir a lista de **15 keywords-habilidade** que o ATS vai buscar como string exata no CV.

**O que são keywords-habilidade:**
Termos compostos que representam competências de gestão e operações — não ferramentas táticas (Grafana, Excel), não soft skills genéricas (liderança, comunicação). Exemplos: "Warehouse Operations", "Supply Chain Management", "Inventory Management", "S&OP", "Capacity Planning", "OTIF", "Cost Reduction", "Strategic Sourcing".

**Como extrair:**
1. Do título da vaga, requisitos obrigatórios e responsabilidades — termos que descrevem o que o candidato deve saber fazer
2. Da dor central — termos que descrevem a capacidade que a empresa busca
3. Do vocabulário do setor da empresa — termos que profissionais da área usariam para descrever essas competências

**Como priorizar:**
Ordenar as 15 keywords por relevância para a dor central, considerando: frequência no anúncio, posição no anúncio (título > requisitos > responsabilidades > diferenciais) e criticidade para o contexto da empresa.

**Como mapear onde cada keyword vai cair no CV:**

Para cada keyword, buscar em qual experiência e bullet ela pode ser inserida como termo exato:

1. **Primeiro**: buscar nas histórias já selecionadas no Passo 7 — verificar se o termo exato já apareceria naturalmente em algum bullet
2. **Se não houver encaixe natural**: buscar em `palavras_chave_carreira.md` e `autoconhecimento.md` experiências adicionais que contenham evidência real para essa keyword — mesmo experiências que não estavam entre as selecionadas
3. Se uma experiência adicional for encontrada e aumentar a densidade de keywords sem diluir o posicionamento, registrá-la como candidata com origem "adicionada por densidade"
4. Se nenhuma experiência cobrir a keyword com evidência real: registrar como gap de keyword

**Produto — tabela `keywords_habilidade_ats`:**

Para cada keyword, registrar:
```
{
  keyword: string,                    // termo exato para ATS (em inglês se CV em inglês)
  prioridade: 1-15,                   // ordem de relevância
  experiencia_alvo: string,           // empresa + cargo onde o termo vai aparecer
  bullet_sugerido: string,            // Responsável / Utilizando / Consegui / Resumo / Stack
  origem: "já selecionada" | "adicionada por densidade" | "gap sem cobertura"
}
```

**Regra de sinalização:** se alguma experiência for adicionada por densidade, sinalizar ao usuário antes de prosseguir — o usuário decide se entra no CV como experiência adicional, como menção no resumo, ou se é descartada. Nunca adicionar experiência ao CV silenciosamente por causa de uma keyword.

### Passo 8 — Montar o draft estruturado do FIT_MAP

Antes de preencher qualquer campo do draft, executar:

```bash
npm run fit-map:template
npm run fit-map:guard
```

Regra dura deste passo:
- o caminho canônico do draft é `.career-state/fit_map.draft.json`
- não criar drafts paralelos em `inbox/`, `outputs/` ou arquivos temporários arbitrários
- o agente deve preencher o template existente, não inventar um JSON do zero
- se `fit-map:guard` retornar bloqueado, qualquer resposta sem edição do draft é execução parcial
- não usar draft de vaga anterior como base estrutural; copiar conteúdo antigo só é aceitável se o usuário pedir explicitamente comparação ou reaproveitamento
- não estimar a nota final antes do `score_fit_map.py`; manter `nota_aderencia.final = null` no draft

```
FIT_MAP = {
  cargo, empresa, modo,
  dor_central,
  keywords_vaga: [ {termo, origem} ],
  competencias_vaga: [ {competencia, tipo} ],
  keywords_para_ats: [ str ],  // lista final para garantir nos textos
  mapa_ajuste: [
    { termo_vaga, tipo_ajuste, evidencia, empresa_origem,
      resultado_numero, angulo_sugerido, ajustes_feitos[], defensavel }
  ],
  objecoes: [
    { objecao, classificacao, origem, mitigacao, evidencia_real }
  ],
  nota_aderencia,
  gaps_sem_cobertura: [ str ],
  historias_selecionadas: {
    principal: { empresa, resultado, keywords_cobertas[], angulo, ajustes[] },
    secundaria: { ... },
    terceira: { ... }
  },
  keywords_habilidade_ats: [
    { keyword, prioridade, experiencia_alvo, bullet_sugerido, origem }
  ]  // 15 keywords ordenadas por prioridade — ver Passo 7.5
}
```

Enums obrigatórios do draft:
- `keywords_vaga[].origem`: somente `titulo`, `requisitos`, `responsabilidades`, `diferenciais`
- `competencias_vaga[].tipo`: somente `hard skill`, `soft skill`, `ferramenta`, `setor`
- `mapa_ajuste[].tipo_ajuste`: somente `DIRETO`, `REPOSICIONAMENTO`, `GAP`
- `objecoes[].classificacao`: somente `forte`, `media`, `fraca`

Regras anti-erro:
- nunca usar `descricao` ou `descrição` em `keywords_vaga[].origem`
- quando o termo vier do corpo da vaga, mapear para `responsabilidades` ou `requisitos`
- nunca usar `requisito`, `idioma` ou `qualificacao` em `competencias_vaga[].tipo`; nesses casos usar `hard skill`

Pitfall — validador rejeita `-` como placeholder fraco em GAPs:
- `validate:fit-map:draft` falha com "contains weak placeholder: '-'" quando `evidencia`, `empresa_origem` ou `resultado_numero` de um item GAP contém apenas `-`
- a correção é substituir por texto explícito prefixado com `GAP:`, ex: `"GAP: Nao ha experiencia em agencia de servicos ou consultoria."`
- para `empresa_origem` e `resultado_numero` de GAPs, usar `"GAP"` como valor
- fazer a substituição em lote via `execute_code` com Python `json` module quando houver múltiplos GAPs — `patch` tende a falhar em JSON grande por diferenças de whitespace/indentação

Este bloco agora deve ser tratado como draft estruturado da análise. O modelo pode montar o conteúdo, mas a persistência final deve passar por validação do draft e canonização.

Regra de progressao do Passo 8:
- concluiu keywords, dor central, gaps e historias principais? pare a analise textual e monte o draft imediatamente
- nao expandir racionalizacao item a item por varios paragrafos antes de salvar o draft
- nao calcular nem publicar subtotais de aderencia no chat antes de persistir o draft; o score conversacional antes de `fit-map:score` e invalido
- se algum item estiver incerto, registrar a incerteza no campo apropriado do draft e deixar o pipeline validar; nao adiar a persistencia por perfeccionismo

Checkpoints opcionais anti-travamento quando o modelo local estiver instavel:

```bash
npm run fit-map:check:extract
npm run fit-map:check:map-evidence
npm run fit-map:check:score-draft
npm run fit-map:check:complete-draft
```

Esses checkpoints validam partes do mesmo `.career-state/fit_map.draft.json` e servem para forcar persistencia incremental: extracao, evidencias, nota estruturada e fechamento do draft.

Regra de linguagem para drafts em português:
- keywords, competências, objeções e histórias devem ser escritas com ortografia portuguesa correta e acentos quando forem texto de exibição
- use formas sem acento apenas em slugs, chaves técnicas ou campos explicitamente pensados para matching
- não deixar a forma canonizada sem acento vazar para CV, carta, pitch ou qualquer output visível ao usuário
- se qualquer texto de exibição destinado ao Notion vier com mojibake (`Ã`, `Â`, `â€“`, `â€”`, `â€™`, `â€œ`, `â€`, `ï¿½`), tratar como artefato inválido e corrigir antes de devolver

### Passo 8.1 — Validar o draft do FIT_MAP

Depois de preencher `.career-state/fit_map.draft.json`, executar:

```bash
npm run validate:fit-map:draft
```

Regra de encerramento:
- se o draft falhar, corrigir o próprio `.career-state/fit_map.draft.json` e reexecutar
- não pular direto para `build_fit_map.py`

### Passo 8.2 — Canonizar e salvar o FIT_MAP

1. Usar o draft já validado em `.career-state/fit_map.draft.json`.
2. Executar:

```bash
npm run fit-map:build
npm run fit-map:score
npm run validate:fit-map
```

3. Somente após validação bem-sucedida considerar o FIT_MAP ativo.

O FIT_MAP é interno. Não exiba sua estrutura bruta na conversa, a menos que o usuário peça explicitamente.

Regra de encerramento: não encerrar a análise como concluída antes da execução bem-sucedida deste passo.

Regra de qualidade do estado salvo: `FIT_MAP valid` só tem valor operacional se o arquivo final preservar o conteúdo obrigatório da análise. Validação estrutural com campos vazios, listas-placeholder ou metadata sem utilidade prática não conta como conclusão correta da skill.

### Passo 9 — Registrar keywords ATS no histórico

Após canonizar, salvar e validar `.career-state/fit_map.json`, atualizar o registro persistente de keywords:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json
```

Esse registro alimenta CVs futuros e a adaptação do LinkedIn. Ele não autoriza usar keywords sem evidência; gaps continuam gaps.

Regra de encerramento: não apresentar a skill como concluída se este registro não tiver sido atualizado.

### Passo 10 — Fechar a associacao da descrição da vaga para Notion

Quando a vaga vier de texto colado pelo usuário, garantir que a descrição bruta ja esteja salva em `inbox/job_descriptions/`. Depois da canonização do FIT_MAP, voce pode rerrodar o script para usar empresa/cargo finais do estado ativo e fechar a associacao para o Notion.

Usar o script:

```bash
python scripts/save_job_description.py --fit-map .career-state/fit_map.json --text-file <arquivo_com_texto_bruto_da_vaga>
```

Esse arquivo é obrigatório caso o usuário peça posteriormente para criar registro em `Aplicações` no Notion, porque a criação deve preencher `Descrição da Vaga` além de nome e nota.

Regra de execução:
- quando a vaga vier de texto colado, o texto bruto deve ter sido salvo no Passo 0
- se o arquivo bruto inicial ja estiver correto e com nome suficiente para rastreabilidade, este passo pode servir apenas como confirmacao final com `--fit-map`
- nao substituir o fluxo por gravacao manual do arquivo bruto fora do script

---

## OUTPUT VISÍVEL AO USUÁRIO — MODO 1

Após construir o FIT_MAP, exiba na conversa:

**1. Dor central identificada**
Uma frase. Base para tudo que vem depois.

**2. Mapa único de aderência com cálculo detalhado**

Um único mapa consolidado substituindo o "mapa de ajuste resumido" e a "nota de aderência" separados. Exibir obrigatoriamente na seguinte estrutura:

**Cabeçalho do mapa — resumo da nota:**
```
Nota de aderência: X,XX / 10
```

**Tabela por dimensão — repetir para cada uma das 4 dimensões:**

| Item da Vaga | Tipo | Evidência | Resultado | Nota (0/0,5/1) | Nota Máx | Ponderação |
|---|---|---|---|---|---|---|
| [item extraído do anúncio] | DIRETO/REPOS/GAP | [empresa + história] | [número defensável] | X,X | X,XX | X,XX |
| ... | | | | | | |
| **Subtotal da dimensão** | | | | **Σ notas** | **Σ máx** | **Σ pond** |
| **% cobertura** | | | | | | **Σ pond / Σ máx × 100%** |
| **Pontos da dimensão** | | | | | | **% cob × peso** |

Legenda das colunas:
- **Nota**: 1,0 = cobertura plena · 0,5 = parcial/reposicionamento · 0,0 = gap
- **Nota Máx**: peso_dimensao / contagem_itens — quanto vale este item se coberto 100%
- **Ponderação**: nota × nota_máx — contribuição real deste item para a nota final

**Tabela de consolidação final (após os 4 blocos):**

| Dimensão | Peso | % Cobertura | Pontos |
|---|---|---|---|
| Requisitos obrigatórios | 40% / 4,0 | X% | X,XX |
| Responsabilidades principais | 30% / 3,0 | X% | X,XX |
| Ausência de gaps críticos | 20% / 2,0 | X% | X,XX |
| Diferenciais / desejáveis | 10% / 1,0 | X% | X,XX |
| **NOTA FINAL** | | | **X,XX / 10** |

**Regra de exibição:** Este mapa único substitui os itens "2. Nota de aderência" e "3. Mapa de ajuste resumido" da versão anterior. Nunca exibir nota sem o mapa. Nunca exibir mapa sem os números calculados.

**3. Ajustes narrativos aplicados**
Lista de todos os reposicionamentos feitos, com explicação de cada um:
```
• [Empresa] "resultado X" reposicionado como resposta à dor Y declarada no requisito Z
• [Empresa] ângulo de "W" ativado porque a vaga é [contexto]
• [Narrativa protegida] aplicada: [qual e por quê]
```

**4. Gaps sem cobertura**
Lista clara. Se gap crítico: sinalizar com impacto na candidatura.

**5. Objeções do recrutador**
Tabela: Objeção | Classificação | Mitigação | Evidência

**6. Keywords-habilidade para ATS**
Tabela das 15 keywords com mapeamento de onde cada uma vai cair no CV:

| # | Keyword | Experiência alvo | Bullet | Origem |
|---|---|---|---|---|
| 1 | [keyword mais relevante] | [empresa + cargo] | [Responsável/Utilizando/Consegui/Resumo/Stack] | já selecionada / adicionada / gap |
| ... | | | | |

Se houver experiências adicionadas por densidade: sinalizar quais e aguardar aprovação do usuário antes de prosseguir.

Se houver gaps de keyword (sem experiência real): listar e indicar se é aceitável (keyword secundária) ou problemático (keyword primária sem cobertura).

Regra anti-opcionalidade:
- esta tabela é entrega obrigatória da análise de aderência, não um próximo passo sugerido
- nunca encerrar a análise oferecendo "posso gerar a tabela de keywords cobertas" ou variação semelhante
- se `keywords_habilidade_ats` não existir ou estiver incompleta no FIT_MAP, a skill está parcial/incompleta; corrigir o draft e rerrodar validação/canonização antes de concluir
- próximos passos só podem sugerir documentos derivados depois que a tabela de keywords-habilidade tiver sido exibida ou houver bloqueio real declarado

**7. Validação operacional da execução**
Exibir obrigatoriamente um bloco de status ao final da análise. Este bloco não pode ser inferido; ele deve refletir apenas o que foi realmente executado no runtime:

| Etapa obrigatória | Status | Evidência objetiva |
|---|---|---|
| Draft estruturado do FIT_MAP produzido | executado / não executado | caminho do draft ou motivo da ausência |
| `scripts/validate_fit_map_draft.py` | executado / não executado | comando executado ou erro objetivo |
| `scripts/build_fit_map.py` | executado / não executado | comando executado ou erro objetivo |
| `scripts/score_fit_map.py` | executado / não executado | comando executado ou erro objetivo |
| `scripts/validate_fit_map.py` | executado / não executado | comando executado ou erro objetivo |
| `.career-state/fit_map.json` atualizado para a vaga analisada | executado / não executado | caminho + cargo/empresa salvos ou motivo da ausência |
| `scripts/register_keywords.py` | executado / não executado | comando executado ou erro objetivo |
| `scripts/save_job_description.py` ou fluxo equivalente definido na skill | executado / não executado | comando executado ou erro objetivo |

Regras deste bloco:
- se qualquer linha estiver como `não executado`, a skill deve ser apresentada como parcial ou incompleta
- nunca marcar `executado` sem evidência objetiva
- leitura de arquivo, intenção declarada ou planejamento não contam como evidência
- se houver falha de script, mostrar o erro de forma resumida na coluna `Evidência objetiva`
- se `validate_fit_map_draft.py`, `build_fit_map.py` ou `validate_fit_map.py` falharem por draft incompleto, shape inválido ou placeholder, o agente deve corrigir `.career-state/fit_map.draft.json` e reexecutar; nunca mascarar a falha com resumo manual

**8. Próximos passos sugeridos**
Quais documentos faz sentido gerar (CV qual persona, FERAS qual formato, carta, Gupy).

### Respostas curtas para formulários e entrevistas

Se o usuário pedir uma resposta de candidatura derivada das objeções/gaps:
- abrir respondendo diretamente `Sim`, `Não diretamente` ou a forma factual equivalente
- não usar enfeite retórico nem tese de adaptabilidade
- mitigar com fatos, não com promessa; evitar `eu aprenderia`, `eu faria o mesmo`, `setor-agnóstico`, `aprendo rápido`
- manter a narrativa presa ao FIT_MAP ativo, aos gaps reconhecidos e às evidências defensáveis da base

---

## FLUXO — MODO 2 (PESQUISA DE MERCADO)

1. Buscar no Notion (collection `3130003f-9481-80b9-a281-000b7782b9f8`) entradas com "Descrição da Vaga" preenchida.
2. Complementar com pesquisa web por vagas dos 3 perfis-alvo:
   - Head/Diretor de Operações Logísticas (marketplace: Mercado Livre, Magalu, Amazon)
   - Head/Diretor de Operações (logística scale-up: Loggi, Rappi, Lalamove)
   - Head de Customer/SaaS Operations (Fintech/B2B SaaS: Dock, Nuvemshop, Pagar.me)
3. Para cada cargo, extrair competências e keywords recorrentes. Consultar `../career-system/references/competencias_matrix.json` e `../career-system/references/competencias_por_experiencia.json` para cruzar com as competências já mapeadas no perfil.
4. Cruzar com a base de Armel usando o mesmo fluxo do Modo 1.
5. Entregar por cargo:

```
Cargo: [nome]
Fit atual: X/10
O que você tem: [lista com evidências]
O que falta: [gaps reais com grau de criticidade]
O que fazer para ser competitivo: [ações concretas — curso, projeto, narrativa]
Keywords mais exigidas que você cobre: [lista]
Keywords críticas sem cobertura: [lista]
```

---

## FLUXO — MODO 3 (PERFIL REVERSO)

1. Pesquisar web por 5–10 vagas reais do cargo/perfil alvo.
2. Extrair competências e keywords mais frequentes (>50% das vagas pesquisadas = obrigatório; <50% = diferencial).
3. Propor mapa para validação:

```
Proposta de mapa para [cargo/perfil]:

Competências obrigatórias pelo mercado:
• [competencia] — frequência: X/10 vagas
...

Keywords mais exigidas:
• [keyword] — [contexto de uso]
...

Competências diferenciais (aparecem em menos de 50% das vagas):
• [competencia]
...

Do seu perfil atual, você já cobre:
• [item] → evidência: [história + número]

Gaps a desenvolver ou posicionar:
• [item] → grau de criticidade: alto/médio/baixo
```

4. Aguardar validação do usuário antes de gerar qualquer documento.
5. Após validação, tratar o mapa aprovado como FIT_MAP e alimentar as demais skills.

---

## REGRAS CRÍTICAS — NUNCA VIOLAR

- Nunca usar termos da Seção 2 do `dicionario_palavras_chave_mercado.md` (lista de exclusão)
- Nunca afirmar P&L total — usar sempre a alavanca operacional real
- Nunca posicionar Armel como "gestor de CS" na VivaReal — sempre "arquiteto da área"
- Nunca atribuir fill rate à VivaReal — métrica pertence à Trifil
- Nunca declarar espanhol como competência
- Nunca alterar números — validar sempre contra `perfil_restricoes.md` seção NÚMEROS CRÍTICOS
- Nunca cobrir gap com narrativa forçada — declarar o gap com clareza
- BSP: em português = "MBA Corporate Strategy — BSP Business School São Paulo"; em inglês = "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo"
- Inglês: sempre "avançado" — nunca "fluente"
- WeHandle → iFood: sempre narrativa de escolha consciente, nunca retrocesso de senioridade

---

## CONSISTÊNCIA ENTRE DOCUMENTOS

Quando CV, FERAS e carta forem gerados a partir do mesmo FIT_MAP:
- As 3 histórias selecionadas no Passo 7 são as únicas usadas nos 3 documentos
- Os números são idênticos nos 3 documentos (validados em `perfil_restricoes.md`)
- As keywords para ATS aparecem em todos os documentos
- O ângulo narrativo de cada história é o mesmo nos 3 documentos
- A dor central norteia o tom de todos os documentos

Se o usuário pedir documentos em sessões separadas, pergunte se há um FIT_MAP ativo ou se deve gerar uma nova análise.

## Execucao Multiagente

Quando acionada pelo maestro, esta skill deve operar como `fit-map-agent`.

Entrada obrigatoria:
- ler primeiro `.career-state/agent_requests/fit-map_request.json` ou `.career-state/agent_requests/fit-map_request.md`
- usar somente os arquivos listados em `allowed_files`
- executar somente comandos listados em `allowed_commands`

Saida obrigatoria:
- preencher somente `.career-state/fit_map.draft.json`
- rodar as validacoes do request, especialmente `npm run validate:fit-map:draft`
- retornar status estruturado com `files_written`, `commands_executed`, `validation_result` e `blocker_reason`

Proibido neste modo:
- editar `.career-state/fit_map.json`
- rodar `npm run fit-map:finalize`
- escrever score final na conversa antes dos gates
- criar scripts temporarios na raiz para gerar ou reparar JSON
