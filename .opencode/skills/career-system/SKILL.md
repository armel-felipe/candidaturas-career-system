---
name: career-system
description: >
  Orquestra o sistema local de carreira executiva de Felipe Armel no OpenCode/VS Code. Use sempre que o usuário pedir
  análise de vaga, CV, currículo, FERAS, pitch, carta de apresentação, Gupy, habilidades, resumo ATS, mensagem de
  networking, extração de vaga do LinkedIn, revisão de documentos, comparação de competências, pesquisa de cargos
  aderentes ou migração/manutenção deste projeto de carreira. Esta skill define a memória, os gatilhos, o FIT_MAP local,
  as regras globais, validações obrigatórias e a equivalência local das skills operacionais do projeto.
---

# Career System

## Governança da Skill

Manutenção canônica desta skill: `.opencode/skills/career-system/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.opencode/skills/career-system/SKILL.md`.

Use esta skill como camada orquestradora antes de qualquer rotina de candidatura. Ela define o fluxo operacional local do projeto no OpenCode.

## Runtime Local

- Workspace raiz: resolver pelo diretório atual do projeto.
- Memória compartilhada: `.opencode/skills/career-system/references/`.
- Estado ativo: `.career-state/fit_map.json`.
- Saídas finais: `outputs/`.
- Scripts locais: `scripts/`.
- Registro de keywords ATS: `.opencode/skills/career-system/references/keyword_ats_registry.json`.
- Dicionário canônico de equivalentes PT-BR para keywords ATS: `.opencode/skills/career-system/references/keyword_translation_registry.json`.
- Memória gerada a partir do histórico de candidaturas para priorizar traduções PT-BR: `.opencode/skills/career-system/references/keyword_translation_candidates.json`.
- Integração Notion: `scripts/notion_sync.py`.
- Caminhos do runtime devem ser resolvidos a partir da raiz local do workspace.

## Skills Disponíveis

Antes de executar uma tarefa que aciona uma skill, leia o `SKILL.md` correspondente na pasta `.opencode/skills/`.

Ler a skill é pré-requisito, não conclusão. A execução só conta como concluída quando o workflow operacional definido pela skill tiver sido realmente cumprido, com artefatos persistidos e validações executadas.

Fluxo padrão:

1. `career-fit-analysis` gera um draft analítico, canoniza via `scripts/build_fit_map.py`, calcula a nota via `scripts/score_fit_map.py` e então atualiza `.career-state/fit_map.json`.
2. `cv-generator`, `feras-pitch`, `cover-letter` e `habilidades-chave` consomem o FIT_MAP ativo.
3. `output-reviewer` roda obrigatoriamente após toda skill de produção antes de entregar.
4. `networking-message` sempre pergunta o perfil do destinatário antes de gerar mensagem.
5. `linkedin-job-extractor` salva a descrição completa de vagas ou postagens de vaga do LinkedIn antes de acionar análise, CV ou Notion.

Regra de roteamento para URLs do LinkedIn:

- pedidos como `avalie a vaga em <URL>`, `analise a vaga em <URL>`, `gera CV para <URL>` ou equivalentes devem detectar URLs `linkedin.com/jobs/view/`, `linkedin.com/jobs/`, `linkedin.com/job/`, `linkedin.com/feed/update/`, `linkedin.com/posts/` e `linkedin.com/pulse/`
- se a URL for de vaga ou postagem de vaga do LinkedIn, executar `linkedin-job-extractor` antes de qualquer análise, FIT_MAP, CV, carta, FERAS, habilidades ou Notion
- nunca usar `browser_navigate`, navegador genérico do agente, `web_search` ou busca web para abrir/analisar LinkedIn; usar apenas `npm run linkedin:extract:authenticated -- --url "<url>"` para vagas ou `npm run linkedin:post:extract:authenticated -- --url "<url>" --company "<empresa>" --role "<cargo>"` para postagens
- se o comando autenticado falhar por sessão expirada, bloquear e autenticar com `npm run linkedin:auth` conforme `LINKEDIN_AUTH_RUNBOOK.md`; não cair para navegador/web search
- após extração e persistência da descrição, continuar com a skill final pedida; para avaliação/análise de vaga, continuar com `career-fit-analysis`
- não analisar a URL do LinkedIn diretamente e não reutilizar FIT_MAP antigo para a nova URL

Regra de roteamento para vagas salvas do LinkedIn/Rastreador de vagas:

- pedidos para listar vagas salvas, consultar "minhas vagas", abrir saved jobs, usar o Rastreador de vagas ou escolher uma vaga salva para análise devem acionar `linkedin-saved-jobs`
- `linkedin-saved-jobs` é apenas um seletor de URL: lista título, empresa, localização e URL canônica da vaga salva
- para listar, executar `npm run linkedin:saved-jobs:extract`, que abre `https://www.linkedin.com/jobs-tracker/`, usa a sessão Playwright persistida, lê a aba `Salvas` e grava `inbox/linkedin_saved_jobs.json`
- não ler `inbox/linkedin_saved_jobs.json` antigo como substituto da extração, salvo pedido explícito para consultar a última extração salva
- depois que o usuário escolher uma vaga da lista, usar `npm run intake:linkedin-job -- --url "<url-da-vaga-escolhida>"` e seguir `next_required_step`
- não usar `npm run linkedin:extract:authenticated` como caminho final quando o objetivo for análise/FIT_MAP de vaga escolhida no Rastreador de vagas; usar o wrapper de intake

Preferências operacionais para reduzir custo de execução sem relaxar os gates:

- toda vaga específica deve entrar por `intake:*` antes da análise: `intake:notion-record`, `intake:paste`, `intake:linkedin-job`, `intake:linkedin-post` ou `intake:url`
- para `Avalie vaga Notion <número>`, prefira `npm run agent:evaluate-notion -- <número>`, que roda intake, guard de conduta, mapa local e request compacto `fit-map`
- `npm run agent:evaluate-notion-local -- <número>` existe como alias explícito do modo local/menor, mas o comando padrão já é local-safe
- use `npm run agent:guard` após interrupção, output truncado ou dúvida sobre a próxima ação autorizada
- use `npm run intake:resume` para retomar e seguir `next_required_step`, em vez de procurar arquivos por nome, rodar `grep`, listar Notion ou reabrir URL por conta própria
- quando o intake retornar `next_required_step = fill_fit_map_draft`, a próxima ação é preencher `.career-state/fit_map.draft.json`; não entregar análise textual nem reaproveitar FIT_MAP antigo
- preencher `.career-state/fit_map.draft.json` significa o agente editar o arquivo persistido; é proibido responder com instruções para o usuário preencher o template, imprimir o JSON bruto do template ou tratar placeholders como entrega
- em modo multiagente/local pequeno, depois do intake gerar/ler o request compacto com `npm run multiagent:request -- fit-map` e seguir as `Operational Rules`
- após qualquer edição de `.career-state/fit_map.draft.json`, executar `npm run validate:fit-map:draft`; se falhar, corrigir e reexecutar antes de responder ao usuário
- se `.career-state/fit_map.draft.json` ficar com JSON inválido, executar `npm run fit-map:template` para resetar o template da vaga ativa antes de continuar
- quando o draft analítico já estiver preenchido, prefira `npm run fit-map:finalize`
- use `npm run fit-map:summary`, `npm run fit-map:draft-summary`, `npm run workflow:summary` e `npm run registry:summary` para inspeções compactas antes de abrir qualquer JSON grande
- use `npm run validate:fit-map:quality` depois de `fit-map:finalize` em execuções com modelo local para detectar degradação textual/semântica
- para diagnosticar travamento ou estado misto entre vaga, draft e FIT_MAP, rode `npm run fit-map:status`
- se `fit-map:status` apontar template com placeholders ou FIT_MAP antigo, rode `npm run fit-map:resume` e execute a ação indicada sem reexplicar o workflow
- depois de `npm run fit-map:template` e em qualquer retomada, rode `npm run fit-map:guard`; se retornar `guard=blocked`, a próxima ação deve ser exatamente `required_next_command`, sem análise textual intermediária
- para forcar persistencia incremental em modelos instaveis, use `npm run fit-map:check:extract`, `npm run fit-map:check:map-evidence`, `npm run fit-map:check:score-draft` e `npm run fit-map:check:complete-draft`
- para gate local/diagnóstico do CV, use `npm run cv:approve -- --artifact outputs/<cv>.docx`
- quando o agente gerar um CV final e a entrega OneDrive/rclone estiver configurada, o encerramento correto é `npm run cv:deliver -- --artifact outputs/<cv>.docx`
- use `npm run memory:build` para regenerar a memória compacta do runtime antes de trabalhos de manutenção ou quando referências canônicas forem atualizadas
- use `npm run runtime:diagnose` para investigar estado inchado, caches e sinais de custo operacional

Política de contexto compacto:

- trabalhar por ponteiros: artefatos grandes ficam em arquivos; a conversa recebe apenas resumo curto, paths, contagens e status
- nunca imprimir FIT_MAP, draft, registry ATS, cache Notion, descrição longa, payload de validação completo ou diff gigante
- para JSON, usar projeções pequenas (`jq`/campos específicos) ou comandos compactos do projeto; não usar `cat` em `.career-state/fit_map*.json`, `applications_cache.json`, registries ou referências longas
- validações devem retornar apenas `passed/failed`, contagens, score/path e erros objetivos; payload completo só com flag explícita de manutenção
- para link ou página Notion por ID único, usar `npm run notion:link-record -- <id_unico>` ou comandos canônicos por ID; não varrer cache/sweep com `grep -r`
- para diagnóstico de prontidão local strict, usar `npm run local:strict:doctor`
- para dry-run de atualização Notion por modelo local, preferir `npm run notion:update-record-current:compact -- <id_unico> --dry-run`
- para benchmark rápido do estado local strict, usar `npm run benchmark:local-agent`
- se um comando gerar output grande ou truncado, descartar como evidência conversacional e repetir com projeção compacta

Gate global para CV em DOCX:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv outputs/<cv>.docx
python scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/fit_map.json --registry .opencode/skills/career-system/references/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
```

Regras:
- os dois comandos acima devem rodar sobre o artefato final em `outputs/`
- o idioma do CV segue o idioma da descrição da vaga: descrição em inglês gera CV em inglês; descrição em português gera CV em português
- CV de vaga em inglês usa sufixo obrigatório `_en` antes da extensão e texto visível em inglês
- CV de vaga em português não usa sufixo `_en` e texto visível em português
- `review_output.py` só pode rodar depois de `register_keywords.py --cv`
- se `review_output.py` não rodar, falhar, ou retornar `approved_for_delivery=false`, o CV não pode ser considerado aprovado nem entregue
- o gate do CV decide por blockers e warnings: blockers impedem entrega; warnings não impedem entrega sozinhos
- política ATS top 8: `covered_exact=1,0`, `covered_similar=0,8`, `declared_gap=0`, `missing_unexplained=0`; aprovação mínima exige score >= 5,2/8 e zero `missing_unexplained`; ótimo exige >= 6,2/8
- `pt_cv_keyword_shotgun_control` é blocker em CV PT-BR quando o gate detectar cluster artificial de keywords em inglês; naturalidade humana prevalece sobre matching literal
- todo CV PT-BR passa por polimento textual obrigatório no `output-reviewer`, mesmo quando o gate objetivo aprovar de primeira; se o polimento alterar texto, regenerar DOCX, rerodar `register_keywords.py --cv` e rerodar `review_output.py`
- o modo padrão de CV é conciso: exatamente 3 bullets por experiência; modo expandido/bullet points só com pedido explícito do usuário
- se o agente inferir que modo expandido pode ser mais inteligente por vaga multiarea, formulário, indicação, reposicionamento, CV mestre ou maximização ATS, deve validar com o usuário antes de gerar; sem confirmação explícita, manter conciso
- todo CV orientado por vaga deve trazer entre 4 e 8 experiências por padrão; reduzir abaixo de 4 só com pedido explícito do usuário
- nunca juntar experiências, cargos, promoções, fases ou escopos em uma única entrada de CV; se houver limite de espaço, selecionar experiências separadas por aderência
- as 8 keywords-habilidade ATS prioritárias devem ser distribuídas em experiências defensáveis do CV; ausência sem explicação vira blocker e deve gerar pedido de reparo objetivo

## Contrato de Execução

Quando uma skill for acionada, o agente deve seguir o fluxo completo descrito nela. Resposta textual sem execução operacional não conta como uso correto da skill.

Critério geral de conclusão:

- referências obrigatórias lidas na ordem definida
- scripts mandatórios executados quando previstos
- arquivos de estado e artefatos persistidos nos caminhos corretos
- validações finais executadas com sucesso
- resposta final consistente com o estado salvo
- bloco visível de validação operacional preenchido com status real de execução quando a skill exigir esse output

Se qualquer passo obrigatório falhar ou não puder ser executado, o agente deve:

- interromper a narrativa de conclusão
- relatar o bloqueio de forma objetiva
- identificar o artefato ou script faltante
- evitar dizer que a skill foi concluída

Comportamentos proibidos:

- usar a skill apenas como guia conceitual sem executar seus passos operacionais
- declarar que construiu FIT_MAP sem atualizar `.career-state/fit_map.json`
- declarar que calculou nota final quando o cálculo exigido pela skill não foi produzido
- prosseguir para skills dependentes usando estado antigo, incompleto ou não validado
- marcar script, validação ou arquivo como concluído sem evidência real de execução
- aprovar CV em DOCX sem executar o gate objetivo `scripts/review_output.py` sobre o artefato final em `outputs/`
- tratar inspeção do script gerador como substituto da revisão do DOCX final
- limpar `outputs/_tmp/` antes de `register_keywords.py --cv` e `review_output.py` terem concluído com sucesso no arquivo final

## Politica Global Anti-Stall

- depois de ler `AGENTS.md`, `career-system` e a skill-alvo, a proxima resposta deve conter ou um comando executado ou uma pergunta bloqueadora objetiva
- duas respostas consecutivas sem mudar o estado do trabalho contam como risco de loop; o agente deve parar de expandir raciocinio e executar o proximo passo concreto
- analise longa so e aceitavel quando ela produzir imediatamente um artefato persistido no passo seguinte
- se o agente estiver recalculando nota, reexplicando workflow ou reenumerando passos ja completos, ele deve encerrar esse bloco e voltar ao pipeline operacional
- mensagens como `continue`, `ta rodando?`, `travou?` e equivalentes exigem resposta curta com `ultimo passo concluido`, `passo atual` e `proximo comando`
- para CV, se o formato de saída já estiver explícito no pedido, não perguntar de novo: executar o pipeline correspondente no mesmo turno
- antes de `.career-state/fit_map.draft.json` estar preenchido, nao escrever subtotais nem nota final na conversa; classificar os itens diretamente no draft
- se houver duvida sobre o estado atual, executar `npm run fit-map:status` e seguir `next_required_step`
- se `next_required_step` for `preencher .career-state/fit_map.draft.json`, executar `npm run fit-map:resume`; a resposta seguinte deve editar o draft ou declarar bloqueio real, nunca recalcular nota em texto livre
- se o agente acabou de ler `.career-state/fit_map.draft.json` e ele ainda contém placeholders, a leitura não conta como progresso; deve editar o arquivo imediatamente
- se `npm run fit-map:guard` retornar `blocked=true`, qualquer resposta subsequente sem edição do draft conta como execução parcial/stall
- ao avaliar logs de benchmarking ou travamento, executar `python scripts/diagnose_session_stall.py <session.md>` e tratar `stalled=true` como execucao parcial

## Execucao Multiagente Local

Para reduzir contexto em modelos locais, o projeto possui um maestro deterministico e agentes especialistas. O maestro
nao substitui os gates; ele gera requests compactos e bloqueia improvisos.

Comandos:

```bash
npm run agent:maestro
npm run agent:maestro -- fit-map
npm run agent:maestro -- cv
npm run agent:maestro -- notion-update
npm run agent:maestro -- email-draft
npm run agent:maestro -- linkedin
npm run agent:evaluate-notion-local -- <id_unico>
npm run multiagent:runbook
npm run multiagent:local-model-map
npm run multiagent:request -- fit-map
npm run validate:workspace-clean
```

Artefatos:
- runbook: `.career-state/agent_requests/multiagent_runbook.json`
- mapa para modelo local: `.career-state/agent_requests/local_model_map.json/md`
- requests compactos: `.career-state/agent_requests/{fit-map,cv,notion-update,email-draft,linkedin}_request.json`
- espelho legivel: `.career-state/agent_requests/*_request.md`

Regras:
- para modelos locais/menores, gerar e ler primeiro `.career-state/agent_requests/local_model_map.md` com `npm run multiagent:local-model-map`; esse mapa define gatilho, comando canonico, request seguinte e proibicoes
- o maestro e o unico ponto que decide a sequencia de etapas
- cada agente especialista deve ler primeiro seu request e operar somente nos arquivos e comandos permitidos
- se a validacao falhar, o agente nao improvisa scripts; devolve `blocked` ou recebe um repair request especifico
- cada request deve conter `Operational Rules` especificas da etapa; ignorar essas regras conta como execucao parcial/stall
- `fit-map-agent`: edita `.career-state/fit_map.draft.json` quando houver placeholders; nao delega o preenchimento ao usuario e nao imprime o template bruto como resposta
- `fit-map-agent`: se o request indicar `Current FIT_MAP.matches_active_job = false`, tratar `.career-state/fit_map.json` como antigo e nao reutilizar
- `fit-map-agent`: depois de editar, deve rodar `npm run validate:fit-map:draft`; se o JSON quebrar ou a validação falhar, deve corrigir antes de responder
- `cv-agent`: produz DOCX em `outputs/`, roda `validate:docx` e encerra com `cv:deliver` quando OneDrive/rclone estiver configurado; `cv:approve` isolado é gate local/diagnóstico
- `notion-agent`: prepara somente dry-run ate aprovacao explicita; usa scripts locais, bloqueia mismatch/mojibake e nunca le `.env` ou usa MCP/curl
- `email-agent`: revisa texto antes do preview, valida anexos, faz dry-run e so cria draft real apos aprovacao explicita; nunca envia email
- `linkedin-agent`: usa apenas scripts autenticados, persiste a descricao e confirma `active_intake`; se sessao expirar, usa `linkedin:auth`
- arquivos temporarios na raiz como `gen_*.py`, `generate_*fitmap*.py`, `create_draft.py`, `create_drafi.py` e `tmp_*.py` sao proibidos
- `validate:workspace-clean` deve passar antes de considerar uma execucao multiagente saudavel

## Memória Obrigatória

Antes de abrir referências longas, o runtime pode consultar a memória compacta em `.career-state/memory/` quando ela existir:

- `profile_facts.json`
- `application_rules.json`
- `ats_keyword_summary.json`
- `evidence_index.json`

Esses arquivos são derivados e não substituem as fontes canônicas. Quando houver decisão factual, dúvida, divergência ou necessidade de defesa detalhada, prevalece a leitura das referências originais abaixo.

Use as referências nesta ordem:

1. `dicionario_palavras_chave_mercado.md` para permitir, bloquear ou traduzir termos da vaga.
2. `palavras_chave_carreira.md` para localizar evidência e resultados por keyword.
3. `autoconhecimento.md` para validar datas, contexto, escopo, ferramentas e defensabilidade.
4. `perfil_restricoes.md` para validar números críticos, narrativas protegidas e restrições.
5. `.opencode/skills/habilidades-chave/references/habilidades_mercado_livre.json` para listas derivadas de catálogos externos. `habilidades_gupy.json` somente para Gupy — lista oficial de 30 habilidades selecionáveis. Nunca usar habilidade fora da fonte ativa do modo selecionado e nunca normalizar o texto de um catálogo para parecer o do outro.
6. `competencias_matrix.json` e `competencias_por_experiencia.json` para comparativos de competências e análises de fit por cargo quando solicitado. `competencias_linkedin.json` para gestão das habilidades do perfil LinkedIn.
7. `keyword_ats_registry.json` para aprender quais keywords foram extraídas, cobertas no CV, ficaram faltando e devem alimentar CVs/LinkedIn futuros.

Nenhum número, ferramenta, experiência, idioma, certificação ou escopo pode ser inventado.

## Regras Globais

- Nunca afirmar responsabilidade total por P&L; usar alavanca operacional real: OPEX, custo logístico, margem, eficiência ou receita incremental.
- Em toda análise de vaga, identificar 3 a 5 objeções do recrutador e mitigar com evidência real.
- Nunca usar espanhol como competência.
- Inglês sempre `avançado`, nunca `fluente`.
- VivaReal CS: sempre `arquiteto da área`, nunca `gestor de CS`.
- Fill rate pertence à Trifil, nunca à VivaReal.
- BSP em português: `MBA Corporate Strategy — BSP Business School São Paulo`.
- BSP em inglês: `Specialization Certificate in Corporate Strategies — BSP Business School São Paulo`.
- `wehandle` deve aparecer em minúsculas em documentos finais.
- Movimento iFood -> wehandle deve ser tratado com fatos, escopo e resultados; não com justificativa motivacional.
- Tom de documentos: factual, direto, primeira pessoa real; sem linguagem de coach, frases de efeito ou formulário de RH.

## FIT_MAP Local

O FIT_MAP ativo deve ser JSON válido em `.career-state/fit_map.json` com os campos mínimos:

```json
{
  "cargo": "",
  "empresa": "",
  "modo": "",
  "dor_central": "",
  "keywords_vaga": [],
  "competencias_vaga": [],
  "keywords_para_ats": [],
  "mapa_ajuste": [],
  "objecoes": [],
  "nota_aderencia": null,
  "gaps_sem_cobertura": [],
  "historias_selecionadas": {
    "principal": null,
    "secundaria": null,
    "terceira": null
  },
  "keywords_habilidade_ats": []
}
```

Use `scripts/build_fit_map.py` para canonizar drafts intermediários, `scripts/score_fit_map.py` para calcular a nota estruturada e `scripts/validate_fit_map.py` para validar o arquivo final quando houver dúvida.
O workflow estruturado registra a vaga ativa por fingerprint da descrição salva; pré-requisitos de FIT_MAP devem pertencer à mesma vaga ativa, não a uma análise anterior.

Regras duras de aderência:
- `fit_map.json` deve privilegiar defensabilidade em entrevista, não similaridade semântica
- `scripts/build_fit_map.py` e `scripts/validate_fit_map.py` devem falhar em drafts/FIT_MAPs com conteúdo-placeholder, shape parcial ou perda silenciosa de informação; falso positivo estrutural não é estado válido
- nota `1,0` em itens de aderência exige `tipo = DIRETO` e `prova_literal = true`
- cobertura por analogia, contexto semelhante ou reposicionamento recebe no máximo `0,5`
- itens sensíveis sem prova literal, especialmente `motoristas/ajudantes`, `combustível/pedágio/horas extras` e `distribuição de alimentos/perecíveis`, devem gerar gap explícito

## Registro de Keywords ATS

Depois de toda análise de vaga, registrar as keywords extraídas:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json
```

Depois de todo CV gerado, atualizar o mesmo registro com o DOCX final para marcar cobertura real por string exata:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv outputs/<cv_gerado>.docx
```

Use esse histórico para:
- priorizar nomenclaturas canônicas mais defensáveis;
- gerar CVs futuros já com os termos de mercado corretos;
- sinalizar keywords faltantes sem forçar experiência;
- montar o LinkedIn com 4 a 8 bullets semelhantes ao modelo de CV, usando apenas keywords cobertas e fatos validados.

## Integração Notion

**Canal único:** toda interação com o Notion neste projeto usa exclusivamente os scripts locais `scripts/notion_sync.py` e `scripts/notion_query.py`. Ferramentas MCP de Notion — como `notion-fetch`, `notion-search`, `notion-update-page`, `notion-create-pages`, `notion-create-comment`, `notion-move-pages` e similares — são **proibidas**, mesmo quando disponíveis no runtime em uso. Esta restrição existe para garantir paridade de comportamento e rastreabilidade operacional.

Notion tem skill operacional própria em `.opencode/skills/notion-transactions/SKILL.md`. Essa skill organiza o workflow; a implementação continua nos scripts locais. Não procurar skills `notion-query`, `notion-cli-fallback`, `notion-create-description`, `notion-update-record` ou nomes semelhantes. Para `Notion <número>`, executar `npm run notion:prepare-record -- <número>` ou `python3 scripts/notion_sync.py prepare-analysis-from-record <número>`.

Para avaliar/analisar vaga por `Notion <número>`, o comando preferencial é `npm run intake:notion-record -- <número>`.

Não ler `.env`, não extrair `NOTION_TOKEN`, não montar `curl` manual e não chamar endpoints do Notion diretamente. Os scripts locais resolvem token, database/data source, propriedades, paginação, templates e validação de payload.

Comandos mínimos:

```bash
npm run notion:list
npm run notion:prepare-record -- <id_unico>
python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>" --dry-run
python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run
npm run notion:update-record-current -- <id_unico> --dry-run
```

## Orquestrador Automático de Candidaturas

Comandos oficiais:

```bash
npm run applications:config
npm run applications:heartbeat -- --dry-run --max-per-run 1
npm run applications:heartbeat -- --max-per-run 3
npm run applications:agent-heartbeat -- --max-per-run 3
npm run applications:agent-heartbeat -- --max-per-run 3 --model openai/gpt-5.4 --variant medium
npm run applications:heartbeat:install-task -- --interval-minutes 60 --max-per-run 3 --run-agent
```

Regras:
- o heartbeat lê a fila a partir do cache/sweep do Notion e processa candidaturas sequencialmente;
- nunca executar candidaturas em paralelo enquanto houver escrita em `.career-state/applications/<ID>/`;
- `max_per_run` padrão é 3, configurado em `.career-state/applications_v2/config.json`;
- o status de tratamento automático é `Fila Agente`;
- o status final configurado é `Aplicação andamento`;
- vaga em fila sem campo `Descrição da Vaga` preenchido deve ser ignorada pelo agente e movida para `Sem descrição de vaga`;
- o orquestrador detecta o idioma da descrição e grava `required_cv_language` no manifest da candidatura;
- cada candidatura deve ter pasta própria em `.career-state/applications/<ID>/` com `manifest.json`, `state.json`, `job_description.md`, requests por etapa, `conversation_context.md` e relatórios;
- o estado canônico da candidatura fica em `.career-state/applications/<ID>/state.json`; `.career-state/fit_map.json` é apenas espelho de compatibilidade;
- `applications:agent-heartbeat` e os comandos manuais usam o mesmo pipeline por etapa: `prepare -> analyze -> generate -> repair -> finalize`;
- o modelo e variant ficam em `.career-state/applications_v2/config.json` e podem ser sobrescritos com `--model provider/model --variant medium`, mantendo o agente `build`;
- se faltar FIT_MAP ou artefato gerado por modelo e `--run-agent` não estiver ativo, gravar `pending_model_tasks.md` e não promover status para aplicação em andamento;
- baixa aderência (`nota < 6.0`) atualiza análise e memória, mas não gera CV;
- alta aderência (`nota >= 6.0`) só pode ser promovida após CV aprovado pelo reviewer objetivo e pelo polish gate;
- CV PT-BR precisa de `outputs/_tmp/output_review_report.json` e `outputs/_tmp/polish_review.json`;
- se `polish_review.json` tiver `approval_blockers`, o CV está bloqueado mesmo que o reviewer objetivo aprove.

Contrato de orquestração pesada e agente leve:
- `prepare` resolve fila, descrição, idioma, memória compacta, estado e request da etapa seguinte;
- `analyze` gera apenas `fit_map.draft.json`; a finalização do FIT_MAP é local;
- `generate` gera apenas `cv_content.json`, `feras_formal.md` e habilidades; DOCX, ATS e reviewers são locais;
- `repair` corrige apenas artefatos textuais bloqueados pelos gates locais, com foco primário em cobrir keywords top 8 ausentes em experiências defensáveis e preservar a faixa de 4 a 8 experiências;
- o agente não decide status do Notion, não renderiza DOCX e não promove a candidatura.

Contrato de leitura para agentes:
- ler primeiro `analysis_request.json/md`, `generation_request.json/md` ou `repair_request.json/md`;
- atualizar apenas os arquivos permitidos nessa etapa;
- não abrir referências longas por padrão; usar somente quando o request apontar conflito factual, lacuna de evidência ou dúvida de defensabilidade;
- qualquer request que mande “executar o pipeline completo” é inválido.

Há dois tipos de interação com o Notion:

1. **Leitura como insumo de análise** — permitido quando o usuário pedir para analisar vaga(s) já cadastrada(s), calcular aderência, coletar keywords, identificar cobertura e gaps. Usar:

```bash
python scripts/notion_sync.py list
python scripts/notion_sync.py read-page <page_id> --save
python scripts/notion_sync.py prepare-analysis-from-page <page_id>
python scripts/notion_sync.py prepare-analysis-from-record <id_unico>
```

2. **Criação de registro no tracker Aplicações** — só executar quando o usuário pedir explicitamente para criar/salvar/registrar a candidatura no Notion. Usar sempre o template cadastrado e preencher, no mínimo: `Vaga`, `avaliação de aderencia claude` e `Descrição da Vaga`. A criação também deve anexar ao corpo da página a análise de aderência produzida a partir do FIT_MAP, salvo quando `--no-append-summary` for pedido deliberadamente.

```bash
python scripts/notion_sync.py create-from-fit-map --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga>
```

O template não é opcional. Para listar ou trocar o template:

```bash
python scripts/notion_sync.py templates
python scripts/notion_sync.py create-from-fit-map --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga> --template-id <template_id>
```

Quando `NOTION_APPLICATIONS_TEMPLATE_ID` estiver preenchido no `.env`, `create-from-fit-map` usa esse template automaticamente.

Na criação, o corpo da página deve receber:
- nota de aderência;
- dor central;
- resumo das dimensões da nota;
- gaps mitigados por reposicionamento com defesa;
- gaps ainda abertos;
- objeções do recrutador e mitigação.
- tabela/lista das 15 keywords-habilidade para ATS, com prioridade, experiência alvo, bullet sugerido e origem.
- sempre que existir um bloco de primeiro nível com texto `Pesquisa Inicial`, inserir a análise imediatamente abaixo dele; somente usar o fim da página como fallback quando esse bloco não existir.

3. **Atualização de página já existente no tracker Aplicações** — quando a vaga nasceu no Notion e o usuário pedir para registrar/devolver a análise, atualizar a mesma página em vez de criar duplicata:

```bash
python scripts/notion_sync.py update-from-fit-map <page_id> --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga> --dry-run
python scripts/notion_sync.py update-from-fit-map <page_id> --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga>
python scripts/notion_sync.py update-from-fit-map-record <id_unico> --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga> --dry-run
python scripts/notion_sync.py update-from-fit-map-record <id_unico> --fit-map .career-state/fit_map.json --job-description <arquivo_com_descricao_da_vaga>
```

4. **Registro ou atualização apenas da descrição extraída** — quando o usuário pedir "atualize a vaga ID/Notion
`<número>` com a descrição extraída" ou "crie/faça/registre a vaga no Notion" antes de haver FIT_MAP:

```bash
python scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo_com_descricao_da_vaga> --source-url "<url>" --dry-run
python scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo_com_descricao_da_vaga> --source-url "<url>"
python scripts/notion_sync.py create-description-record --job-description <arquivo_com_descricao_da_vaga> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run
python scripts/notion_sync.py create-description-record --job-description <arquivo_com_descricao_da_vaga> --company "<empresa>" --role "<cargo>" --source-url "<url>"
```

Use `update-description-record` quando o usuário mencionar `ID`, `Notion <número>` ou uma vaga já existente no tracker.
Use `create-description-record` quando o usuário pedir para criar/registrar a vaga extraída no Notion sem um registro
existente. Esses comandos só preenchem propriedades de intake como `Descrição da Vaga`, `Link`, empresa/cargo quando a
base permitir; análise de aderência continua sendo produzida depois pelo FIT_MAP.

Variações operacionais suportadas:
- se a vaga foi colada no chat e depois o usuário pedir para registrar no Notion, usar a descrição salva em `inbox/job_descriptions/` no `create-from-fit-map`
- se a vaga foi colada no chat, o usuário abriu manualmente um template no Notion e depois pediu para atualizar pelo `ID`, usar `update-from-fit-map-record <id_unico>`; quando o registro ainda tiver apenas texto de template, o script deve selecionar automaticamente a descrição local que combina com o FIT_MAP ativo
- se a vaga nasceu no Notion com descrição parcial ou completa, usar `prepare-analysis-from-record <id_unico>` como entrada da análise e devolver o resultado para o mesmo registro com `update-from-fit-map-record <id_unico>`

O `dry-run` de update deve ser lido antes da escrita real:
- `job_description_source = saved_job_description` significa que a vaga veio do arquivo local salvo no pipeline de análise
- `job_description_source = notion_page.description` significa que a vaga veio da propriedade `Descrição da Vaga` do Notion
- `Descrição da Vaga` com conteúdo de template (`Pesquisa Inicial`, `Feedback em caso de Reprovação`) não é descrição válida; se não houver descrição local compatível, a atualização deve bloquear
- nunca usar `--allow-mismatch` para contornar descrição errada; se houver mismatch, corrigir a descrição salva, o FIT_MAP ativo ou a origem da página antes da escrita real

Essa atualização deve preencher o que a base permitir nas propriedades e anexar ao corpo da página:
- nota de aderência;
- dor central;
- resumo das dimensões da nota;
- gaps mitigados por reposicionamento com defesa;
- gaps ainda abertos;
- objeções do recrutador e mitigação.
- tabela/lista das 15 keywords-habilidade para ATS, com prioridade, experiência alvo, bullet sugerido e origem.
- sempre que existir um bloco de primeiro nível com texto `Pesquisa Inicial`, inserir a análise imediatamente abaixo dele; somente usar o fim da página como fallback quando esse bloco não existir.

Regra dura de encoding para Notion:
- todo texto enviado a propriedades ou blocos deve ser UTF-8 legível e preservar acentos, travessões e aspas corretamente
- o script deve bloquear escrita quando detectar mojibake (`Ã`, `Â`, `â€“`, `â€”`, `â€™`, `â€œ`, `â€`, `ï¿½`)
- nunca “normalizar” visualmente no improviso; corrigir o artefato de origem e reexecutar

Regras críticas:
- nunca criar ou atualizar registro no Notion apenas porque uma análise foi feita;
- escrita no Notion exige pedido explícito do usuário;
- criação em `Aplicações` sempre usa template;
- se a vaga veio de `page_id` do Notion, preferir `update-from-fit-map` sobre `create-from-fit-map`; a nota de aderência não muda essa escolha, mesmo quando o score for alto;
- se o usuário disser `Notion 218`, `vaga Notion 218` ou equivalente, resolver a página pelo campo único `ID = 218`, não pelo título visível da página;
- bloquear criação se faltar nome da vaga, nota de aderência ou descrição da vaga;
- bloquear criação se `FIT_MAP` ativo e `job_description` apontarem para cargos/vagas diferentes;
- tratar divergência de empresa como alerta, não como bloqueio duro;
- quando houver mismatch, iniciar fluxo de recuperação: `career-fit-analysis` -> `build_fit_map.py` -> `score_fit_map.py` -> `validate_fit_map.py` -> nova tentativa de criação;
- leitura pode ser usada como contexto quando solicitada.

## Respostas A Perguntas De Candidatura

Quando o usuário pedir uma resposta curta para formulário, entrevista ou pergunta eliminatória:

- responder a pergunta logo na primeira frase
- se houver gap real, declarar com clareza antes de mitigar
- usar no máximo 2 ou 3 evidências concretas, com resultado e contexto
- fechar conectando essas evidências à pergunta, sem prometer aprendizado futuro nem criar tese abstrata sobre adaptabilidade
- evitar fórmulas com cara de IA, como `minha abordagem é setor-agnóstica`, `eu faria o mesmo`, `aprendo rápido`, `guardo paralelos relevantes`
- preferir voz factual: `Não atuei diretamente em telecom. Minha experiência mais próxima foi...`

## Entrega Local

Depois da aprovação por `output-reviewer`, entregue textos na conversa e arquivos em `outputs/`. Para arquivos, informe o caminho local relativo e absoluto quando útil.
