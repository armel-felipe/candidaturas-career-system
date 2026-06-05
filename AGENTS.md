# Career Job Application System — Felipe Armel

Sistema local de candidatura executiva. Toda tarefa relacionada a vaga, CV, pitch, carta, Gupy ou networking é executada pelas skills deste projeto.

## Governança das skills

Fonte canônica de manutenção: `.opencode/skills/{skill}/SKILL.md`.

Regra operacional:
- Para criar, corrigir, refatorar ou revisar uma skill, editar sempre `.opencode/skills/{skill}/SKILL.md`
- Nunca criar uma pasta paralela de skills fora de `.opencode/skills/`
- Ao citar uma skill em respostas, revisões ou instruções de manutenção, preferir sempre o caminho canônico em `.opencode/skills/`

## Regra de execução obrigatória

Antes de executar qualquer skill, ler o arquivo `SKILL.md` correspondente em `.opencode/skills/{skill}/SKILL.md`. Nunca executar de memória — os arquivos são atualizados com frequência.

Executar uma skill significa cumprir o workflow operacional descrito no arquivo, incluindo:
- leitura dos arquivos de referência exigidos
- geração dos artefatos intermediários obrigatórios
- execução dos scripts mandatórios
- persistência dos resultados nos caminhos definidos pela skill
- validação final do estado produzido

Se algum passo não puder ser executado:
- declarar explicitamente que a execução foi parcial ou bloqueada
- informar exatamente qual passo não foi executado
- nunca apresentar a skill como concluída

Comportamentos proibidos:
- tratar leitura de `SKILL.md` como execução
- substituir scripts obrigatórios por raciocínio textual
- afirmar conclusão sem persistir os artefatos exigidos pela skill
- encerrar com próximos passos opcionais quando o estado obrigatório da skill ainda não tiver sido produzido e validado
- preencher checklist ou bloco de validação operacional sem evidência real dos comandos executados
- presumir arquivos intermediários brutos por convenção de nome sem que tenham sido criados no runtime
- reutilizar estado ativo como se fosse análise nova quando o usuário colou uma nova vaga e a persistência inicial ainda não aconteceu
- aprovar CV em DOCX sem executar `python3 scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/fit_map.json --registry .opencode/skills/career-system/references/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json`
- tratar inspeção do script gerador como substituto da revisão do artefato final em `outputs/`
- limpar `outputs/_tmp/` antes de o gate objetivo de revisão do CV ter aprovado o artefato final

## Ponto de entrada único

Para OpenCode e agentes locais, o ponto de entrada canônico deste projeto é `AGENTS.md`.

Ordem canônica de execução:
1. Carregar `AGENTS.md` via `opencode.json`
2. Ler `.opencode/skills/career-system/SKILL.md`
3. Ler `.opencode/skills/{skill}/SKILL.md` antes de executar a skill pedida

Arquivos `LOCAL_LLM_*` podem existir como documentação auxiliar para outros runtimes, mas não fazem parte do fluxo canônico do projeto e não substituem `AGENTS.md` nem nenhum `SKILL.md`.

Regras de progressao para agentes locais:
- depois de ler a skill pedida, executar a proxima acao concreta antes de explicar o workflow novamente
- em respostas como `continue`, retomar do ultimo passo nao executado; nao recomeçar do passo 1 sem motivo real

## Skills disponíveis e gatilhos

| O usuário pede | Skill a executar |
|---|---|
| Analisar vaga / "como me encaixo" / colar anúncio | `intake-orchestrator` → `career-fit-analysis` |
| "Avalie a vaga em <URL>" / "analise a vaga em <URL>" quando a URL for `linkedin.com/jobs/view/...`, `linkedin.com/jobs/...` ou `linkedin.com/job/...` | `intake-orchestrator` → `career-fit-analysis` |
| "Avalie a vaga em <URL>" / "analise a postagem" / extrair vaga de post quando a URL for `linkedin.com/feed/update/...`, `linkedin.com/posts/...` ou `linkedin.com/pulse/...` | `intake-orchestrator` → `career-fit-analysis` |
| Gerar CV / currículo / adaptar CV | `intake-orchestrator` se a vaga ainda não estiver ativa → `career-fit-analysis` → `cv-generator` |
| CV geral / currículo geral / CV para sites de emprego / LinkedIn para busca ativa / competências gerais | `general-cv-optimizer` |
| Pitch / FERAS / "me fale sobre você" / resumo Gupy | `career-fit-analysis` → `feras-pitch` |
| Carta de apresentação / cover letter | `career-fit-analysis` → `cover-letter` |
| Habilidades Mercado Livre / habilidades Gupy / resumo ATS / aplicar pelo sistema | `career-fit-analysis` → `habilidades-chave` |
| Mensagem LinkedIn / networking / contato recrutador | `networking-message` |
| Link de vaga do LinkedIn / extrair descrição completa do LinkedIn / URL contendo `linkedin.com/jobs/view/` como `https://www.linkedin.com/jobs/view/4405127989/` | `linkedin-job-extractor` |
| Link de postagem do LinkedIn divulgando vaga / extrair descrição de post / URL contendo `linkedin.com/feed/update/`, `linkedin.com/posts/` ou `linkedin.com/pulse/` | `linkedin-job-extractor` |
| Pesquisar/listar/ler vaga no Notion / consultar `Notion <número>` | `notion-transactions`; para avaliar/analisar usar `intake-orchestrator` |
| Listar vagas salvas do LinkedIn / Rastreador de vagas / minhas vagas / saved jobs / escolher URL salva para análise | `linkedin-saved-jobs` |
| Atualize a vaga ID/Notion `<número>` com a descrição extraída / preencher `Descrição da Vaga` a partir da vaga extraída | `linkedin-job-extractor` se houver URL LinkedIn pendente → `notion-transactions` |
| Crie/faça/registre a vaga no Notion a partir da descrição extraída, antes de análise/FIT_MAP | `linkedin-job-extractor` se houver URL LinkedIn pendente → `notion-transactions` |
| Mandar algo para o próprio email / deixar em draft / enviar arquivo para o email informado / email de candidatura por Gmail | `self-email-draft` |
| Colar vaga + ID Notion + URL / "analisa e registra no Notion" / "faz tudo" / "analisa e salva" | `unified-job-analysis` |
| Revisar documento / "está bom?" / conferir | `output-reviewer` |
| Quais cargos combinam comigo | `career-fit-analysis` (Modo 2) |
| Posicionamento para cargo novo | `career-fit-analysis` (Modo 3) |

