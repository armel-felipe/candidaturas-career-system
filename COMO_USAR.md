# COMO USAR — Guia Operacional do Sistema de Candidatura

O runtime prioritario deste projeto e o **OpenCode**.
Ele le `AGENTS.md`, descobre skills via `.opencode/skills/`, executa scripts locais e produz os outputs finais deste repositorio.
Este documento e o manual de operacao do fluxo OpenCode-first.

O projeto agora tambem possui uma camada operacional estruturada em `src/career/`, com:
- `schemas` para contratos de dados
- `services` para logica reutilizavel
- `tasks` para orquestracao por dependencias
- `workflow` para controle de estado
- `scripts/career_cli.py` como CLI oficial

---

## 1. Arquitetura em uma linha

```
AGENTS.md  →  .opencode/skills/career-system/SKILL.md
                         ↓
              .opencode/skills/ (fonte canonica + discovery)
                         ↓
    .opencode/skills/career-system/references/   (fonte da verdade)
                         ↓
       .career-state/applications_v2/<ID>/       (memoria canonica da candidatura)
                         ↓
                         outputs/               (DOCX final e logs entregaveis)
                         outputs/_tmp/          (intermediarios de geracao; pode limpar apos entrega final)
                         scripts/generated/     (scripts especificos gerados)
```

O estado fica nos arquivos, nao no runtime. No fluxo novo, cada candidatura tem uma pasta propria em `.career-state/applications_v2/<ID>/`. O arquivo `.career-state/fit_map.json` continua existindo para skills gerais, mas o heartbeat usa a pasta da candidatura como fonte primaria.

### 1.1 Onde cada artefato fica

Para uma candidatura `236`, os principais arquivos ficam em:

```text
.career-state/applications_v2/236/state.json
.career-state/applications_v2/236/job_description.md
.career-state/applications_v2/236/fit_map.draft.json
.career-state/applications_v2/236/fit_map.json
.career-state/applications_v2/236/cv_content.json
.career-state/applications_v2/236/feras_formal.md
.career-state/applications_v2/236/habilidades_gupy.md
.career-state/applications_v2/236/habilidades_mercado_livre.md
.career-state/applications_v2/236/conversation_context.md
```

O DOCX final aprovado fica em:

```text
outputs/<cv>.docx
```

Logs ficam em:

```text
.career-state/applications_v2/_logs/
```

A memoria da candidatura e persistente: ela fica no disco ate alguem apagar a pasta ou ate uma rotina explicita de limpeza ser criada.

## 1.2 CLI estruturada

Os comandos oficiais do projeto podem ser disparados por `npm run ...` ou diretamente por:

```bash
python scripts/career_cli.py [subcomando]
```

Exemplos:

```bash
python scripts/career_cli.py notion refresh
python scripts/career_cli.py fit-map template
python scripts/career_cli.py fit-map status
python scripts/career_cli.py workflow show-state
```

## 1.3 Caminho canonico de execucao no OpenCode

Use sempre este caminho, sem variantes:

1. iniciar o OpenCode na raiz do projeto
2. deixar o runtime carregar `AGENTS.md` via `opencode.json`
3. ler `.opencode/skills/career-system/SKILL.md`
4. ler `.opencode/skills/{skill}/SKILL.md` da tarefa pedida
5. executar a proxima acao concreta da skill usando as tools reais do ambiente

Regra de interpretacao:
- skill e workflow, nao garantia de tool dedicada
- se existir uma tool generica `skill`, use-a apenas para carregar o conteudo da skill
- se nao existir, abra o `SKILL.md` diretamente
- a execucao da tarefa sempre acontece via leitura de arquivo, terminal, busca e edicao

## 1.4 Governança das skills

Para manutencao do projeto, existe uma regra unica:

- `.opencode/skills/{skill}/SKILL.md` e a fonte canonica
- qualquer ajuste, melhoria ou criacao de skill deve ser feito sempre em `.opencode/skills/`

Em outras palavras: OpenCode e Codex devem operar sobre o mesmo caminho fisico de skill.

---

## 2. Como acionar cada funcionalidade

