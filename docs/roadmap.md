# Roadmap vivo — Sistema de candidaturas

Este documento é o backlog operacional e técnico consolidado do projeto. Ele
registra problemas, melhorias e decisões que atravessam mais de um plano de
implementação.

## Regra de autoridade

- O roadmap registra **o que precisa ser tratado**.
- Um plano paralelo registra **como uma frente específica será executada**.
- Um plano paralelo pode concluir um item do roadmap, mas não pode deixá-lo
  implicitamente resolvido.
- Toda criação, execução ou encerramento de plano deve revisar este arquivo.
- Um item só sai do backlog com evidência verificável, referência ao teste ou
  comando executado e data da atualização.
- Se uma mudança de arquitetura tornar um item desnecessário, ele recebe
  `SUPERSEDED`, com a decisão e o plano que substituiu a abordagem.
- Novos problemas descobertos durante qualquer execução entram aqui antes de
  serem tratados como “observação informal”.

## Estados

| Estado | Significado |
|---|---|
| `BACKLOG` | Identificado, ainda sem execução iniciada. |
| `IN_PROGRESS` | Existe uma implementação ou investigação em andamento. |
| `BLOCKED` | Há uma dependência externa ou decisão pendente. |
| `DONE` | Critérios de saída comprovados e evidência registrada. |
| `SUPERSEDED` | A abordagem deixou de fazer sentido por decisão documentada. |

## Checklist obrigatório para qualquer plano paralelo

Antes de iniciar:

- [ ] Ler este roadmap.
- [ ] Associar cada tarefa do plano a um ID existente ou criar um novo ID.
- [ ] Declarar quais itens serão tratados, observados ou não afetados.

Antes de encerrar:

- [ ] Atualizar o estado de todos os IDs relacionados.
- [ ] Registrar testes, comandos, artefatos ou decisão de supersessão.
- [ ] Confirmar que nenhuma pendência tratada permanece aberta por erro de
      sincronização entre o plano e este roadmap.
- [ ] Registrar novas pendências descobertas durante a execução.

## Pendências operacionais atuais