Instrução completa de cada skill: `.opencode/skills/{skill}/SKILL.md`.
Orquestração e regras globais: `.opencode/skills/career-system/SKILL.md`.

## Orquestrador de intake de vagas

Toda análise de vaga começa por um comando `intake:*`, que transforma diferentes origens em um estado comum:
descrição persistida em `inbox/job_descriptions/`, `active_intake` em `.career-state/workflow_state.json`,
template `.career-state/fit_map.draft.json` recriado, guard executado e `next_required_step` explícito.

Comandos oficiais:

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
npm run agent:evaluate-notion-local -- <id_unico>          # alias explícito do modo local/menor
```

Regra operacional:
- `intake:*` são comandos npm, não nomes de skill; a skill correspondente é `.opencode/skills/intake-orchestrator/SKILL.md`
- para `Avalie vaga Notion <número>`, executar preferencialmente `npm run agent:evaluate-notion -- <número>`; este comando é compatível com modelos locais/menores e também gera o mapa local e o request compacto antes de devolver a próxima ação
- `npm run agent:evaluate-notion-local -- <número>` existe como alias explícito do mesmo modo operacional; fallback permitido: `npm run intake:notion-record -- <número>`
- após qualquer intake, executar `npm run agent:guard` se houver dúvida, interrupção, output truncado ou tentação de fallback
- nunca executar `notion:list`, `grep`, query inventada, `.env`, `curl`, navegador ou script temporário para substituir `agent:evaluate-notion`/`intake:notion-record`
- para URL LinkedIn de vaga, executar `npm run intake:linkedin-job -- --url "<url>"`
- para URL LinkedIn de postagem, executar `npm run intake:linkedin-post -- --url "<url>" --company "<empresa>" --role "<cargo>"`
- para texto colado, salvar em arquivo real ou usar stdin com `intake:paste`
- depois do intake, se `next_required_step = fill_fit_map_draft`, a próxima ação é preencher `.career-state/fit_map.draft.json`; não entregar análise textual nem usar FIT_MAP antigo
- preencher `.career-state/fit_map.draft.json` é responsabilidade do agente: ler a skill/referências necessárias e editar o arquivo. Nunca pedir para o usuário preencher o template, abrir editor, substituir marcadores ou tratar o JSON bruto como entrega.
- em modo multiagente/local pequeno, depois do intake gerar/ler o request compacto com `npm run multiagent:request -- fit-map`; o agente deve seguir `Operational Rules` antes de editar o draft
- após qualquer edição de `.career-state/fit_map.draft.json`, executar `npm run validate:fit-map:draft`; se falhar, corrigir e reexecutar antes de responder ao usuário
- se `.career-state/fit_map.draft.json` ficar com JSON inválido, executar `npm run fit-map:template` para resetar o template da vaga ativa antes de continuar
- `intake:resume` é o comando padrão para retomar trabalho interrompido e descobrir o próximo passo
- o JSON de saída do intake inclui `delivery_plan` para CV, FERAS, carta, habilidades e atualização no Notion
- se qualquer comando `intake:*` falhar, é proibido abrir `.env`, copiar token, montar `curl`, criar script temporário ou abrir Notion no navegador; executar `npm run intake:resume` e relatar o bloqueio objetivo
- se `agent:guard` retornar `allowed_next_action = fill_fit_map_draft`, a única próxima ação autorizada é preencher `.career-state/fit_map.draft.json`

Regra para URL de vaga LinkedIn:
- qualquer pedido de avaliação/análise/CV/fit que contenha URL `linkedin.com/jobs/view/`, `linkedin.com/jobs/` ou `linkedin.com/job/` deve executar primeiro `linkedin-job-extractor`
- qualquer pedido de avaliação/análise/CV/fit que contenha URL de postagem `linkedin.com/feed/update/`, `linkedin.com/posts/` ou `linkedin.com/pulse/` deve executar primeiro `linkedin-job-extractor`
- nunca usar ferramenta de navegador genérica, `browser_navigate`, `web_search` ou busca web para abrir/analisar vaga LinkedIn; o LinkedIn exige sessão local persistida e o caminho único é o script do projeto
- em execução automatizada, o comando padrão é `npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"`; se falhar por sessão expirada, bloquear e pedir/rodar `npm run linkedin:auth` conforme `LINKEDIN_AUTH_RUNBOOK.md`
- para postagem, o comando padrão é `npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"`; se a postagem trouxer link de vaga, o script delega para o extrator de vaga
- em pedidos de análise/CV/fit, preferir os wrappers de intake (`intake:linkedin-job` ou `intake:linkedin-post`), pois eles extraem, salvam, registram `active_intake`, geram o template e devolvem o próximo passo
- depois de a descrição ser extraída e salva, executar a skill solicitada sobre a vaga salva; para "avaliar/analisar vaga", executar `career-fit-analysis`
- nunca tentar analisar a URL diretamente sem antes persistir a descrição extraída