### 2.1 Tabela de gatilhos

| Funcionalidade | Frase gatilho | Skill acionada |
|---|---|---|
| Analisar vaga | "Analisa essa vaga: [colar anúncio]" | `career-fit-analysis` |
| Quais cargos combinam comigo | "Quais cargos são mais aderentes ao meu perfil?" | `career-fit-analysis` modo 2 |
| Posicionamento para cargo novo | "Quero construir posicionamento para [cargo]" | `career-fit-analysis` modo 3 |
| Gerar CV | "Gera o CV para essa vaga" | `cv-generator` |
| Gerar CV geral | "Gera um CV geral para sites de emprego" / "CV geral conciso" | `general-cv-optimizer` |
| Gerar pitch / FERAS | "Gera o FERAS" / "Como me apresento para essa vaga?" | `feras-pitch` |
| Carta de apresentação | "Faz a carta de apresentação" | `cover-letter` |
| Habilidades Mercado Livre / Gupy | "Traga 10 habilidades Mercado Livre" / "Seleciona as habilidades do Gupy" | `habilidades-chave` |
| Mensagem LinkedIn | "Escreve a mensagem de networking para [perfil]" | `networking-message` |
| Draft de email / candidatura por Gmail | "Crie um draft de email de candidatura para [email]" | `self-email-draft` |
| Revisar documento | "Revisa o CV" / "Confere a carta" / "Está bom?" | `output-reviewer` |
| Candidatura completa via Notion | usar `run_agent_heartbeat_once.sh` | orquestrador por etapa |
| Sincronizar Notion | "Exporta para o Notion" / "Cria a página no Notion" | via `scripts/notion_sync.py` |

---

### 2.2 OpenCode — como invocar

OpenCode e acionado no terminal. Dois modos:

**Modo interativo (recomendado para candidaturas):**

```bash
# Iniciar sessão no diretório do projeto
cd "/Users/mac/Library/Mobile Documents/com~apple~CloudDocs/llm server/projetos/candidaturas"
opencode
```

Dentro da sessão interativa, use as mesmas frases da tabela acima.

**Modo direto (uma tarefa, sem sessão):**

```bash
opencode run "Analisa essa vaga e gera o FIT_MAP: [texto da vaga]"
opencode run "Gera o CV para a vaga de Head de Operacoes da Wellhub"
opencode run "Traga 10 habilidades Mercado Livre usando o FIT_MAP ativo"
opencode run "Seleciona as habilidades do Gupy usando o FIT_MAP ativo"
```

**Observacao:** OpenCode deve carregar `AGENTS.md` automaticamente ao iniciar no diretorio, conforme `opencode.json`.

### 2.3 Heartbeat automatico no MacBook

Para operar o fluxo automatico de candidaturas, prefira os arquivos `.sh` da raiz do projeto:

```bash
./run_agent_heartbeat_once.sh
./stop_active_agent_run.sh
# pausa: descarregue o LaunchAgent em ~/Library/LaunchAgents/com.felipe.candidaturas.heartbeat.plist
# retomar: reinstale com ./install_agent_heartbeat_60min.sh
./install_agent_heartbeat_60min.sh
```

Regras praticas:
- `run_agent_heartbeat_once.sh` pede confirmacao `RUN` antes de consumir modelo.
- `stop_active_agent_run.sh` pede confirmacao `STOP`, encerra heartbeat/OpenCode ativo e limpa locks locais.
- o arquivo `run_agent_heartbeat_once.sh` controla `--max-per-run`; ajuste ali quando quiser testar 1, 2 ou mais vagas.
- o modelo padrao fica em `.career-state/applications_v2/config.json`; para trocar, ajuste `active_model` e `active_variant`.
- o status `Reprocessar` no Notion limpa o pacote local da candidatura e força nova execução no próximo heartbeat.
- o heartbeat processa vagas em sequencia, nunca em paralelo.
- o modelo entra apenas nas etapas `analyze` e `generate`; render, reviewer, polish e update no Notion ficam com o orquestrador local.

### 2.4 Fluxo manual por candidatura