| ID | Estado | Prioridade | Item | Plano relacionado | Critério de saída |
|---|---|---|---|---|---|
| `RUNTIME-OBS-001` | `IN_PROGRESS` | P1 | Encerrar a janela de observação da Fase 8 e decidir o arquivamento do JSON legado. | `2026-08-18-runtime-unification` | Janela encerrada com evidência; JSON arquivado ou decisão explícita de preservação. |
| `RUNTIME-002` | `DONE` | P1 | Hermes não conseguia atravessar a raiz do workspace como usuário não-root; hook de contexto não era executável. | Diagnóstico dos bots após cutover | Permissões `755` aplicadas, teste regressivo aprovado e acesso UID 10000 comprovado nos dois bots. |
| `RUNTIME-003` | `DONE` | P1 | O resolver SQLite ignorava `CAREER_CONTROL_DB_PATH` e tentava gravar no caminho readonly do mount raiz. | Diagnóstico dos bots após cutover | `canonical_database()` usa o caminho injetado; intake 591 grava no `.career-control` e teste de resolução aprovado. |
| `RUNTIME-004` | `DONE` | P1 | `sqlite_only` perdia `active_intake` após novo processo porque o ponteiro existia apenas no JSON de compatibilidade. | Diagnóstico dos bots após cutover | Projeção SQLite reconstrói o intake; teste de reinício aprovado e `intake:resume -- --application-id notion_591` retorna `active_intake_ready`. |
| `RUNTIME-006` | `DONE` | P1 | O supervisor procurava `application_id` no nível errado do retorno de `evaluate_notion` e bloqueava o especialista. | Diagnóstico dos bots após cutover | ID propagado no envelope de intake; guard e preparação do request 591 passam com escopo explícito. |
| `RUNTIME-007` | `DONE` | P1 | O runner dependia de `PATH` para localizar `hermes` no subprocesso. | Diagnóstico dos bots após cutover | Runner resolve `/opt/hermes/bin/hermes` no container e o request 591 alcança a execução do modelo. |
| `RUNTIME-005` | `DONE` | P1 | O runtime principal dos bots deve usar modelos grandes no Ollama Cloud, sem retirar a possibilidade de seleção local explícita. | `2026-08-25-critical-roadmap-fixes` | Os quatro arquivos efetivos usam `provider: ollama-cloud` e `deepseek-v4-flash:0731`; `tailscale-openai-local` permanece disponível nos perfis, mas não é fallback/default. |
| `RUNTIME-008` | `DONE` | P1 | A identidade física do SQLite incluía hostname/machine-id do container; dois bots com o mesmo bind mount calculavam identidades diferentes e o segundo não herdava a autorização do primeiro. | Correção de identidade cross-container | Identidade baseada na cópia montada (`st_dev` + `st_ino`), igual nos dois containers; ledger normalizado pelo comando oficial em 2026-08-24 e ambos passam `assert_authoritative_storage`. |
| `RUNTIME-009` | `DONE` | P1 | `applications:plan` deixava um lease celular vivo ao terminar; o processo seguinte (`applications:run`) era bloqueado pelo próprio lease órfão. | Correção do ciclo de vida do lease celular | Executor expõe liberação explícita; CLI libera em `finally`; teste regressivo aprovado em 2026-08-24. |
| `HARNESS-001` | `DONE` | P1 | Continuação conversacional perde o `application_id` e trata cada mensagem composta como uma nova autorização, fazendo o supervisor devolver ao usuário decisões operacionais que já pertencem ao pipeline. | `2026-08-24-harness-continuity-approvals` | `PipelineIntentStore` persiste a sessão; o supervisor resolve o escopo pela sessão sem ponteiro global; teste regressivo e suíte focada aprovados em 2026-08-24. |
| `HARNESS-002` | `DONE` | P1 | Handoff de storage é apresentado como bloqueio manual ad hoc, sem aprovação idempotente, execução pelo comando oficial e retomada segura do pipeline. | `2026-08-24-harness-continuity-approvals` | Aprovação idempotente por identidade física/owner; `authorize-handoff` oficial executado sob lock; aprovação consumida e retomada testada em 2026-08-24, sem edição manual de autoridade. |
| `HARNESS-003` | `DONE` | P1 | Falha do pre-LLM hook fazia o Hermes continuar a rodada sem o HarnessSupervisor, permitindo que o agente tentasse contornar gates depois de erros de infraestrutura. | Correção de identidade cross-container | Hook converte exceções em bloqueio estruturado e encerra com sucesso controlado; execução manual fora do supervisor não é liberada por erro do hook. |
| `HARNESS-004` | `DONE` | P0 | O runtime do bot ignorava `CAREER_HERMES_PROFILE_ID` em `src/`, calculando um perfil diferente do configurado no container e prejudicando a resolução da sessão/candidatura. | `2026-08-25-vagas-bot-02-stabilization` | `profile_id_from_env()` prioriza o ID explícito; smoke no bot 02 retornou `bcc27ffe51db`; testes de continuidade passaram. |
| `HARNESS-005` | `DONE` | P0 | Mensagens compostas como CV + OneDrive + Notion eram classificadas pela primeira intenção encontrada, e pedidos com `application_id` podiam ser desviados para coleta de Notion ID. | `2026-08-25-vagas-bot-02-stabilization` | Dispatcher produz intenção `pipeline` ordenada; execução scoped usa o mesmo `application_id`; testes de dispatch e canário passaram. |
| `HARNESS-006` | `DONE` | P0 | Respostas curtas como “sim” não eram correlacionadas à pergunta emitida; `pending_input` antigo interceptava a conversa e o fallback Hermes recebia uma mensagem sem histórico. | `2026-08-25-vagas-bot-02-stabilization` | Pendências carregam sessão/candidatura/turno/expiração; “sim”/“não” são resolvidos deterministicamente; pendência legada não intercepta; testes passaram. |
| `HARNESS-007` | `DONE` | P0 | O fallback genérico podia afirmar entrega ou escolher arquivos de outra candidatura a partir de `outputs/`, reports globais ou bindings antigos. | `2026-08-25-vagas-bot-02-stabilization` | Status de entrega exige `application_id` e consulta somente `deliveries` scoped; ausência de receipt bloqueia; teste C&A/Jobgether passou. |
| `HARNESS-008` | `DONE` | P0 | `pending_input.json` legado ou de uma sessão anterior sequestrava uma nova entrada de vaga e fazia o bot perguntar o ID do Notion, inclusive para vagas salvas do LinkedIn. | `2026-08-25-vagas-bot-02-stabilization` | Pendências sem sessão são descartadas; pendências de outra sessão/candidatura não bloqueiam a nova intenção; regressão de `lista de vagas salvas no linkedin` passou no supervisor e no container. |
| `HARNESS-009` | `DONE` | P0 | Seleção natural de vaga salva (`analise a vaga 2`) não era reconhecida como seleção de menu; o número caía no parser de Notion e o agente entrava em loop livre após erro de escopo. | `2026-08-26-vagas-bot-02-loop-containment` | Seleção por frase resolve a URL LinkedIn; o perfil do bot 02 interrompe falhas repetidas; canário no container e testes regressivos passam sem alterar o bot 01. Evidências: 24 testes focados, `validate:structure`, `runtime:verify -- --strict`, smoke no container e restart do bot 02 em 2026-08-26. |
| `HARNESS-010` | `DONE` | P0 | A seleção de vaga salva no `vagas_bot_01` resolvia a URL, mas recriava o intake sem reutilizar a candidatura canônica; a repetição terminava em colisão de alias. | `2026-08-27-vagas-bot-01-flow-repair` | Alias LinkedIn resolvido no SQLite e `application_id` existente repassado ao intake; 4 testes de regressão, suíte focada de 28 testes, smoke real do bot01 e validações estrutural/runtime aprovados em 2026-08-27. |
| `HARNESS-011` | `DONE` | P0 | Uma retomada longa com `application_id` e `run_id` explícitos podia ser classificada como vaga colada por não usar a frase exata do menu; o bot02 bloqueava no intake antes de tocar o run celular. | Correção de precedência de retomada celular | IDs explícitos agora têm precedência sobre o detector de texto longo, o nó `compose_cv` é reconhecido com segurança e a retomada chama o comando oficial no mesmo run; 13 testes de harness e 28 testes focados passaram em 2026-08-27. |
| `HARNESS-012` | `DONE` | P0 | A retomada podia reconhecer os IDs, mas perder o nó quando a instrução usava linguagem natural, como `repare primeiro o normalize_job`; sem `repair_node`, o harness executava apenas `applications:run`. | Extração tolerante do nó de reparo celular | Parser aceita verbos de correção e artigos/adverbios intermediários, encaminhando `normalize_job` para `applications:repair`; teste regressivo adicionado em 2026-08-27. |
| `HARNESS-013` | `DONE` | P0 | O vínculo de sessão ainda dependia do mirror JSON em parte do supervisor; após reinício, o bot podia perder a candidatura e pedir o `application_id` interno. | `2026-08-28-safe-session-and-canonical-maintenance` | `register_session`/`resolve_session` usam `session_memory` SQLite como fonte primária e mantêm JSON somente como espelho; `tests/test_runtime_repairs.py::test_session_binding_survives_without_json_registry` passou em 2026-08-28. |
| `HARNESS-014` | `DONE` | P0 | A intenção “pesquise duplicidade no Notion antes de escrever” e a continuação `processe-a-vaga` podiam cair no assistente genérico; uma execução sem estágio também podia ser reportada como concluída. | `2026-08-28-safe-session-and-canonical-maintenance` | Rotas `notion_preflight` e `pipeline` determinísticas, continuação recuperada pelo vínculo/intenção SQLite e zero estágio retorna `blocked`; quatro testes de regressão passaram e o route smoke foi executado em 2026-08-28. |
| `MAINT-001` | `DONE` | P1 | A manutenção do código canônico era tratada como proibida, embora o agente pudesse corrigir uma causa comprovada sem tocar artefatos de candidatura. | `2026-08-28-safe-session-and-canonical-maintenance` | `maintenance:request` cria allowlist revisável; `maintenance:apply` exige dry-run, rejeita paths fora de `src/`, `.agents/skills/` e `hermes-src/`, e aplica somente com `--apply`; dois testes e smoke CLI passaram em 2026-08-28. |
| `HARNESS-015` | `IN_PROGRESS` | P0 | O timeout de 300s do pre-LLM hook era descartado e deixava o Hermes seguir sem supervisão. | `2026-08-28-safe-session-and-canonical-maintenance` | Timeout produz diretiva `block` e o prólogo interrompe antes do LLM; falta validar o comportamento integrado no container e a resposta visível ao usuário. |
| `CELLULAR-003` | `DONE` | P0 | Após reparar `normalize_job`, `applications:run` podia reservar e consumir `analyze_fit` sem draft/binding externo, criando bloqueio artificial antes da intervenção do agente. | Não consumir tentativa de `analyze_fit` sem draft preparado | `run_ready` mantém `analyze_fit` em `planned` até os dois arquivos externos existirem; teste de reparo da normalização confirma tentativa não consumida em 2026-08-27. |
| `CELLULAR-004` | `DONE` | P1 | A reconciliação canônica registrava nós auxiliares de gates em `cell_nodes` usando o mesmo `run_id` dos nós executáveis, fazendo `resume`/`inspect-run` rejeitar um run já concluído por diferença exata de conjuntos. | `2026-08-27-cellular-reconciliation-run-projection` | `resume` preserva a detecção de nós do plano ausentes e ignora somente nós auxiliares fora do plano; teste regressivo passou e o `inspect-run` do Modaxo voltou a reconhecer o run concluído em 2026-08-27. |
| `RUNTIME-011` | `DONE` | P0 | A atualização do espelho `application_alias_index.json` podia lançar `PermissionError` depois da persistência canônica e interromper o agente. | `2026-08-27-vagas-bot-01-flow-repair` | Mirror tolerante a `OSError`; estado do bot01 corrigido para UID/GID 10000 com alias index `0600`; prova de escrita UID 10000 e smoke real aprovados em 2026-08-27. |
| `RUNTIME-012` | `DONE` | P0 | O heartbeat celular ignorava `CAREER_CONTROL_DB_PATH` e abria `V2_DIR.parent / "career.db"`, apontando para o SQLite legado mesmo quando o runtime estava configurado para `.career-control/career.db`. Toda nova execução celular podia falhar no mismatch de identidade antes de processar a vaga. | `2026-08-27-cellular-heartbeat-canonical-db` | `_run_cellular_heartbeat` usa `canonical_database().db_path`; teste com banco legado distinto passou, 90 testes focados, `validate:structure`, `runtime:verify -- --strict` e canário real do bot01 passaram. O canário criou o run e avançou `normalize_job` sem mismatch. |
| `RUNTIME-010` | `DONE` | P0 | Os testes focados estavam verdes, mas não existia canário de jornada que cobrisse pipeline composto, confirmação curta e status sem troca de candidatura. | `2026-08-25-vagas-bot-02-stabilization` | Canário descartável passou duas vezes consecutivas; `validate:structure`, `runtime:verify -- --strict` e smoke do bot 02 passaram. |
| `CV-001` | `DONE` | P1 | O renderer canônico colocava cargo, empresa e período no mesmo parágrafo, prejudicando a leitura do CV. | Correção do renderer e testes de DOCX | `test_renderer_separates_period_and_bolds_key_result_metrics`, `validate_docx` e renderização de smoke aprovados em 2026-08-21. |
| `CV-002` | `DONE` | P1 | O renderer descartava rich text dos bullets e não destacava resultados-chave no DOCX. | Correção do renderer e testes de DOCX | Runs explícitos preservados e métricas destacadas; `tests/test_custom_cv_generation.py` passou 10/10 em 2026-08-21. |
| `CV-003` | `DONE` | P1 | `review_output.py` tinha dependência quebrada (`sha256_file`) e o gate CLI podia ser gravado sem `revision_id`, incentivando workarounds indevidos. | Correção dos gates e do reviewer | `sha256_file` canônico, reviewer de formatação e resolução automática da revisão atual; 42 testes focados passaram em 2026-08-21. |
| `CV-004` | `DONE` | P1 | `cv:deliver` não recebia nem repassava `--application-id` e ainda apontava para FIT_MAP, registry e reports globais. | Correção do wrapper de aprovação/entrega | Wrapper exige escopo explícito, usa paths da candidatura, repassa o ID ao `cv approve` e os testes `tests/test_cv_delivery_scope.py` passaram em 2026-08-22. |
| `CV-005` | `DONE` | P1 | O seletor promovia `trifil_expedicao` por uma lista fixa de fallback, mesmo quando outra experiência era mais aderente ou mais recente para a vaga. | Correção da seleção de experiências | Candidatos restantes são ranqueados por keywords de foco, com recência e fallback fixo apenas como desempates; testes de CX/Trifil passaram em 2026-08-22. |
| `CV-006` | `DONE` | P1 | O renderer emitia travessão em cargo/empresa, períodos e formação, e o reviewer não verificava a convenção de pontuação solicitada. | Normalização de pontuação do DOCX | Renderer, reviewer e testes aprovados com `Cargo | Empresa`, período com `a` em português ou `to` em inglês, formação com `:` e nenhum travessão residual. Evidências: 64 testes focados, `npm run validate:structure` e `npm run runtime:verify -- --strict` aprovados em 2026-08-22. |
| `CV-007` | `DONE` | P1 | O reviewer celular inferia PT-BR pelo nome temporário `cv.docx`, bloqueando keywords inglesas em CVs cujo FIT_MAP declarava `idioma=en`. | `2026-08-26-cellular-cv-repair` | Polish e revisão objetiva recebem o idioma declarado; `tests/test_review_language.py` e 7 testes direcionados passaram; as duas revisões celulares aprovaram. |
| `CV-008` | `DONE` | P1 | A materialização inglesa descartava o vínculo entre keywords ATS do FIT_MAP e as experiências, reduzindo o top8 apesar de evidência defensável. | `2026-08-26-cellular-cv-repair` | Materialização e proveniência usam as mesmas cláusulas controladas; as duas revisões celulares aprovaram ATS top8 8,0/8 e zero `missing_unexplained`. |
| `DELIVERY-001` | `DONE` | P0 | Os containers dos bots não possuíam `RCLONE_ONEDRIVE_REMOTE` e `RCLONE_ONEDRIVE_DELIVERY_DIR`; o upload OneDrive não podia ser comprovado. | `2026-08-26-cellular-cv-repair` | Variáveis configuradas nos dois containers; `rclone lsd` e os dois receipts `delivery_report.json` confirmaram `status=delivered` em 2026-08-26. |
| `CELLULAR-001` | `DONE` | P0 | Runs celulares concluídos não eram projetados nas tabelas SQLite de FIT_MAP, artefato, delivery e Notion; `core_package_sealed` permanecia invisível. | `2026-08-26-cellular-cv-repair` | Ponte persistente `src/career/services/cellular_persistence.py` criada e testada; Jobgether e Change.org reconciliados, `applications:resolve` retornou `core_package_sealed`. |
| `CV-009` | `DONE` | P0 | O idioma da vaga era detectado por implementações conflitantes: o intake identificava a vaga Modaxo como `en`, enquanto o contexto derivado a identificava como `pt-BR`; o CV e o review acabavam usando fontes diferentes. | `2026-08-27-cellular-cv-language-and-repair-hardening` | Detector canônico em `src/career/services/job_language.py`; intake e contexto derivado compartilham a decisão, `compose_cv` consome o `job_normalized.json` validado e `review_cv` consome o idioma do `cv_content.json`. O contrato inclui `normalize_job` e runs antigos recebem a dependência retroativamente; fixture mista, pipeline celular paralelo, 54 testes focados, `validate:structure` e `runtime:verify -- --strict` passaram em 2026-08-27. |
| `CV-010` | `DONE` | P1 | `cv_content.json` marcava keywords como `exact` apenas porque encontrou a experiência-alvo, mesmo quando o texto materializado não continha a keyword; isso divergira do gate objetivo do DOCX e mascarava gaps de evidência. | `2026-08-27-cellular-cv-language-and-repair-hardening` | `ats_keyword_coverage` agora compara o texto materializado e classifica `exact`, `similar`, `declared_gap` apenas quando declarado no FIT_MAP, ou `missing_unexplained`; contrato e instruções foram alinhados ao reviewer. A materialização inglesa ganhou cláusulas controladas para as sete keywords operacionais do Jobgether e as seis keywords de IA do Modaxo, com testes de evidência e sem converter gross margin em sinônimo literal de contribution margin. Suíte focada atualizada em 2026-08-27. |
| `CV-011` | `DONE` | P1 | O caminho PT-BR de `_build_summary` injetava `fit_map.dor_central` no resumo do candidato quando havia `positioning`, misturando problema da vaga com experiência pessoal. | `2026-08-27-cellular-cv-language-and-repair-hardening` | O resumo usa perfil, fatos e fragmentos canônicos do candidato; `dor_central` só orienta o posicionamento. Teste regressivo com dor exclusiva da vaga passou, junto da suíte focada em 2026-08-27. |
| `CELLULAR-002` | `DONE` | P1 | `applications:repair` criava uma nova reserva celular e retornava sem executar ou cancelar a tentativa; se a etapa seguinte falhava, o nó podia permanecer reservado até o TTL e bloquear reparos descendentes. | `2026-08-27-cellular-cv-language-and-repair-hardening` | `repair_and_run` executa e finaliza o reparo, ou faz `defer/cancel` em falha; `analyze_fit` devolve a tentativa a `planned` até existir draft/binding externo. Testes de falha, defer e CLI passaram; o pipeline celular paralelo também passou sem leases órfãos em 2026-08-27. |
| `CELLULAR-005` | `DONE` | P0 | A execução explícita de uma run celular pelo bot apenas reportava `ready_nodes` e não disparava o agente externo; além disso, o heartbeat só selecionava a fila do Notion e ignorava runs locais já planejadas. | `2026-08-27-cellular-explicit-run-and-notion-identity` | `applications:run --run-agent` e a retomada do harness processam a run local no mesmo `application_id`/`run_id`; o teste de descoberta local passou, o canário real do bot01 chegou ao agente e encerrou sem lease órfão. O canário ficou bloqueado somente pela credencial ausente do `ollama-cloud`. Evidência: 90 testes focados, `validate:structure`, `runtime:verify -- --strict` e `doctor-concurrency` verdes em 2026-08-27. |
| `NOTION-001` | `DONE` | P1 | Uma candidatura local sem página Notion podia persistir o próprio `application_id` como `notion_page_id`, fazendo o sync inicial chamar update com um ID inválido em vez de criar a página. | `2026-08-27-cellular-explicit-run-and-notion-identity` | Só UUID de página ou `record_id` numérico é alvo de update; aliases locais/sintéticos são ignorados, o sync inicial do Jobgether criou a página `3c90003f-9481-817c-979d-e0f5a6018bbd` e o receipt foi validado. Testes de identidade/sync passaram em 2026-08-27. |
| `CV-012` | `DONE` | P1 | A materialização inglesa cobria apenas um subconjunto fixo de keywords ATS; uma FIT_MAP de planejamento/S&OP com evidência canônica legítima continuava gerando CV com gaps artificiais no texto. | `2026-08-27-cellular-explicit-run-and-notion-identity` | Cláusulas inglesas foram adicionadas somente para conceitos suportados pelas fontes canônicas, a ordem cronológica passou a usar o fim real do período e o CV regenerado chegou a ATS 7,0/8, mantendo apenas `SIOP` como gap honesto. Evidência: 23 testes de CV e review celular em 2026-08-27. |
| `CELLULAR-006` | `DONE` | P0 | O gateway Telegram seleciona o perfil `vagas_bot_01`/`vagas_bot_02` e carrega seu `.env`, mas o subprocesso celular Hermes era iniciado sem `--profile`; ele caía no `HERMES_HOME` raiz, onde não existe `.env`, e falhava como se a credencial do provedor estivesse ausente. | `2026-08-28-cellular-profile-env` | `SubprocessAgentRunner` agora encaminha o perfil explícito, com fallback em `CAREER_HERMES_PROFILE_NAME`; os dois compose declaram `vagas_bot_01`/`vagas_bot_02`. A entrada de `OLLAMA_API_KEY` permanece apenas no `.env` dos perfis. 26 testes focados, `validate:structure` e `git diff --check` passaram em 2026-08-28. |
| `CELLULAR-007` | `DONE` | P1 | A reconciliação do pacote-base comparava o registry celular com o cargo bruto do intake, que podia conter localização e tipo de contrato, e ainda gravava o idioma como `en` por default, mesmo para uma vaga PT-BR. | `2026-08-28-portuguese-ats-materialization` | `registry_entry_matches_application` prioriza `application_id` e usa o cargo do FIT_MAP como fallback; `reconciliation_cv_language` detecta o idioma da descrição persistida. Testes regressivos passaram e o Tempo foi reconciliado como `core_package_sealed`, com `cv_language=pt-BR`, em 2026-08-28. |
| `CV-013` | `DONE` | P1 | O reviewer tratava `SIOP` como keyword ausente mesmo quando o CV continha `S&OP` e havia evidência canônica de inventário, capacidade e planejamento de manufatura. | `2026-08-28-siop-ats-equivalence` | Registry curado reconhece `S&OP` como equivalente de `SIOP` somente sob essa condição de evidência; `SIOP` não é inserido artificialmente no texto. Teste RED/GREEN, validação JSON e suíte focada passaram em 2026-08-28. |
| `CV-014` | `DONE` | P1 | A nova seleção de keywords para planejamento/S&OP elevou `supply chain` ao top8, mas a materialização inglesa ainda não possuía cláusula controlada para essa evidência canônica. | `2026-08-28-supply-chain-ats-materialization` | Cláusula inglesa adicionada somente com evidência de demanda, inventário, materiais e manufatura; teste RED/GREEN aprovado. A run Jobgether foi regenerada, review aprovado (`approved_for_delivery=true`, ATS top8 7,8/8, zero `missing_unexplained`) e CV entregue. |
| `CV-015` | `DONE` | P1 | A materialização PT-BR ainda não possuía cláusulas controladas para keywords sustentadas pelo FIT_MAP; as runs Tempo/Vivo chegaram ao `review_cv` com score ATS top8 insuficiente apesar de evidência canônica. | `2026-08-28-portuguese-ats-materialization` | Cláusulas PT-BR curadas para as keywords suportadas, teste RED/GREEN, CV regenerado por run celular e `review_cv` aprovado sem `missing_unexplained`; Tempo (`run_5d3a95f1b9074ea9844198db4c51fdc8`) terminou com ATS top8 `8,0/8`, entrega OneDrive, página Notion e `core_package_sealed`. Keywords sem evidência continuam como gap. |
| `CV-016` | `DONE` | P1 | O gerador mistura mecanismo/caso e resultado quantitativo no bullet 2; em algumas experiências o mesmo resultado aparece novamente no bullet 3, e cláusulas ATS com números são anexadas ao bullet errado. | `2026-08-28-cv-bullet-role-separation` | Em modo `concise`, bullet 2 contém somente posicionamento/mecanismo/caso coerente com a experiência e as keywords-alvo, sem métrica de resultado; bullet 3 contém o resultado quantitativo canônico; o contrato rejeita bullet 2 quantitativo, bullet 3 sem métrica ou duplicação literal. `_materialize_experience` foi testado nas 8 experiências em PT-BR/EN; suítes focadas passaram 45/45, além de `validate:structure`, `runtime:verify -- --strict` e `git diff --check`, em 2026-08-28. |
| `CV-017` | `DONE` | P1 | A fonte canônica classificava `budget de R$300MM/ano` simultaneamente como responsabilidade no bullet 1 e resultado no bullet 3; o contrato conciso não detectava repetição quantitativa entre esses bullets. | `2026-08-28-cv-result-claim-deduplication` | Budget permanece somente no bullet 1; o resultado do bullet 3 contém as métricas de cobertura/indisponibilidade/agrupamento; validador B1/B3 passou; CV v2 aprovado e entregue no OneDrive na run `run_bdc2377ca46a447595a6c500a21f0c23`. |
| `CV-018` | `DONE` | P1 | O gerador PT-BR não materializava sete keywords de atendimento sustentadas pelo FIT_MAP, porque o catálogo de cláusulas cobria apenas termos genéricos de Customer Experience e Zendesk. | `2026-08-28-cv-result-claim-deduplication` | Cláusulas controladas foram adicionadas para as sete keywords com evidência canônica; teste regressivo passou; `review_cv` final aprovou ATS top8 `8,0/8`, zero `missing_unexplained` e zero blockers. |
| `CV-019` | `DONE` | P1 | O seletor de experiências acrescentava um fallback mesmo quando o FIT_MAP já havia selecionado experiências suficientes, o matcher confundia cargos diferentes da mesma empresa e o resumo usava prioridades globais em vez das experiências-alvo da vaga; na Vivo isso inseriu `Gerente de Customer Success` e deixou o foco de MIS sem materialização suficiente. | `2026-08-28-cv-target-coherence` | Fallback agora só completa até o mínimo contratual com experiência relevante; o matcher respeita empresa e cargo; o resumo prioriza experiências com maior cobertura das keywords top8; variantes MIS sustentadas são materializadas somente nas experiências-alvo. A run final `run_84637545b10946f29c463bbadcb4d2fc` gerou CV sem `renault_cs`, com `trifil_inteligencia_comercial`, `review_cv` aprovado, ATS top8 `8,0/8`, zero `missing_unexplained` e zero blockers. Evidência adicional: 82 testes, `validate:structure`, `runtime:verify -- --strict`, `git diff --check` e entrega OneDrive confirmada (`status=delivered`, receipt `1fe179fbaca4`). |
| `CV-020` | `DONE` | P1 | `_summary_support_pairs` acessava diretamente `summary_fragments[experience_id]`; quando o FIT_MAP selecionava uma experiência válida sem fragmento de resumo, como `trifil_expedicao`, `cv:build-content` falhava com `KeyError`. | Manutenção canônica `maintenance_549ac7c360ce` | A função usa `.get()` e ignora a experiência sem fragmento, preservando a exigência de duas experiências suportadas; teste de regressão reproduziu o `KeyError` e passou após a correção. Suíte focada de CV: 53 testes aprovados em 2026-08-29. |
| `POSITION-001` | `BACKLOG` | P0 | A base estruturada do candidato não representa de forma completa e rastreável as histórias úteis do `autoconhecimento.md`; `candidate_cv_facts.json` continua sendo uma projeção limitada para o CV. | `2026-08-29-positioning-evidence-pipeline` | Base de evidências versionada, com `story_id`, claims permitidos, métricas e referências de origem; uma história nova passa a aparecer nos packs aplicáveis sem edição manual de artefatos. |
| `POSITION-002` | `BACKLOG` | P0 | FIT_MAP, CV, FERAS, carta, habilidades e respostas não compartilham ainda um contrato único para traduzir a mesma estratégia de reposicionamento por formato. | `2026-08-29-positioning-evidence-pipeline` | Um `positioning pack` scoped é materializado a partir da revisão de posicionamento e consumido por todos os artefatos; cada saída registra as histórias/claims utilizados. |
| `POSITION-003` | `BACKLOG` | P1 | Não existe gate que detecte estratégia selecionada mas não traduzida em artefato, nem invalidação explícita de derivados quando a base de evidências muda. | `2026-08-29-positioning-evidence-pipeline` | Cobertura estratégica e dependência da revisão de evidências são validadas antes da aprovação; alterações de fonte tornam derivados incompatíveis e exigem regeneração. O Notion recebe apenas o snapshot final pelos campos já existentes. |
| `CELLULAR-010` | `BLOCKED` | P0 | A candidatura Sonova/Record 619 tem `fit_map.json` sem o bloco obrigatório de `provenance`; o código atual bloqueia antes de `cv:build-content`, independentemente do `KeyError` corrigido. | Recuperação oficial da candidatura Sonova | Regenerar ou recuperar o FIT_MAP pelo fluxo oficial com o mesmo `application_id`, fingerprint e evidências; não inserir provenance manualmente nem alterar o artefato para contornar o gate. |
| `CELLULAR-008` | `DONE` | P1 | O reparo de `analyze_fit` podia executar o draft/binding da tentativa anterior antes de o agente regenerar o draft, produzindo `attempt_mismatch` e consumindo uma tentativa de reparo. | `2026-08-28-cv-result-claim-deduplication` | Reparo de `analyze_fit` sempre devolve a tentativa para `planned`; o agente gera e vincula uma nova tentativa; teste de binding stale passou; a run final não deixou lease ativo ou nó bloqueado. |
| `CELLULAR-009` | `DONE` | P0 | A rota celular bloqueava em `review_cv` por baixa cobertura ATS sem gerar o repair request nem acionar a adaptação defensável do `cv_content.json`; o retry atual apenas revisava o mesmo artefato. | `2026-08-29-cellular-review-repair` | `run_b750a8f962a8428a99b6611f347dbd76` chegou ao bloqueio real e criou handoff scoped; a validação rejeitou o candidato sem proveniência e impediu entrega. `run_c3a26b408d264e278eceaee094820929` concluiu o DAG com CV 7,8/8, OneDrive entregue, Notion final sincronizado e SQLite `core_package_sealed`; `review_output.py` independente passou 12/12 blockers. |
| `RUNTIME-013` | `DONE` | P1 | Os perfis carregavam cópias locais obsoletas de skills com mais de 100.000 caracteres; o bot 02 truncava `AGENTS.md` em 70.000 e ambos traziam um `tirith` ARM64 em containers x86_64. Também faltava uma precedência explícita entre skills do projeto, globais e locais, permitindo resolução ambígua e loops de `skill_manage`. | `2026-08-28-runtime-skill-precedence` | Os quatro arquivos efetivos de configuração declaram `max_turns: 150`, `context_file_max_chars: 80000`, `project_dirs: [/workspace/candidaturas/.agents/skills]` e `source_precedence: [project, global, profile]`; o resolver compartilhado aplica a ordem em prompt, listagem, view, manager, gateway e comandos, e bloqueia colisão projeto/profile. As seis cópias legadas confirmadas foram removidas, `tirith_enabled=false` permanece nos dois runtimes, os containers foram recriados com UID Hermes 10000 e os guards de colisão passaram nos dois. Evidência: 459 testes Hermes, 13 testes do projeto, `validate:structure`, `runtime:verify -- --strict`, `git diff --check`, smoke de resolução e logs recentes sem erros de truncamento, permissão ou arquitetura. |
| `RUNTIME-014` | `DONE` | P1 | O script de reconciliação celular usava por default o `control-plane/career.db` do workspace, que é read-only dentro dos containers, ignorando `CAREER_CONTROL_DB_PATH` e recriando o bloqueio de permissão/abertura do banco. | `2026-08-28-portuguese-ats-materialization` | `scripts/reconcile_cellular_run.py` usa `Database()` quando `--db` não é informado e mantém override explícito quando informado; teste regressivo passou e a reconciliação Tempo foi executada sem `--db`, retornando `core_package_sealed`. |