Regra para vagas salvas do LinkedIn/Rastreador de vagas:
- pedidos para listar vagas salvas, ver "minhas vagas", consultar saved jobs ou escolher uma vaga salva para análise devem executar `.opencode/skills/linkedin-saved-jobs/SKILL.md`
- a skill `linkedin-saved-jobs` só identifica vagas e URLs salvas; ela não analisa aderência, não gera FIT_MAP e não substitui intake
- o comando obrigatório para listar é `npm run linkedin:saved-jobs:extract`, que abre `https://www.linkedin.com/jobs-tracker/`, usa a sessão Playwright persistida, lê a aba `Salvas` e grava `inbox/linkedin_saved_jobs.json`
- não ler `inbox/linkedin_saved_jobs.json` antigo como substituto da extração, salvo pedido explícito para consultar a última extração salva
- depois que o usuário escolher uma vaga da lista, executar `npm run intake:linkedin-job -- --url "<url-da-vaga-escolhida>"` e seguir `next_required_step`
- nunca usar `npm run linkedin:extract:authenticated` como caminho final quando o objetivo for análise/FIT_MAP de uma vaga escolhida no Rastreador de vagas; usar o wrapper de intake

## Pipeline FIT_MAP — comandos exatos

```bash
# 1. Salvar descrição da vaga colada antes do FIT_MAP
python3 scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --text-file <arquivo>

# Quando o texto vier diretamente do chat/pipe
cat <<'EOF' | python3 scripts/save_job_description.py --company "<empresa>" --role "<cargo>" --stdin
<texto bruto da vaga>
EOF

# 2. Gerar draft (o agente preenche o arquivo após análise; não delegar ao usuário)
npm run fit-map:template
npm run fit-map:guard
npm run fit-map:status
npm run fit-map:draft-summary
npm run fit-map:check:extract
npm run fit-map:check:map-evidence
npm run fit-map:check:score-draft
npm run fit-map:check:complete-draft
npm run validate:fit-map:draft

# 3. Canonizar, pontuar e validar
npm run fit-map:build
npm run fit-map:score
npm run validate:fit-map
npm run fit-map:summary
npm run validate:fit-map:quality

# Alternativa composta preferencial quando o draft já está pronto
npm run fit-map:finalize

# Diagnosticar retomada/travamento entre template, draft e FIT_MAP
npm run fit-map:status
npm run fit-map:guard

# 4. Registrar keywords ATS
python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json
python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv outputs/<cv>.docx
npm run registry:summary

# 5. Opcional: reassociar a descrição da vaga usando o FIT_MAP final
python3 scripts/save_job_description.py --fit-map .career-state/fit_map.json --text-file <arquivo>

Observação:
- `--text-file` exige um caminho real de arquivo
- `--text-file -` não usa stdin neste projeto
- para texto pipado/colado na execução, usar `--stdin`
```

## CV em DOCX — comandos exatos

```bash
npm run cv:docx                                              # gera via Node.js (docx lib)
npm run validate:docx                                        # valida o DOCX gerado
python3 scripts/review_output.py --kind cv --artifact outputs/<cv>.docx --fit-map .career-state/fit_map.json --registry .opencode/skills/career-system/references/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
npm run docx:tmp:clean                                       # limpa resíduos em outputs/_tmp/

# Comando composto preferencial para registrar keywords + revisar o DOCX final
npm run cv:approve -- --artifact outputs/<cv>.docx
npm run cv:deliver -- --artifact outputs/<cv>.docx                # aprova e entrega via rclone somente se aprovado
```