O projeto nao expoe mais comandos manuais por etapa/`record_id`.
O entrypoint operacional canonico das candidaturas e o heartbeat.

### 2.5 CV geral

Use `general-cv-optimizer` quando o objetivo for um CV mestre para sites de emprego, LinkedIn e busca ativa ATS.

```bash
npm run general-cv:strategy
npm run general-cv:strategy -- --mode expanded --bullet-count 5
npm run general-cv:strategy -- --mode concise --dominant-cluster operacoes_supply_logistica
```

Regras principais:
- `CV geral` sem modo usa expandido com 8 bullets por experiência
- `CV geral com X bullets` aceita X entre 4 e 8
- cada bullet narrativo expandido deve ter 270 a 330 caracteres
- `CV geral conciso` exige escolher um cluster dominante antes de gerar
- o DOCX geral final deve ser aprovado com `npm run general-cv:approve -- --artifact outputs/felipe_armel_cv_geral_operacoes_supply_chain.docx`

### 2.3 Gmail — drafts de email e candidatura

Para preparar a integracao local com Gmail:

```bash
npm run gmail:auth
```

Configuracao esperada no `.env`:

```env
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GMAIL_OAUTH_TOKEN_URI=https://oauth2.googleapis.com/token
GMAIL_OAUTH_REDIRECT_URI=http://localhost:8080/
GMAIL_OAUTH_LOCAL_PORT=8080
GMAIL_TOKEN_PATH=.secrets/gmail/token.json
```

Como invocar a skill:

```text
Crie um draft de email de candidatura para recrutador@empresa.com usando o template STARTUP, vaga Head de Operacoes, anexando outputs/meu_cv.docx
```

```text
Use a skill self-email-draft para preparar um email de candidatura multinacional para talentos@empresa.com com o CV outputs/felipe_armel_cv.docx
```

Regra operacional:
- o remetente e sempre a conta Gmail autenticada pelo OAuth local; nao informar nem perguntar email de envio
- a skill sempre revisa ortografia/fluidez, remove termos internos ou canonicos, e mostra destino, assunto, corpo completo e anexos antes de criar o draft real
- `python scripts/review_email_text.py --subject "<assunto>" --body "<corpo>"` precisa passar antes do preview aprovado e antes do draft real
- o usuário precisa aprovar explicitamente com algo como "aprovado", "pode criar" ou "gera o draft"
- antes da aprovação, no máximo usar `--dry-run`
- nunca enviar email automaticamente

---

## 3. Fluxo completo com ordem obrigatória

```
analyze        (modelo preenche fit_map.draft.json; finalizacao local gera fit_map.json)
   ↓
generate       (modelo gera cv_content.json, FERAS e habilidades)
   ↓
postprocess    (orquestrador renderiza DOCX, registra keywords, roda reviewer e polish)
   ↓
finalize       (orquestrador atualiza Notion e fecha estado)
```

No fluxo automatico, o modelo nao executa o pipeline inteiro. Ele so atua nas etapas textuais curtas:
- `analyze`: gera apenas `.career-state/applications_v2/<ID>/fit_map.draft.json`
- `generate`: gera apenas `cv_content.json`, `feras_formal.md`, `habilidades_gupy.md` e `habilidades_mercado_livre.md`
- nao existe mais etapa manual exposta de `repair`; qualquer reabertura deve acontecer no proprio heartbeat v2

O orquestrador local faz selecao da fila, estado, score, DOCX, reviewer, polish, registro ATS e Notion.

No uso manual por skill, `career-fit-analysis` continua sendo pré-requisito de CV, FERAS, carta e habilidades. Nesse caso, `.career-state/fit_map.json` pode ser usado como FIT_MAP ativo de compatibilidade.

No fluxo de `feras-pitch` para pitch oral, a entrega padrão inclui:
- `FERAS estruturado` (`F/E/R/A/S`) para inspeção lógica;
- `Pitch fluido para fala/leitura` em parágrafos naturais;
- `Keywords incorporadas naturalmente`;
- `Keywords relevantes não usadas`, com justificativa breve.

---

## 4. Retomar uma candidatura