## Plano de correção — idioma, ATS, resumo e reparo celular

Plano: `2026-08-27-cellular-cv-language-and-repair-hardening` — concluído em
2026-08-27.

Objetivo: garantir que uma candidatura celular use uma única decisão de idioma,
que a cobertura ATS publicada reflita o texto real do CV, que o resumo nunca
confunda a vaga com o candidato e que uma falha de reparo não deixe leases
órfãos.

Escopo confirmado pela execução Modaxo no `vagas_bot_02` (`run_62621fc435554290be1fbe127968c29b`):

- `CV-009`: unificar a detecção e a propagação de idioma. A decisão deve nascer
  no intake/normalização e ser preservada no pacote da aplicação. Remover a
  competição entre `applications_v2.detect_job_language` e
  `derived_context._infer_language`; `cv_content` e `review_cv` não devem
  voltar a inferir idioma pelo nome temporário do DOCX ou por um FIT_MAP sem
  `idioma`.
- `CV-010`: alinhar proveniência e gate ATS. Revisar
  `cv_content._build_ats_coverage` para não chamar uma associação de
  experiência de cobertura `exact`; materializar apenas frases autorizadas por
  evidência e classificar gaps honestamente. O teste deve comparar a cobertura
  do JSON com o texto extraído do DOCX final.