Regra global para CV em DOCX:
- o idioma do CV segue o idioma da descrição da vaga: descrição em inglês gera CV em inglês; descrição em português gera CV em português
- CV de vaga em inglês usa sufixo obrigatório `_en` antes da extensão e texto visível em inglês
- CV de vaga em português não usa sufixo `_en` e texto visível em português
- em nenhum CV é permitido juntar experiências, cargos, promoções, fases ou escopos em uma única entrada; se houver limite de espaço, selecionar experiências separadas por aderência, nunca consolidar
- `register_keywords.py --cv` deve rodar sobre o artefato final em `outputs/` antes do `review_output.py`
- se `review_output.py` falhar, não for executado, ou retornar `approved_for_delivery=false`, a entrega do CV conta como incompleta
- o gate do CV usa blockers e warnings: blockers impedem entrega; warnings não impedem entrega sozinhos
- política ATS top 8: `covered_exact=1,0`, `covered_similar=0,8`, `declared_gap=0`, `missing_unexplained=0`; aprovação mínima exige score >= 5,2/8 e zero `missing_unexplained`; ótimo exige >= 6,2/8
- `pt_cv_keyword_shotgun_control` é blocker em CV PT-BR quando o gate detectar cluster artificial de keywords em inglês; naturalidade humana prevalece sobre matching literal
- todo CV PT-BR passa por polimento textual obrigatório no `output-reviewer`, mesmo quando o gate objetivo aprovar de primeira; se o polimento alterar texto, regenerar DOCX, rerodar `register_keywords.py --cv` e rerodar `review_output.py`
- qualquer bloco "Revisão concluída" sem esse comando é inválido
- comando preferencial quando o objetivo for aprovar e enviar para OneDrive: `npm run cv:deliver -- --artifact outputs/<cv>.docx`
- `cv:deliver` deve bloquear se `cv:approve` falhar, se `approved_for_delivery=false`, se houver blocker de polimento ou se `deliver:artifact` não retornar `status=delivered`

## Entrega de artefatos via OneDrive/rclone

```bash
npm run deliver:artifact -- --file outputs/<arquivo>.docx --dry-run
npm run deliver:artifact -- --file outputs/<arquivo>.docx
```

Regra global de entrega:
- a fonte oficial continua sendo o arquivo local em `outputs/`
- a entrega para nuvem usa `rclone` com `RCLONE_ONEDRIVE_REMOTE` e `RCLONE_ONEDRIVE_DELIVERY_DIR` definidos no `.env` local de cada máquina
- MacBook e servidor Ubuntu/RPi5 usam o mesmo comando, desde que o `rclone config` tenha sido feito naquela máquina
- nunca subir configuração real do rclone, tokens ou `.env` para GitHub
- para CV, só executar entrega depois de `cv:approve` aprovado no artefato final
- cada entrega grava relatório em `outputs/_tmp/delivery_report.json`; sem `status=delivered` ou `dry_run_ok`, não afirmar que o upload funcionou

## CV geral — comandos exatos

```bash
npm run general-cv:strategy
npm run general-cv:strategy -- --mode expanded --bullet-count 5
npm run general-cv:strategy -- --mode concise --dominant-cluster operacoes_supply_logistica
npm run general-cv:validate-content -- --path .career-state/general_cv_content.json
npm run general-cv:docx
npm run general-cv:approve -- --artifact outputs/felipe_armel_cv_geral_operacoes_supply_chain.docx
npm run general-cv:deliver -- --artifact outputs/felipe_armel_cv_geral_operacoes_supply_chain.docx
```

Regra global para CV geral:
- modo padrão é `concise` com `bullet_count=3`
- modo expandido/bullet points só deve ser usado quando o usuário pedir explicitamente
- se o agente inferir que expandido pode ser melhor, validar com o usuário antes; sem confirmação explícita, manter conciso
- modo expandido aceita somente 4 a 8 bullets por experiência
- cada bullet narrativo expandido deve ter 270 a 330 caracteres e evidência defensável
- modo `concise` usa `dominant_cluster=operacoes_supply_logistica` quando o usuário não informar outro foco
- modo conciso usa 3 bullets por experiência e não tenta cobrir todos os clusters
- clusters aceitos: `operacoes_supply_logistica`, `planejamento_sop_capacity`, `transformacao_eficiencia`, `cx_saas_operations`, `product_revenue_business_ops`
- DOCX geral final continua sujeito ao gate objetivo de aprovação antes da entrega

## Gmail draft — comandos exatos

```bash
npm run gmail:auth
python3 scripts/create_gmail_draft.py --to "<email>" --subject "<assunto>" --body "<corpo>" --dry-run
python3 scripts/review_email_text.py --subject "<assunto>" --body "<corpo>"
python3 scripts/create_gmail_draft.py --to "<email>" --subject "<assunto>" --body "<corpo>" --attach "<arquivo>"
```

Regra global para drafts de email:
- toda tarefa de email por Gmail usa `self-email-draft`
- o remetente é sempre a conta Gmail autenticada pelo OAuth local; nunca perguntar email de envio/remetente
- para email de candidatura, usar os templates Multinacional ou Startup definidos em `.opencode/skills/self-email-draft/SKILL.md`
- antes de criar draft real, revisar ortografia/fluidez, remover termos internos ou canônicos, e exibir destino, assunto, corpo completo e anexos validados
- `scripts/review_email_text.py` deve passar antes do preview aprovado e antes do draft real
- só executar `create_gmail_draft.py` sem `--dry-run` depois de aprovação explícita do usuário
- nunca enviar email automaticamente