No fluxo novo, a retomada e feita pelos arquivos persistidos da candidatura em `.career-state/applications_v2/<ID>/`.

Arquivos principais para retomada:

```text
.career-state/applications_v2/236/state.json
.career-state/applications_v2/236/fit_map.json
.career-state/applications_v2/236/job_description.md
.career-state/applications_v2/236/cv_content.json
.career-state/applications_v2/236/feras_formal.md
.career-state/applications_v2/236/habilidades_gupy.md
.career-state/applications_v2/236/habilidades_mercado_livre.md
.career-state/applications_v2/236/conversation_context.md
```

---

## 5. Atualizar arquivos de referência

Todos os arquivos de referência ficam em `.opencode/skills/career-system/references/`. Qualquer motor pode ler e atualizar.

### 5.1 Tabela de referências e quando atualizar

| Arquivo | Conteúdo | Atualizar quando |
|---|---|---|
| `autoconhecimento.md` | Histórico completo de carreira (1998–2026) | Nova experiência, novo número validado, nova ferramenta usada |
| `perfil_restricoes.md` | Números críticos, restrições, narrativas protegidas | Novo número validado, nova restrição definida |
| `palavras_chave_carreira.md` | Índice de competências por tema, empresa e resultado | Nova história, novo resultado mensurável |
| `dicionario_palavras_chave_mercado.md` | Vocabulário da vaga → base de conhecimento | Nova keyword validada ou proibida identificada |
| `diretrizes_carta_de_apresentacao.md` | Modelo e regras de carta | Mudança de estilo ou estrutura da carta |
| `habilidades_gupy.json` | 30 habilidades oficiais da plataforma Gupy | Gupy adicionar ou remover habilidades da lista |
| `.opencode/skills/habilidades-chave/references/habilidades_mercado_livre.json` | Catálogo derivado da imagem de habilidades do usuário | Ajustar catálogo de habilidades externas, como Mercado Livre |
| `competencias_matrix.json` | 53 competências × 16 experiências | Nova competência mapeada, nova evidência |
| `competencias_por_experiencia.json` | Top competências por experiência | Repriorização após nova vaga analisada |
| `competencias_linkedin.json` | 85 habilidades LinkedIn com status ativo/inativo | Mudança no perfil LinkedIn |

---

### 5.2 Como pedir a atualização

**Adicionar nova experiência ou resultado:**

```
Adiciona em autoconhecimento.md a experiência: [descrever]
Valida e adiciona o número [valor] em perfil_restricoes.md sob [empresa/tema]
```

**Adicionar keyword ao dicionário:**

```
Adiciona "[keyword]" como válida em dicionario_palavras_chave_mercado.md — sinônimo de [competência]
Marca "[keyword]" como proibida em dicionario_palavras_chave_mercado.md — razão: [motivo]
```

**Atualizar habilidades Gupy:**

```
Atualiza habilidades_gupy.json — adiciona "[nova habilidade]" à lista
Atualiza habilidades_gupy.json — remove "[habilidade]" que não existe mais na plataforma
```

**Atualizar matriz de competências:**

```
Atualiza competencias_matrix.json — adiciona evidência "[empresa] - [cargo]" para a competência "[nome]"
```

**Marcar habilidade LinkedIn como inativa:**

```
Atualiza competencias_linkedin.json — marca "[habilidade]" como ativo: false
```

---

### 5.3 Protocolo de atualização — o que o motor faz

Quando você pede uma atualização de referência, qualquer motor executa na mesma ordem:

1. Lê o arquivo atual (`Read`)
2. Aplica a alteração (`Edit` ou `Write`)
3. Confirma o resultado relendo o trecho alterado
4. Sinaliza se a mudança exige atualização em outro arquivo (ex: novo número em `autoconhecimento.md` pode exigir atualização em `perfil_restricoes.md`)

Não é necessário dizer "edita o JSON" — basta descrever o que deve mudar. O motor identifica o arquivo e o campo corretos.

---

## 6. Atualizar discovery do OpenCode

As skills ficam localmente em `.opencode/skills/{skill}/SKILL.md`.