- `CV-011`: corrigir `_build_summary`. `dor_central` permanece disponível para
  seleção de posicionamento, mas não pode ser interpolada no resumo como foco
  autobiográfico. O teste deve provar que uma dor exclusiva da vaga não entra
  no resumo e que os anchors continuam suportados por experiências.
- `CELLULAR-002`: tornar o reparo transacional do ponto de vista operacional.
  O comando que reserva uma tentativa deve executar a etapa ou devolver a
  tentativa a `planned`/`cancelled` quando a execução não começa ou falha.
  Expiração deve ser reconciliada antes de bloquear reparos descendentes;
  nenhuma correção manual em `career.db` será aceita.

Sequência de implementação e validação:

1. Criar testes regressivos para o texto Modaxo com cabeçalho em português e
   corpo em inglês, para o resumo com `positioning`, para cobertura ATS falsa e
   para falha entre `repair` e `run`.
2. Implementar a fonte única de idioma e atualizar os consumidores celulares;
   validar `job_extract`, `cv_content`, nome do DOCX e review no mesmo idioma.
3. Corrigir a semântica de cobertura ATS e ajustar o mapeamento de keywords para
   distinguir evidência, equivalente traduzido e gap declarado.
4. Corrigir o resumo e executar os gates de proveniência/qualidade do CV.
5. Corrigir o ciclo de vida do reparo, executar o cenário de lease órfão e
   validar que `applications:resume`/`applications:run` retomam o mesmo
   `run_id` sem intervenção no banco.