## Notion — comandos exatos

```bash
npm run intake:notion-record -- <id_unico>                  # entrada padrão para avaliar/analisar vaga por ID do Notion
npm run notion:list                                          # lista candidaturas
npm run notion:link-record -- <id_unico>                    # resolve link por ID sem varrer cache
npm run notion:record-summary -- <id_unico>                 # alias compacto do link por ID
npm run notion:templates                                     # lista templates disponíveis
npm run notion:sweep:refresh                                 # sincroniza o snapshot local a partir do Notion e reescreve o cache consolidado
npm run notion:sweep:build-cache                             # apenas reconstrói o cache local a partir do sweep já salvo
npm run notion:create-current                                # cria página a partir do FIT_MAP ativo
python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run
python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>" --dry-run
python3 scripts/notion_sync.py read-page <page_id> --save     # ler página específica
npm run notion:prepare-page -- <page_id>                     # transformar uma página existente em entrada formal para análise
npm run notion:update-page-current -- <page_id> --dry-run    # prévia da atualização da mesma página com o FIT_MAP ativo
npm run notion:update-page-current:compact -- <page_id> --dry-run # prévia compacta sem payload grande
npm run notion:prepare-record -- <id_unico>                  # resolver pelo campo ID da tabela e preparar a análise
npm run notion:update-record-current -- <id_unico> --dry-run # prévia da devolução da análise pelo ID único
npm run notion:update-record-current:compact -- <id_unico> --dry-run # prévia compacta sem blocos/payloads
```

## Orquestrador automático de candidaturas

```bash
npm run applications:config
npm run applications:heartbeat -- --dry-run --max-per-run 1
npm run applications:heartbeat -- --max-per-run 3
npm run applications:agent-heartbeat -- --max-per-run 3
npm run applications:agent-heartbeat -- --max-per-run 3 --model openai/gpt-5.4 --variant medium
npm run applications:heartbeat:install-task -- --interval-minutes 60 --max-per-run 3 --run-agent
```

Regra operacional do heartbeat:
- processa vagas elegíveis do Notion em sequência, nunca em paralelo
- `max_per_run` define quantas vagas entram no lote do ciclo; a execução continua serial, uma vaga por vez
- status de tratamento automático deve ser `Fila Agente`
- status `Reprocessar` força limpeza completa do pacote local da candidatura antes do próximo ciclo
- status final configurado para vagas processadas é `Aplicação andamento`
- vaga em fila sem campo `Descrição da Vaga` preenchido deve ser ignorada pelo agente e movida para `Sem descrição de vaga`
- o orquestrador detecta o idioma da descrição e grava `required_cv_language` no manifest da candidatura
- a configuração local fica em `.career-state/applications_v2/config.json`
- cada candidatura tem memória própria em `.career-state/applications_v2/<ID>/`
- o estado canônico por vaga fica em `.career-state/applications_v2/<ID>/state.json`
- o índice leve para conversa futura fica em `.career-state/applications_v2/index.json`
- o launchd apenas dispara o comando; o orquestrador local decide fila, lock, status, memória e gates
- `applications:agent-heartbeat` executa `analyze` e `generate`; render, review, polish e finalize são locais
- o modelo e variant ficam em `.career-state/applications_v2/config.json` e também podem ser sobrescritos por execução com `--model provider/model --variant medium`
- o heartbeat não marca uma candidatura como pronta se faltar FIT_MAP, DOCX final em `outputs/`, reviewer objetivo aprovado ou `polish_review.json`
- CV PT-BR só pode ser aprovado com `outputs/_tmp/output_review_report.json` e `outputs/_tmp/polish_review.json` compatíveis

Entrega e persistência por candidatura:
- a memória permanente da candidatura fica em `.career-state/applications_v2/<ID>/` até remoção manual ou rotina explícita de limpeza
- FIT_MAP canônico da candidatura: `.career-state/applications_v2/<ID>/fit_map.json`
- descrição da vaga: `.career-state/applications_v2/<ID>/job_description.md`
- FERAS: `.career-state/applications_v2/<ID>/feras_formal.md`
- habilidades Gupy: `.career-state/applications_v2/<ID>/habilidades_gupy.md`
- habilidades Mercado Livre: `.career-state/applications_v2/<ID>/habilidades_mercado_livre.md`
- conteúdo estruturado do CV: `.career-state/applications_v2/<ID>/cv_content.json`
- DOCX final aprovado: `outputs/<cv>.docx`
- logs do heartbeat: `.career-state/applications_v2/_logs/`
- `.career-state/fit_map.json` continua existindo para skills gerais, mas não é a fonte primária do heartbeat

Fluxo manual canônico de candidatura:
- o comando canônico exposto neste momento é o heartbeat
- comandos manuais por etapa e por `record_id` não fazem mais parte da superfície operacional do projeto
- quando precisarmos reabrir operação manual, ela deve nascer já no `v2`, não ser reintroduzida do sistema antigo

Regra de payload compacto para agentes:
- o agente deve ler primeiro `analysis_request.json/md`, `generation_request.json/md` ou `repair_request.json/md`
- o request define os únicos arquivos permitidos na etapa
- o request nunca pode mandar o agente “executar o pipeline completo”
- referências longas são fallback, não leitura inicial obrigatória