**Regra pratica:** edite sempre `.opencode/skills/`.
Nao crie pasta paralela de skills.

---

## 7. Integração com Notion

**Canal único autorizado:** toda interação com o Notion é feita exclusivamente via `scripts/notion_sync.py` e `scripts/notion_query.py`. Ferramentas MCP de Notion (`notion-fetch`, `notion-search`, `notion-update-page`, `notion-create-pages` etc.) são **proibidas** neste projeto, mesmo quando estiverem tecnicamente acessíveis.

Motivo: o projeto precisa manter um unico caminho operacional para rastreabilidade, consistencia e reproducao de comportamento.

A skill operacional de Notion é `.opencode/skills/notion-transactions/SKILL.md`. Ela organiza leitura, criação, atualização, dry-run e validação. A implementação permanece nos scripts locais `scripts/notion_sync.py` e `scripts/notion_query.py`, chamados via shell local do macOS.

Não procurar skills inexistentes como `notion-query`, `notion-cli-fallback`, `notion-create-description` ou similares. Também não ler `.env`, não imprimir `NOTION_TOKEN`, não montar `curl` manual e não chamar a API pública do Notion diretamente.

**Variáveis de ambiente necessárias (já configuradas em `.env`):**
- `NOTION_TOKEN`
- `NOTION_APPLICATIONS_DATABASE_ID` (banco de candidaturas)
- `NOTION_APPLICATIONS_DATA_SOURCE_ID` (data source do banco, quando configurado)
- `NOTION_APPLICATIONS_TEMPLATE_ID` (template de página)
- `NOTION_APPLICATIONS_TEMPLATE_TIMEZONE`

### Operações disponíveis

**Listar candidaturas no Notion:**

```
"Lista as candidaturas no Notion"
```

O motor executa:
```bash
npm run notion:list
```

**Sincronizar o snapshot local de candidaturas do Notion:**

```bash
npm run notion:sweep:sync
```

Esse comando compara o banco do Notion com `inbox/notion/applications_sweep/`, baixa as candidaturas faltantes e reescreve:
- `inbox/notion/applications_sweep_summary.json`
- `inbox/notion/applications_cache.json`

Regra recomendada do projeto: quando a consulta depender do historico de candidaturas do Notion, prefira sempre `npm run notion:sweep:refresh`, porque pode haver edicoes feitas diretamente no Notion sem passar por este repositorio.

**Atualizar do Notion e reescrever o cache consolidado:**

```bash
npm run notion:sweep:refresh
```

Esse e o comando padrao para preparar a base local antes de usar o historico do Notion em analises, retrieval ou comparacoes.

**Reconstruir o banco local sem chamar o Notion:**

```bash
npm run notion:sweep:build-cache
```

Esse comando usa apenas os arquivos ja salvos em `inbox/notion/applications_sweep/` e e util quando voce alterou o sweep local ou so quer reindexar. Ele nao e o caminho padrao para consumo do historico, porque nao captura mudancas feitas diretamente no Notion.

**Inspecionar o estado do workflow:**

```bash
python scripts/career_cli.py workflow show-state
```

O estado e persistido em `.career-state/workflow_state.json` e registra quais etapas estruturadas ja foram concluidas.

**Ler página de uma candidatura:**

```
"Mostra a candidatura [nome da empresa] no Notion"
```

```bash
python scripts/notion_sync.py read-page [ID] --save
```

**Transformar uma página do Notion em entrada formal da análise:**

```bash
npm run notion:prepare-page -- <page_id>
```

Esse comando salva o payload bruto em `inbox/notion/` e exporta a descrição da vaga para `inbox/job_descriptions/`, pronta para iniciar o pipeline de `career-fit-analysis`.

Quando você quiser referenciar a vaga pelo campo único `ID` da tabela, use:

```bash
npm run intake:notion-record -- 218
```

Para leitura simples sem análise, `npm run notion:prepare-record -- 218` continua disponível. Para avaliar/analisar, sempre usar `intake:notion-record`, porque ele também registra `active_intake`, recria `.career-state/fit_map.draft.json` e devolve `next_required_step`.