6. Rodar a suíte focada, `npm run validate:structure`,
   `npm run runtime:verify -- --strict` e um canário real de cada bot; depois
   reprocessar a execução Modaxo somente pelo fluxo celular oficial.

Restrições de execução:

- Não tornar `src/` gravável dentro dos containers; ele é código montado em
  somente leitura. Correções de código são feitas no host e entram no processo
  após reinício controlado.
- Não editar `cv_content.json`, DOCX validado, manifests celulares ou SQLite
  manualmente para contornar hash, review ou lease.
- Não relaxar `ats_top8_minimum_score` nem
  `ats_top8_no_missing_unexplained`; keywords sem evidência devem permanecer
  declaradas como gap.
- A execução precisa manter `application_id` e `run_id` explícitos, com os
  mesmos paths e artefatos imutáveis por candidatura.

Critério global de aceite: uma execução celular em inglês com metadados
auxiliares em português produz CV inglês consistente, cobertura ATS honesta,
resumo factual, review objetivo e nenhum lease ativo ou tentativa reservada
órfã após falha de reparo. O estágio só poderá ser marcado `DONE` com comandos,
testes e artefatos dessa prova registrados aqui.

## Backlog inicial pós-Fase 8 — 8 falhas da suíte ampla

Esses itens foram identificados na execução de `PYTHONPATH=src .venv/bin/pytest
-q tests`: 485 testes passaram e 8 falharam. Os 41 testes focados da Fase 8
passaram; portanto, estes itens não bloqueiam o cutover operacional, mas devem
ser resolvidos ou formalmente superseded para que a suíte ampla volte a ficar
verde.