Condições suportadas para atualização no Notion:
- vaga colada no chat e depois criação de página no Notion: usar `npm run notion:create-current`/`create-from-fit-map` com a descrição salva em `inbox/job_descriptions/`
- vaga colada no chat e template aberto manualmente no Notion: usar `npm run notion:update-record-current -- <id_unico> --dry-run`; quando a página ainda tiver texto de template, o script deve usar automaticamente a descrição salva que combina com o FIT_MAP ativo
- parte da vaga já registrada no Notion e depois análise local: usar `npm run notion:prepare-record -- <id_unico>`, executar `career-fit-analysis`, e devolver com `npm run notion:update-record-current -- <id_unico> --dry-run`

Regra para template manual:
- nunca usar `--allow-mismatch` para contornar descrição errada
- para "atualize a vaga ID/Notion <número> com a descrição extraída", usar `update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>" --dry-run` antes da escrita real
- para "crie/faça/registre a vaga no Notion" a partir de uma descrição extraída e ainda sem FIT_MAP, usar `create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run` antes da escrita real
- se o dry-run mostrar `job_description_source = saved_job_description`, a atualização está usando a vaga salva localmente
- se mostrar `job_description_source = notion_page.description`, a atualização está usando o texto que já está no Notion
- se a propriedade `Descrição da Vaga` ainda for apenas template e não houver descrição local compatível, bloquear e pedir/salvar a vaga antes de atualizar

Regra operacional para histórico do Notion:
- se a tarefa depender de consultar candidaturas anteriores salvas no Notion, atualizar sempre com `npm run notion:sweep:refresh` antes de usar `inbox/notion/applications_cache.json`
- motivo: pode haver edições feitas diretamente no Notion fora deste projeto
- `npm run notion:sweep:build-cache` fica restrito a reindexação local deliberada ou manutenção técnica do cache, não como passo padrão de leitura

## OpenCode local

Este repositório deve ser executado priorizando o OpenCode no diretório raiz do projeto.

Configuração local do runtime:
- `opencode.json`
- `.opencode/skills/`

Regras operacionais:
- o agente padrão deve ser `build`
- instruções carregadas via `opencode.json` devem incluir `AGENTS.md`
- skills devem ser descobertas em `.opencode/skills/` e lidas a partir do `SKILL.md` correspondente antes da execução
- permissões devem favorecer execução local do projeto sem depender de `settings.json` do Claude

## Camada operacional estruturada

Além dos scripts legados em `scripts/`, o projeto agora possui uma camada estruturada em:
- `src/career/schemas/` para contratos de dados
- `src/career/services/` para operações reutilizáveis
- `src/career/tasks/` para tarefas com dependências explícitas
- `src/career/workflow/` para controle de estado e bloqueio de transições inválidas
- `scripts/career_cli.py` como CLI estruturada oficial

Regra operacional:
- preferir os comandos do `package.json` ou `python3 scripts/career_cli.py ...` como entrypoint oficial
- scripts legados continuam existindo como compatibilidade técnica e suporte às services
- quando um comando oficial gravar estado de workflow, não burlar a sequência rodando manualmente uma etapa posterior sem satisfazer as pré-condições
- o workflow estruturado registra a vaga ativa por fingerprint da descrição salva; pré-requisitos de FIT_MAP devem pertencer à mesma vaga ativa, não a uma análise anterior
- preferir `npm run fit-map:finalize` quando o draft já estiver preenchido e `npm run cv:approve -- --artifact outputs/<cv>.docx` para o gate final do CV
- usar `npm run fit-map:status` quando houver dúvida sobre retomada, template com placeholders ou FIT_MAP possivelmente antigo
- usar `npm run fit-map:resume` quando `fit-map:status` indicar template com placeholders, FIT_MAP antigo ou retomada travada; executar a ação indicada sem reexplicar o workflow
- usar `npm run fit-map:guard` imediatamente após `fit-map:template` e em qualquer retomada; se retornar `guard=blocked`, a próxima ação deve ser o `required_next_command`, sem análise textual intermediária
- usar `npm run runtime:diagnose` para investigar custo operacional e `npm run memory:build` para regenerar a memória compacta local
- usar `npm run workflow:summary`, `npm run fit-map:summary`, `npm run fit-map:draft-summary`, `npm run registry:summary` e `npm run local:strict:doctor` antes de qualquer inspeção manual ampla
- usar `npm run validate:fit-map:quality` após `fit-map:finalize` quando o modelo local tiver reescrito o draft, para capturar degradação textual/semântica que schema não detecta
- usar `npm run benchmark:local-agent` para checar rapidamente se o estado ativo está saudável para modelos locais antes de continuar geração/atualização

## Política de contexto compacto

Regra global:
- artefatos intermediários grandes devem ficar em arquivos; a conversa deve conter apenas ponteiros, resumos curtos, contagens, paths e erros objetivos