### 7.1 Intake de vagas

Toda análise de vaga começa por um comando `intake:*`.

```bash
npm run agent:evaluate-notion -- <id_unico>
npm run agent:guard
npm run intake:notion-record -- <id_unico>
npm run intake:paste -- --company "<empresa>" --role "<cargo>" --text-file <arquivo>
cat <arquivo> | npm run intake:paste -- --company "<empresa>" --role "<cargo>" --stdin
npm run intake:linkedin-job -- --url "<url-da-vaga>"
npm run intake:linkedin-post -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
npm run intake:url -- --url "<url>" --company "<empresa>" --role "<cargo>"
npm run intake:resume
```

O intake produz um JSON com:
- `job_description_path`
- `active_intake` em `.career-state/workflow_state.json`
- `draft_path`
- `next_required_step`
- `delivery_plan` para CV, FERAS, carta, habilidades e update no Notion

Se `next_required_step` for `fill_fit_map_draft`, o agente deve preencher `.career-state/fit_map.draft.json` antes de qualquer análise textual.

Para agentes locais, prefira `agent:evaluate-notion` no caso de Notion ID e rode `agent:guard` quando houver interrupção, output truncado ou tentativa de fallback. Se `agent:guard` liberar `fill_fit_map_draft`, nenhuma ação de Notion, navegador, `.env`, `curl` ou script temporário está autorizada.

**Criar página a partir do FIT_MAP ativo:**

```
"Exporta essa candidatura para o Notion"
```

```bash
python scripts/notion_sync.py create-from-fit-map --fit-map .career-state/fit_map.json
```

**Quando a vaga já nasceu no Notion, atualizar a mesma página com a análise ativa:**

```bash
npm run notion:update-page-current -- <page_id> --dry-run
npm run notion:update-page-current -- <page_id> --job-description inbox/job_descriptions/<arquivo>.md
```

O update preenche as propriedades compatíveis da base e acrescenta no corpo da página o resumo da nota, os reposicionamentos defensáveis, os gaps abertos e as objeções do recrutador com mitigação.
Se a referência operacional for o `ID` único da tabela, use:

```bash
npm run notion:update-record-current -- 218 --dry-run
npm run notion:update-record-current -- 218 --job-description inbox/job_descriptions/notion_record_218.md
```

Também é suportado o caso em que você cola a vaga no chat, faz a análise local, abre manualmente um template no Notion e depois pede para atualizar o `ID` criado. Nesse caso, rode:

```bash
npm run notion:update-record-current -- 218 --dry-run
```

Se o registro ainda tiver apenas texto de template em `Descrição da Vaga`, o script procura automaticamente a descrição salva em `inbox/job_descriptions/` que combina com o FIT_MAP ativo. No preview, confira `job_description_source`:
- `saved_job_description`: usou a vaga salva localmente
- `notion_page.description`: usou o texto já existente no Notion

Não use `--allow-mismatch` para resolver template vazio. Se não houver descrição local compatível, salve a vaga primeiro ou use `--job-description <arquivo>`.

Quando houver um bloco de primeiro nível chamado `Pesquisa Inicial`, os blocos analíticos são inseridos imediatamente abaixo dele.
Se o texto a devolver ao Notion contiver sinais de encoding quebrado como `Ã`, `Â`, `â€“`, `â€”`, `â€™`, `â€œ`, `â€` ou `ï¿½`, o script recusa a escrita. Corrija o arquivo de origem em UTF-8 e execute novamente.

Cria a página usando o template definido em `NOTION_APPLICATIONS_TEMPLATE_ID`. O FIT_MAP em `.career-state/fit_map.json` é a fonte dos dados.
Na criação, o script também acrescenta no corpo da página a análise de aderência do FIT_MAP: nota, dor central, resumo das notas, gaps, objeções e defesas. Se houver bloco `Pesquisa Inicial`, a análise entra logo abaixo dele.
Se o `FIT_MAP` ativo não combinar com o cargo/título da descrição da vaga informada, o script bloqueia a criação para evitar registros mistos.
Divergência de empresa vira alerta, não bloqueio.
Quando houver mismatch, o fluxo correto é: refazer `career-fit-analysis` para a vaga alvo, depois `build`, `score`, `validate` e só então criar a página no Notion.