| ID | Estado | Esforço | Falha | Critério de saída |
|---|---|---:|---|---|
| `TEST-001` | `DONE` | Alto | Dois pipelines de CV em paralelo terminam bloqueados no teste de isolamento entre candidaturas. | `2026-08-25-critical-roadmap-fixes` | Execução concorrente passou em 2026-08-25, mantendo artefatos, manifests, hashes, idioma e reviews separados por `application_id`. |
| `TEST-002` | `DONE` | Baixo | `harness_supervisor.py` documentava `register_keywords.py` sem `--translation-registry`. | Comando documentado com o registry; `test_mandatory_keyword_registration_documentation_names_translation_registry` aprovado em 2026-08-21. |
| `TEST-003` | `DONE` | Médio | Provisionamento não atualiza uma base pré-ledger com a coluna `authority_ledger_id` ausente. | `2026-08-24-harness-continuity-approvals` | Fixture de banco legado migrada e provisionada sem erro; teste de schema e ledger aprovado em 2026-08-24. |
| `TEST-004` | `DONE` | Trivial | Painel celular não contém o marcador atual “Fatia E em revalidação”. | Painel atualizado com o marcador e a revalidação do supervisor em 2026-08-24. |
| `TEST-005` | `BACKLOG` | Baixo/Médio | Teste de input packs ainda usa adaptadores globais/depreciados sem escopo explícito. | Teste usa `application_id`/`ApplicationPaths` e prova que o FIT_MAP da aplicação vence o JSON global. |
| `TEST-006` | `DONE` | Trivial | Mock de `guard()` não aceitava o parâmetro `database` introduzido no contrato atual. | Mock atualizado; suíte focada de intake/runtime passou em 2026-08-21. |
| `TEST-007` | `BACKLOG` | Baixo | Teste de geração de request tenta mockar `_prepare_compact_inputs_for_step`, função removida/renomeada. | Teste usa a API atual (`_prepare_scoped_compact_inputs`) ou uma compatibilidade deliberada é documentada. |
| `TEST-008` | `BACKLOG` | Médio | Fixture de intake Notion usa banco temporário sem schema/tabelas disponíveis no caminho observado. | Fixture injeta o banco canônico temporário corretamente; a descrição é persistida antes do template. |
| `TEST-009` | `BACKLOG` | Baixo | `test_cell_planner.py::test_cv_and_notion_plan_has_ordered_nodes` ainda espera que `compose_cv` dependa apenas de `analyze_fit`, embora o plano atual também exija `normalize_job`. | Atualizar a expectativa do teste para refletir a dependência canônica de normalização, sem relaxar a ordem do pipeline celular. |

## Registro de planos

| Plano | Escopo | Itens do roadmap | Estado |
|---|---|---|---|
| `2026-08-18-runtime-unification` | Unificação de runtime, SQLite, cutover e canários. | `RUNTIME-OBS-001`; validação dos testes relacionados à Fase 8. | Cutover concluído; observação aberta. |
| `2026-08-21-cv-renderer-and-gates` | Renderer DOCX, reviewer de formatação, hashes e receipts. | `CV-001`, `CV-002`, `CV-003`, `TEST-002`, `TEST-006`. | Concluído; suíte focada verde. Naquele corte, a suíte ampla ainda conservava falhas antigas; `TEST-003` e `TEST-004` foram resolvidos pelo plano de 2026-08-24. |
| `2026-08-24-harness-continuity-approvals` | Continuidade de sessão/intenção, fronteira de aprovação do supervisor, handoff de storage e reparo de schema pré-ledger. | `HARNESS-001`, `HARNESS-002`, `TEST-003`, `TEST-004`; revalidação relacionada a `RUNTIME-006` e `RUNTIME-OBS-001`. | Concluído; 73 testes focados, `validate:structure` e `runtime:verify -- --strict` aprovados em 2026-08-24. `RUNTIME-OBS-001` continua em observação operacional. |
| `2026-08-24-storage-identity-cross-container` | Tornar a identidade de storage estável entre containers que compartilham o mesmo bind mount, impedir bypass no hook, normalizar a autoridade existente e liberar leases de fronteira CLI. | `RUNTIME-008`, `RUNTIME-009`, `HARNESS-003` | Concluído; 81 testes focados, identidades iguais em host/bot1/bot2, handoff oficial autorizado, lease órfão liberado e `assert_authoritative_storage` aprovado nos dois containers em 2026-08-24. |
| `2026-08-25-vagas-bot-02-stabilization` | Contenção e correção da perda de escopo, roteamento composto, confirmações curtas, fallback genérico, pendências órfãs e canário real do bot 02. | `HARNESS-004` a `HARNESS-008`, `RUNTIME-010` | Concluído em 2026-08-25; testes focados, canário, validação estrutural, verifier estrito e prova route-only no container aprovados. A retomada da candidatura C&A foi removida do escopo por decisão do usuário. |
| `2026-08-26-vagas-bot-02-loop-containment` | Corrigir seleção textual de vagas salvas, impedir interpretação indevida como Notion e interromper loops repetidos no perfil do bot 02. | `HARNESS-009` | Concluído em 2026-08-26; bot 01 preservado. |
| `2026-08-27-vagas-bot-01-flow-repair` | Corrigir a reutilização de candidaturas na seleção de vaga salva e isolar falhas de permissão do mirror JSON de aliases no bot 01. | `HARNESS-010`, `RUNTIME-011` | Concluído em 2026-08-27; 28 testes focados, `validate:structure`, `runtime:verify -- --strict`, prova UID 10000 e smoke do bot01 aprovados. O smoke bloqueou somente pela credencial ausente do `ollama-cloud`, após o intake e o request scoped serem produzidos. |
| `2026-08-25-critical-roadmap-fixes` | Isolamento concorrente de CV e alinhamento do provider Hermes ao Ollama Cloud. | `TEST-001`, `RUNTIME-005` | Concluído em 2026-08-25; teste concorrente, teste de configuração dos dois perfis, validação estrutural e verifier estrito aprovados. Smoke Hermes completo ficou limitado por timeout de latência. |
| `2026-08-26-cellular-cv-repair` | Corrigir materialização ATS, idioma declarado e revisão de CV na rota celular; retomar Jobgether e Change.org até entrega externa. | `CV-007`, `CV-008`, `DELIVERY-001`, `CELLULAR-001` | Concluído em 2026-08-26; CVs aprovados, entregas distintas confirmadas no OneDrive, páginas Notion criadas e projeção SQLite reconciliada em `core_package_sealed`. |
| `2026-08-27-cellular-cv-language-and-repair-hardening` | Corrigir a fonte única de idioma, a consistência da cobertura ATS, a separação entre dor da vaga e resumo do candidato e o ciclo de vida de leases durante reparos celulares. | `CV-009`, `CV-010`, `CV-011`, `CELLULAR-002` | Concluído em 2026-08-27; 61 testes focados, `validate:structure` e `runtime:verify -- --strict` aprovados. A suíte ampla de `tests/` teve 544 aprovados e 3 falhas antigas de `IntakePersistenceTests`, fora deste escopo; a coleta da raiz inteira também inclui overlays/backups e dependências incompatíveis. |
| `2026-08-27-cellular-reconciliation-run-projection` | Corrigir a projeção de receipts auxiliares de gates para que a inspeção de runs celulares continue compatível com o plano persistido. | `CELLULAR-004` | Concluído em 2026-08-27; 32 testes focados, `validate:structure`, `runtime:verify -- --strict` e `applications:inspect-run` do Modaxo aprovados. |
| `2026-08-28-safe-session-and-canonical-maintenance` | Recuperar continuidade SQLite, rotear confirmações/duplicidade sem fallback livre, impedir falso “completed”, permitir manutenção canônica allowlisted e conter timeout do pre-LLM hook. | `HARNESS-013`, `HARNESS-014`, `HARNESS-015`, `MAINT-001` | Parcial em 2026-08-28: os três primeiros itens de continuidade/roteamento/manutenção têm testes verdes; `HARNESS-015` aguarda smoke integrado no container. |
| `2026-08-27-cellular-heartbeat-canonical-db` | Corrigir a seleção do banco de controle no heartbeat celular e impedir que um banco legado seja tratado como autoridade. | `RUNTIME-012` | Concluído em 2026-08-27; plano salvo antes da alteração, teste RED/GREEN, 90 testes focados, validações estruturais/runtime e canário bot01 com run celular criado e `normalize_job` validado. |
| `2026-08-27-cellular-explicit-run-and-notion-identity` | Corrigir a diferença entre “run pronta” e execução do agente externo, permitir retomada de runs locais fora da fila Notion, impedir que IDs locais sejam usados como páginas Notion e completar a materialização ATS evidenciada para planejamento/S&OP. | `CELLULAR-005`, `NOTION-001`, `CV-012` | Concluído em 2026-08-27; os casos correntes permanecem bloqueados apenas por dependências honestas: credencial `ollama-cloud` no bot01 e gap `SIOP` no FIT_MAP do bot02. |
| `2026-08-28-cellular-profile-env` | Corrigir o desvio entre o perfil carregado pelo gateway Telegram e o perfil carregado pelo subprocesso Hermes de `analyze_fit`, preservando credenciais somente no `.env` do perfil. | `CELLULAR-006` | Concluído em 2026-08-28; teste regressivo, validação estrutural e diff limpo. O canário celular seguinte deve ser executado com a mesma run para confirmar o alcance do provedor. |
| `2026-08-28-siop-ats-equivalence` | Corrigir o falso gap ATS de `SIOP` quando `S&OP` cobre o conceito com evidência de inventário, capacidade ou manufatura, preservando a redação factual do CV. | `CV-013` | Concluído em 2026-08-28; entrada curada no registry, teste RED/GREEN e validação JSON aprovados. A candidatura Jobgether foi regenerada em nova run, aprovada e reconciliada; o esgotamento da run anterior não impede a conclusão do caso. |
| `2026-08-28-supply-chain-ats-materialization` | Materializar `supply chain` no CV inglês quando a FIT_MAP aponta a keyword e há evidência canônica de demanda, inventário, materiais e manufatura. | `CV-014` | Concluído em 2026-08-28; teste RED/GREEN, review final com `approved_for_delivery=true`, ATS top8 7,8/8, zero `missing_unexplained`, entrega e reconciliação Jobgether confirmados. |
| `2026-08-28-portuguese-ats-materialization` | Materializar keywords ATS em português somente quando a FIT_MAP e as fontes canônicas sustentarem a redação; regenerar e revisar a run Tempo do bot 02. | `CV-015`, `CELLULAR-007`, `RUNTIME-014` | Concluído em 2026-08-28; teste RED/GREEN, regeneração celular, review ATS `8,0/8`, entrega OneDrive, criação da página Notion, correções de associação/idioma, default de DB canônico e reconciliação `core_package_sealed` confirmados. |
| `2026-08-28-bot02-profile-context-hardening` | Alinhar os perfis dos bots à skill canônica, eliminar truncamento do contexto e neutralizar o binário `tirith` de arquitetura incompatível. | `RUNTIME-013` | Concluído em 2026-08-28; exclusão definitiva da cópia antiga do bot 02, parâmetros comuns `150/80000`, discovery canônica nos dois perfis, containers recriados, smoke de logs e 10 testes de configuração/dispatch aprovados. |
| `2026-08-28-runtime-skill-precedence` | Definir e executar a precedência `project > global > profile` para skills do Hermes, impedir colisão entre skills canônicas e locais e remover as duplicatas de carreira confirmadas nos dois bots. | `RUNTIME-013` | Concluído em 2026-08-28; quatro configurações alinhadas, resolver/guards migrados para todos os caminhos de descoberta, seis pacotes legados removidos, containers recriados, 459 testes Hermes + 13 testes do projeto e validações estruturais/runtime aprovados. |
| `2026-08-28-cv-result-claim-deduplication` | Separar responsabilidade, posicionamento/mecanismo e resultado quantitativo; corrigir cobertura PT-BR sustentada; impedir repetição de métricas entre bullets e evitar que o repair de `analyze_fit` execute binding stale. | `CV-017`, `CV-018`, `CELLULAR-008` | Concluído em 2026-08-28; 60 testes focados, `validate:structure`, `runtime:verify -- --strict` e `git diff --check` aprovados; run `run_bdc2377ca46a447595a6c500a21f0c23` concluída, CV aprovado e receipt OneDrive `delivered`. |
| `2026-08-28-cv-target-coherence` | Corrigir a seleção excedente de experiências, a resolução de cargo dentro de empresas repetidas, tornar o resumo sensível às experiências-alvo do FIT_MAP e completar a materialização PT-BR de MIS sem alterar a fronteira celular. | `CV-019` | Concluído em 2026-08-28; run celular final `run_84637545b10946f29c463bbadcb4d2fc` validou CV sem `renault_cs`, com ATS top8 `8,0/8`, zero blockers e zero `missing_unexplained`; 82 testes, validações estruturais/runtime e diff limpo aprovados. |
| `2026-08-29-cellular-review-repair` | Conectar o bloqueio ATS da revisão celular ao reparo de conteúdo defensável, à nova renderização e à nova revisão no mesmo run; corrigir também a resolução de registry por candidatura. | `CELLULAR-009` | Concluído; handoff de reparo exercitado no bot-01 com bloqueio seguro de candidato inválido e canário end-to-end aprovado/reconciliado em `run_c3a26b408d264e278eceaee094820929`. |
| `2026-08-29-positioning-evidence-pipeline` | Estruturar evidências completas do candidato, derivar `candidate_cv_facts`, materializar posicionamento scoped para os artefatos, validar cobertura/invalidação e sincronizar snapshot no Notion sem alterar seu schema; execução dividida em três ondas com branches/worktrees e merge/deploy entre elas. | `POSITION-001`, `POSITION-002`, `POSITION-003` | Plano criado; execução ainda não iniciada. |