Comportamentos obrigatórios:
- ler arquivos localmente e responder só com síntese curta
- nunca imprimir FIT_MAP, draft, registry ATS, cache Notion, descrição longa ou payload de validação completo
- evitar diff gigante de `.career-state/fit_map.draft.json`; ao editar arquivo grande, relatar apenas que o arquivo foi persistido e validado
- para JSON, usar projeções pequenas (`jq`/campos específicos) ou comandos compactos do projeto; não usar `cat` em artefatos grandes
- quando validar, retornar apenas `passed/failed`, contagens, score/path e erros objetivos
- para Notion por ID, usar `npm run notion:link-record -- <id_unico>` ou scripts canônicos por ID; não varrer `applications_cache.json`/`applications_sweep` com `grep -r`
- para dry-run de atualização Notion em modelos locais, preferir `npm run notion:update-record-current:compact -- <id_unico> --dry-run`
- limitar saída de comandos; se um comando gerar output grande, rerodar com modo compacto ou projeção seletiva

Comportamentos proibidos:
- colar JSON completo do FIT_MAP ou do draft na conversa
- colar diff completo de reescrita de FIT_MAP/draft
- usar `grep -r`/`rg` amplo em `inbox/notion`, `.career-state`, `outputs` ou `.opencode` sem filtro e limite estrito
- usar leitura de cache local como substituto para comando canônico de Notion por ID
- tratar output truncado como evidência completa

## Camada multiagente local

O fluxo manual também pode operar por maestro determinístico e agentes especialistas de escopo curto.

Comandos oficiais:

```bash
npm run agent:maestro
npm run agent:maestro -- fit-map
npm run agent:maestro -- cv
npm run agent:maestro -- notion-update
npm run agent:maestro -- email-draft
npm run agent:maestro -- linkedin
npm run agent:evaluate-notion -- <id_unico>
npm run agent:evaluate-notion-local -- <id_unico>          # alias explícito
npm run multiagent:runbook
npm run multiagent:local-model-map
npm run multiagent:request -- fit-map
npm run validate:workspace-clean
```

Regras operacionais:
- para modelos locais/menores, `npm run agent:evaluate-notion -- <id_unico>` já gera `.career-state/agent_requests/local_model_map.md` e o request compacto `fit-map`; o agente deve ler esses arquivos antes de editar o draft
- o maestro decide o próximo passo, grava requests compactos em `.career-state/agent_requests/` e bloqueia improvisos
- agentes especialistas devem ler primeiro o request correspondente e só operar nos arquivos/comandos permitidos
- `fit-map-agent` só preenche `.career-state/fit_map.draft.json`; não finaliza, não entrega score em texto e não edita `.career-state/fit_map.json`
- `cv-agent` gera conteúdo/DOCX, mas aprovação depende de `npm run cv:approve -- --artifact outputs/<cv>.docx`
- `notion-agent` só faz dry-run até aprovação explícita do usuário
- `email-agent` só cria draft real após aprovação explícita do usuário; nunca envia email
- `linkedin-agent` usa apenas scripts locais autenticados; nunca browser/web_search genérico
- todo request especialista deve trazer `Operational Rules`; se o agente ler o request e ignorar essas regras, tratar como execução parcial/stall
- `fit-map-agent`: se o draft tiver placeholders, deve editar o arquivo; não pode imprimir template bruto nem pedir ao usuário para preencher
- `fit-map-agent`: se o request indicar `Current FIT_MAP.matches_active_job = false`, o FIT_MAP ativo é antigo e não pode ser reutilizado
- `fit-map-agent`: depois de editar, deve rodar `npm run validate:fit-map:draft`; se o JSON quebrar ou a validação falhar, deve corrigir antes de responder
- `cv-agent`: não pode entregar apenas texto; deve produzir DOCX em `outputs/`, validar DOCX e rodar `cv:approve` no artefato final
- `notion-agent`: escrita real no Notion é proibida sem aprovação explícita depois do dry-run; deve bloquear mismatch, template vazio sem descrição local ou mojibake
- `email-agent`: deve rodar revisão textual antes do preview e só criar draft real após aprovação explícita; nunca pergunta remetente
- `linkedin-agent`: deve persistir a descrição e confirmar `active_intake`; se a sessão expirar, usa `linkedin:auth`, não navegador/busca genérica
- criação de arquivos temporários na raiz como `gen_*.py`, `generate_*fitmap*.py`, `create_draft.py`, `create_drafi.py` ou `tmp_*.py` é bloqueio operacional

## Validação da estrutura oficial

Antes e depois de qualquer manutenção estrutural, mudança em skills ou saneamento do projeto, executar:

```bash
npm run validate:structure
```

Essa validação deve falhar se houver caminhos legados, pastas paralelas de skill, estado local paralelo ou instaladores antigos de skills fora de `.opencode/skills/`.

Ela tambem deve falhar se a skill `career-fit-analysis` ou qualquer documentacao operacional voltar a documentar um fluxo ambiguo para salvar a vaga antes do FIT_MAP.

## Checklist anti-loop para benchmarking