---

## 8. Validar o estado do projeto

### Gate de CV

Use o comando composto para registrar keywords no artefato final e revisar em uma única etapa:

```bash
npm run cv:approve -- --artifact outputs/<cv>.docx
```

O gate retorna `approved_for_delivery=true/false`. A decisão segue blockers e warnings:
- blockers impedem entrega
- warnings devem ser reportados, mas não bloqueiam entrega sozinhos
- ATS top 8: `covered_exact=1,0`, `covered_similar=0,8`, `declared_gap=0`, `missing_unexplained=0`
- mínimo aprovável: score >= 5,2/8 e zero `missing_unexplained`
- ótimo: score >= 6,2/8
- `pt_cv_keyword_shotgun_control` é warning, não blocker isolado

Nunca limpar `outputs/_tmp/output_review_report.json` quando o relatório estiver reprovado.

Para verificar a estrutura geral do projeto:

```bash
npm run validate:structure
```

Para verificar uma candidatura especifica:

```bash
python scripts/validate_fit_map.py .career-state/applications_v2/<ID>/fit_map.json
```

Para fluxos legados/manuais que ainda usam o espelho global:

```bash
python scripts/validate_fit_map.py .career-state/fit_map.json
```

## 8.1 Canonizar o FIT_MAP antes de validar em fluxo manual

Quando a análise for feita manualmente fora do orquestrador de candidaturas, prefira salvar primeiro um draft intermediário e só depois gravar o estado final:

```bash
npm run fit-map:template
npm run fit-map:guard
npm run fit-map:status
npm run fit-map:check:extract
npm run fit-map:check:map-evidence
npm run fit-map:check:score-draft
npm run fit-map:check:complete-draft
npm run validate:fit-map:draft
# preencher .career-state/fit_map.draft.json com a análise estruturada
npm run fit-map:build
npm run fit-map:score
npm run validate:fit-map
```

Quando o draft já estiver preenchido e você quiser executar o fechamento inteiro em um passo:

```bash
npm run fit-map:finalize
```

Para diagnosticar retomada, draft com placeholders ou FIT_MAP possivelmente antigo:

```bash
npm run fit-map:status
npm run fit-map:resume
npm run fit-map:guard
```

Se `fit-map:status` indicar `next_required_step = preencher .career-state/fit_map.draft.json`, o agente deve executar `npm run fit-map:resume` e em seguida preencher o draft. Se `fit-map:guard` retornar `guard=blocked`, a próxima ação obrigatória é `required_next_command`; qualquer resposta sem edição do draft conta como execução parcial/stall no benchmark.

No heartbeat, esse fechamento é feito dentro da pasta da candidatura (`.career-state/applications_v2/<ID>/`) e o orquestrador usa essa pasta como fonte primaria do estado.

Para inspecionar custo operacional e regenerar a memória compacta do runtime:

```bash
npm run runtime:diagnose
npm run memory:build
```

Se a vaga vier de texto colado e você quiser preservar a descrição para uso posterior no Notion:

```bash
python scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo_texto_vaga>
```

Regra operacional:
- nao tentar abrir arquivo bruto presumido por nome, como `*_raw.txt`
- o bruto persistido valido e apenas o que foi salvo pelo `save_job_description.py`
- se o usuario colou uma nova vaga, nao trate `.career-state/fit_map.json` como resposta pronta antes de salvar novamente a descricao da vaga nessa execucao

Depois que o FIT_MAP estiver canonizado e validado, voce pode rerrodar o script para fechar a associacao final com o estado ativo:

```bash
python scripts/save_job_description.py --fit-map .career-state/fit_map.json --text-file <arquivo_texto_vaga>
```

### Limpar temporários de DOCX

Se o runtime deixar residuos em `outputs/_tmp/`, a limpeza pode ser feita normalmente:

```bash
npm run docx:tmp:clean
```