## Histórico de decisões

- 2026-08-28 — Por decisão explícita do operador, a cópia antiga de
  `processe-a-vaga` no perfil do `vagas_bot_02` foi excluída definitivamente;
  a fonte única permanece em `.agents/skills/processe-a-vaga/`. Os dois perfis
  ficam com `max_turns: 150` e `context_file_max_chars: 80000`.
- 2026-08-28 — A governança de skills foi incorporada ao runtime Hermes: a
  ordem passa a ser `project > global > profile`, com `.agents/skills/` como
  fonte canônica, guard explícito para colisões projeto/profile e preservação
  apenas das skills locais que não duplicam o projeto. A regra foi aplicada aos
  dois arquivos de profile e aos dois overlays de runtime; o plano
  `2026-08-28-runtime-skill-precedence` registra a implementação e a
  verificação dos containers.
- 2026-08-28 — A reconciliação do Tempo expôs um cargo de intake contaminado e
  um default de idioma `en`; ambos foram corrigidos no bridge celular e
  cobertos por testes, sem alteração manual de CV ou registry gerado.
- 2026-08-28 — O script de reconciliação passou a respeitar a autoridade
  definida por `CAREER_CONTROL_DB_PATH` quando `--db` não é informado, evitando
  que o mount read-only `control-plane/career.db` volte a gerar erro de
  permissão dentro dos containers.
- 2026-08-28 — O contrato de CV conciso passou a separar posicionamento/caso e
  resultado: o bullet 2 usa a evidência de alavanca coerente com a experiência,
  sem métricas de resultado, e o bullet 3 preserva o `result_bullet` quantitativo.
  O `CV-016` foi fechado com testes nas oito experiências e nos dois idiomas.
- 2026-08-28 — A suíte canônica do projeto foi executada com
  `--import-mode=importlib`: 576 testes passaram. As quatro falhas restantes
  são externas a esta frente: uma expectativa antiga do planner (`TEST-009`) e
  os três casos de persistência já acompanhados em `TEST-005`, `TEST-007` e
  `TEST-008`; nenhuma das quatro envolve resolução ou precedência de skills.

- 2026-08-21 — SQLite permanece como autoridade canônica; JSON legado fica
  preservado durante a observação e não pode selecionar candidatura nem servir
  como fallback silencioso.
- 2026-08-21 — As 8 falhas da suíte ampla foram registradas como backlog
  independente, sem reabrir o cutover operacional já validado.
- 2026-08-21 — A observação dos bots encontrou três falhas de implantação/
  persistência (`RUNTIME-002` a `RUNTIME-004`). Elas foram corrigidas antes de
  considerar os bots utilizáveis: permissões do workspace, resolução do banco
  de controle e reconstrução do intake em `sqlite_only`.
- 2026-08-21 — A execução real da análise 591 alcançou o runner e bloqueou
  somente por credencial ausente de `ollama-cloud`; nenhum fallback para outro
  provedor ou token foi inventado.
- 2026-08-24 — A análise dos bots abriu `HARNESS-001` e `HARNESS-002`: o
  supervisor deve conservar intenção e escopo entre turnos, enquanto o usuário
  aprova apenas a mutação de autoridade de storage. O handoff continua canônico
  e não pode ser substituído por edição manual de `authority.json`/SQLite.
- 2026-08-24 — `HARNESS-001`, `HARNESS-002`, `TEST-003` e `TEST-004` foram
  concluídos: intenção de sessão, aprovação idempotente, retomada oficial do
  handoff, reparo pré-ledger e marcador operacional foram validados por 73
  testes focados, `npm run validate:structure` e verifier estrito sem blockers.