Ao avaliar modelos locais neste projeto, usar este criterio minimo:
- apos carregar a skill, deve haver acao concreta em ate 1 resposta
- nao pode haver mais de 1 resposta consecutiva apenas reenumerando o workflow
- deve haver leitura de referencia ou persistencia da vaga em ate 2 respostas
- `continue` deve retomar o ultimo passo nao executado, sem resetar a analise inteira
- o agente nao pode declarar nota final antes de `npm run fit-map:score`
- antes de preencher `.career-state/fit_map.draft.json`, não escrever subtotais nem nota final na conversa; classificar os itens diretamente no draft
- depois de salvar a vaga e ler as referencias obrigatorias, deve ir direto para `npm run fit-map:template`
- se o template já existe e ainda tem placeholders, rodar `npm run fit-map:resume`; a ação seguinte deve preencher `.career-state/fit_map.draft.json` ou declarar bloqueio real
- se `npm run fit-map:guard` retornar `blocked=true`, qualquer resposta subsequente sem edição do draft conta como falha de benchmark
- logs suspeitos devem ser avaliados com `python3 scripts/diagnose_session_stall.py <session.md>`; `stalled=true` significa execução parcial

## Paths locais

| Recurso | Caminho |
|---|---|
| Referências canônicas | `.opencode/skills/career-system/references/` |
| Memória canônica por candidatura | `.career-state/applications_v2/<ID>/` |
| Estado canônico por candidatura | `.career-state/applications_v2/<ID>/state.json` |
| FIT_MAP canônico por candidatura | `.career-state/applications_v2/<ID>/fit_map.json` |
| FIT_MAP ativo legado / espelho | `.career-state/fit_map.json` |
| Estado do workflow | `.career-state/workflow_state.json` |
| Vagas coladas / salvas | `inbox/job_descriptions/` |
| Outputs entregues | `outputs/` para DOCX final e logs |
| Temporários DOCX | `outputs/_tmp/` (gitignored, limpar com `npm run docx:tmp:clean`) |
| Scripts | `scripts/` |
| Pacote estruturado | `src/career/` |
| Scripts DOCX | `scripts/docx/` (`generate_cv_docx.js`, `validate_docx.py`, `convert_pdf.sh`) |

## Notion — integração exclusiva via scripts

Toda interação com o Notion é feita exclusivamente via `scripts/notion_sync.py` e `scripts/notion_query.py`. Ferramentas MCP de Notion (`notion-fetch`, `notion-search`, `notion-update-page`, `notion-create-pages` e similares) são **proibidas** neste projeto — independente do motor de IA em uso.

Notion tem skill operacional própria: `.opencode/skills/notion-transactions/SKILL.md`. Essa skill é uma camada de workflow; a implementação continua exclusivamente nos scripts locais. Não procurar, carregar nem inventar skills como `notion-query`, `notion-cli-fallback`, `notion-create-description`, `notion-update-record` ou equivalentes.

Também é proibido consultar `.env`, copiar `NOTION_TOKEN`, montar `curl` manual ou chamar a API pública do Notion diretamente. Os scripts locais carregam a configuração e resolvem diferenças de API, data source, propriedades e template.

Motivo: o projeto precisa operar com o mesmo canal de acesso ao Notion, independente de modelo ou runtime, para garantir rastreabilidade e consistência.

Criação no Notion exige pedido explícito do usuário e usa sempre o template cadastrado.
Na criação por `create-from-fit-map`, além das propriedades, o corpo da página deve receber a análise de aderência do FIT_MAP (nota, dor central, resumo das notas, gaps, objeções e defesas, e tabela/lista das 15 keywords-habilidade para ATS), inserida abaixo de `Pesquisa Inicial` quando esse bloco existir.

Atualização de uma página já existente no Notion também exige pedido explícito do usuário. Quando a vaga nascer no Notion, preferir atualizar a mesma página via `update-from-fit-map` em vez de criar uma duplicata.
Quando o usuário referenciar `Notion <número>`, tratar esse número como o valor do campo único `ID` da tabela e resolver a página correspondente antes de ler ou atualizar.
Todo texto devolvido ao Notion deve permanecer em UTF-8 legível. Nunca enviar ou aceitar como pronto texto com sinais de mojibake como `Ã`, `Â`, `â€“`, `â€”`, `â€™`, `â€œ`, `â€` ou `ï¿½`; corrigir a origem e repetir o comando.

## Regras que nunca mudam

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
- Respostas a perguntas de candidatura devem responder de forma direta, com defesa curta e fatos verificáveis. Evitar encerramentos genéricos como “aprendo rápido”, “minha abordagem é setor-agnóstica” ou hipóteses amplas do tipo “eu faria o mesmo”.
- `output-reviewer` roda obrigatoriamente após toda skill de produção, antes de entregar qualquer documento

## Números críticos — nunca alterar

| Empresa | Métrica | Valor |
|---|---|---|
| wehandle | Margem bruta | 15% |
| wehandle | Custo por atendimento | R$4,14 → R$3,61 (−13%) |
| iFood | Saving simulador | R$70MM/ano |
| iFood | Budget OPEX logístico | R$300MM/ano |
| iFood | Cobertura geográfica | 400 → 800 cidades |
| VivaReal | Conversão SDR inbound | 18% → 50% |
| VivaReal | Área de CS | 91 pessoas |
| Trifil | Redução de GGF | R$8MM |