Para limpar apenas arquivos temporários mais antigos:

```bash
npm run docx:tmp:clean:stale
```

## 8.2 Checklist anti-loop para modelos locais

Ao testar modelos locais, considere a sessao saudavel apenas se estes sinais aparecerem:

- apos carregar a skill, a proxima resposta executa uma acao concreta
- nao ha mais de 1 resposta consecutiva apenas repetindo o workflow
- ha leitura de referencia ou persistencia da vaga em ate 2 respostas
- `continue` retoma o ultimo passo nao executado, sem resetar a analise
- depois de salvar a vaga e ler as referencias obrigatorias, o agente vai direto para `npm run fit-map:template`
- antes de preencher `.career-state/fit_map.draft.json`, o agente nao escreve subtotais nem nota final na conversa; classifica os itens diretamente no draft
- se `npm run fit-map:guard` retornar `blocked=true`, qualquer resposta subsequente sem editar `.career-state/fit_map.draft.json` reprova o modelo neste fluxo
- logs suspeitos sao avaliados com `python scripts/diagnose_session_stall.py <session.md>`; `stalled=true` significa execucao parcial
=== JSONs em references/ ===
  competencias_matrix.json       experiences=16
  competencias_por_experiencia.json  experiencias=16
  competencias_linkedin.json     habilidades=85
  habilidades_gupy.json          total=30

=== Arquivos de entrada ===
  OK  AGENTS.md
  OK  opencode.json

=== Referências antigas em .opencode/skills/*.md (SKILL.md apenas) ===
  Nenhuma referência antiga encontrada.
```

---

## 9. Regras que nunca mudam

Estas regras valem para qualquer modelo ou runtime. Nenhum deles pode viola-las:

- Nunca inventar dados, números, experiências ou certificações
- Nunca afirmar responsabilidade total por P&L — usar alavanca operacional real
- Inglês: sempre "Avançado" — nunca "Fluente"
- Espanhol: nunca incluir como competência
- VivaReal CS: sempre "arquiteto da área" — nunca "gestor de CS"
- Fill rate: pertence à Trifil — nunca atribuir à VivaReal
- wehandle: sempre em minúsculas nos documentos finais
- Movimento iFood → wehandle: apresentar pelos fatos (escopo, time, resultado) — nunca por justificativa motivacional
- BSP em português: "MBA Corporate Strategy — BSP Business School São Paulo"
- BSP em inglês: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo"
- Tom: factual, direto, primeira pessoa real — sem linguagem de coach, frases de efeito ou formulário de RH
- Em respostas curtas de formulário/entrevista, responder direto, mitigar com fatos e evitar frases abertas como “minha abordagem é setor-agnóstica”, “aprendo rápido” ou “eu faria o mesmo”.
- `output-reviewer` roda obrigatoriamente após toda skill de produção, antes de entregar qualquer documento
- Datas de experiência: sempre lidas de `autoconhecimento.md` — nunca de memória ou sessão anterior
- Notion: usar a skill `.opencode/skills/notion-transactions/SKILL.md`; toda execução real continua exclusivamente via `scripts/notion_sync.py`, `scripts/notion_query.py` e comandos `npm run notion:*` — nunca via MCP, `curl` manual ou cliente direto de API

---

## 10. Números críticos — referência rápida

| Empresa | Métrica | Valor |
|---|---|---|
| wehandle | Margem bruta | 15% |
| wehandle | Custo por atendimento | R$ 4,14 → R$ 3,61 (−13%) |
| iFood | Saving simulador | R$ 70MM/ano |
| iFood | Budget OPEX logístico | R$ 300MM/ano |
| iFood | Cobertura geográfica | 400 → 800 cidades |
| VivaReal | Conversão SDR inbound | 18% → 50% |
| VivaReal | Área de CS | 91 pessoas |
| Trifil | Redução de GGF | R$ 8MM |

Fonte: `.opencode/skills/career-system/references/perfil_restricoes.md` — sempre consultar antes de gerar qualquer documento.

## 11. Ponto de entrada oficial

O caminho oficial do projeto começa em `AGENTS.md`.