- 2026-08-24 — A revalidação dos dois bots identificou `RUNTIME-008`: o banco
  montado era o mesmo (`st_dev`/inode iguais), mas `platform.node()` variava
  entre containers. A correção passou a usar somente a identidade da cópia
  montada; o ledger foi normalizado pelo `applications:authorize-handoff` no
  bot1 e os dois containers passaram a validar a mesma autoridade.
- 2026-08-24 — O hook do Hermes também foi endurecido: exceções de execução
  agora retornam `harness_hook_failure` estruturado e não liberam uma rodada
  sem supervisão. O FIT_MAP antigo do C&A continua sendo artefato histórico e
  deve ser regenerado pelo pipeline celular, nunca carimbado manualmente.
- 2026-08-24 — O primeiro `applications:run` após o `plan` revelou lease
  órfão deixado pela fronteira CLI. O lease foi liberado pelo método oficial e
  `CellExecutor.release_workspace_lease()` passou a ser chamado em `finally`.
- 2026-08-25 — A operação real do `vagas_bot_02` encontrou regressão de
  continuidade: o perfil configurado não era o perfil calculado pelo runtime,
  o pedido composto CV/OneDrive/Notion foi roteado para Notion, uma confirmação
  curta caiu em Hermes genérico sem histórico e uma consulta de entrega citou
  Jobgether enquanto a candidatura ativa era C&A. A estabilização foi aberta
  como `HARNESS-004` a `HARNESS-007` e `RUNTIME-010`; até o canário passar, o
  bot fica fora do fluxo de entrega de candidaturas reais.
- 2026-08-25 — A estabilização do bot 02 foi concluída: o profile explícito
  passou a ser respeitado, o dispatcher passou a preservar pedidos compostos,
  confirmações curtas ficaram vinculadas à sessão, o fallback operacional foi
  bloqueado sem escopo e consultas de entrega passaram a usar receipts scoped.
  O canário descartável passou duas vezes consecutivas, além de 31 testes
  focados, `validate:structure`, `runtime:verify -- --strict` e smoke no
  container. A candidatura C&A não foi retomada porque o usuário a resolveu
  manualmente.
- 2026-08-25 — A suíte canônica isolada (`tests --import-mode=importlib`)
  registrou 517 passes e quatro falhas já pertencentes às frentes de isolamento
  concorrente e fixtures/adapters legados (`TEST-001`, `TEST-005`, `TEST-007` e
  `TEST-008`); nenhuma pertence aos cinco itens de estabilização do bot 02. A
  coleta sem escopo do workspace continua inválida por incluir backups, runtimes
  Hermes e lazy packages.
- 2026-08-25 — `TEST-001` foi concluído. A reprodução concorrente revelou uma
  fixture inglesa com `growth` marcado como coberto sem evidência literal e
  expectativas antigas de pontuação/idioma; a fixture e asserções foram
  alinhadas ao contrato atual, e a execução paralela passou preservando
  manifests, hashes, reviews e conteúdo por `application_id`.
- 2026-08-25 — `RUNTIME-005` foi alinhado ao requisito operacional do usuário: os
  dois bots usam `ollama-cloud` como provider primário com `deepseek-v4-flash:0731`;
  a configuração foi conferida no host e no container, sem expor credenciais.
- 2026-08-25 — A disponibilidade de seleção local foi preservada: o provider
  `tailscale-openai-local` permanece declarado nos dois perfis para uso explícito;
  apenas o default/fallback silencioso permanece bloqueado.
- 2026-08-25 — A regressão `HARNESS-008` revelou que um `pending_input.json` sem
  sessão, deixado por uma pergunta anterior de Notion, interceptava uma nova
  mensagem como “lista de vagas salvas no LinkedIn”. O supervisor passou a
  descartar pendências legadas e ignorar pendências de outra sessão/candidatura;
  a regressão passou no teste automatizado e no container do bot 02.
- 2026-08-26 — A operação da vaga Jobgether revelou que `analise a vaga 2` não
  era tratado como seleção do menu salvo: o número caía no parser de Notion e
  o modelo entrou em loop de patches com paths truncados até `150/150`. O
  supervisor agora reconhece frases de seleção no contexto
  `linkedin_saved_jobs`; o perfil do bot 02 foi limitado a 60 iterações com
  hard stop para falhas repetidas. O skill `processe-a-vaga` também passou a
  exigir a rota celular para end-to-end e proibir provenance manual. Evidências:
  24 testes focados, validação estrutural, verifier estrito e smoke no container;
  o bot 01 não foi alterado.
- 2026-08-21 — A propagação de `application_id` no envelope do supervisor e a
  resolução absoluta do binário Hermes foram corrigidas (`RUNTIME-006` e
  `RUNTIME-007`); o bloqueio restante é exclusivamente a credencial do modelo.
- 2026-08-21 — A auditoria do CV confirmou que o problema visual era determinístico:
  o renderer usava tab no mesmo parágrafo e descartava runs enriquecidos. Os itens
  `CV-001` a `CV-003` foram abertos para correção test-first.
- 2026-08-21 — `CV-001` a `CV-003` e `TEST-006` foram concluídos. A suíte focada
  passou; seis falhas permanecem na suíte ampla, concentradas em isolamento
  concorrente e adaptadores/fixtures legados de intake, sem relação com o novo
  renderer DOCX.
- 2026-08-21 — O `outputs/_tmp/shim/sitecustomize.py` encontrado em artefatos
  históricos é evidência de workaround inválido. Ele não foi reutilizado nem
  removido para preservar rastreabilidade; a causa foi corrigida no código
  canônico e as skills agora proíbem esse bypass.
- 2026-08-27 — A reexecução real de `analise a vaga 2` no bot 01 revelou duas
  regressões encadeadas: o ID explícito era slugificado e perdia a maiúscula do
  identificador canônico, e o mirror JSON podia interromper o intake por
  `PermissionError`. O supervisor agora resolve aliases LinkedIn no SQLite,
  preserva IDs explícitos, passa o banco/application_id ao intake e trata o
  mirror como best-effort. O estado exclusivo do bot 01 foi normalizado para
  UID/GID 10000. O smoke avançou até gerar o request scoped e bloqueou somente
  pela credencial ausente do `ollama-cloud`; bot 02 permaneceu intacto.
- 2026-08-27 — A execução celular da vaga Modaxo no bot 02 revelou quatro
  pendências novas. O intake classificou o corpo da vaga como inglês, mas o
  contexto derivado classificou o mesmo texto como PT-BR; o CV resultante foi
  `cv.docx` em PT-BR, apesar de seis keywords inglesas ficarem sem cobertura.
  O `cv_content.json` também marcou essas keywords como `exact` sem presença no
  texto final, e `_build_summary` mantém um caminho que injeta `dor_central` no
  resumo. Durante o reparo, `render_cv` ficou reservado até o TTL porque o
  comando `repair` não fechou automaticamente a tentativa. Essas pendências
  foram separadas em `CV-009` a `CV-011` e `CELLULAR-002`, no plano
  `2026-08-27-cellular-cv-language-and-repair-hardening`; o pacote Modaxo não
  foi aprovado nem entregue.
- 2026-08-27 — A reconciliação do pacote Modaxo revelou que receipts auxiliares
  de gates eram persistidos em `cell_nodes` com o mesmo `run_id` dos nós do
  plano. O executor passou a projetar somente os nós executáveis ao reconstruir
  o estado, sem relaxar a detecção de nós do plano ausentes; `CELLULAR-004` foi
  concluído com teste regressivo.
- 2026-08-27 — O heartbeat celular do bot 01 revelou uma regressão de resolução
  do banco: apesar de `CAREER_CONTROL_DB_PATH` apontar para `.career-control`,
  `_run_cellular_heartbeat` ainda montava `V2_DIR.parent / "career.db"`. O bug
  foi aberto como `RUNTIME-012` e corrigido com `canonical_database().db_path`.
  O canário real do bot01 criou o run celular e validou `normalize_job` sem o
  mismatch; os dois perfis reportam a mesma identidade autoritativa.

## Modelo para novos itens

```text
| `AREA-NNN` | `BACKLOG` | Baixo/Médio/Alto | Descrição objetiva | plano-ou-nenhum | Critério de saída verificável |
```
