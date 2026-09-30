# OpenCode Telegram Connector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operar `vagas_bot_02` como interface Telegram para OpenCode no projeto `/opt/agent-projects/candidaturas`, permitindo selecionar Hermes (`vagas_bot_01`) ou OpenCode como runtime único.

**Architecture:** Instalar o conector comunitário `Tah10n/opencode-telegram-connector` num diretório de serviço externo ao projeto, fixado ao commit aprovado na especificação. Um serviço systemd gerencia o conector e `opencode serve` em loopback; um seletor de runtime coordena os serviços Hermes/OpenCode, bloqueia mudanças durante runs e falha de modo seguro. O terminal SSH usa `opencode attach` no mesmo servidor.

**Tech Stack:** OpenCode CLI/server 1.18.33 (confirmar compatibilidade antes da ativação), Node.js LTS isolado >=20, conector Node.js ESM no commit `d54a14683960e0848dc5cc8d3c0d5dd142ed006d`, systemd, Python 3 para o seletor existente/novo.

**Spec:** `docs/superpowers/specs/2026-09-29-opencode-telegram-connector-design.md`

## Global Constraints

- A configuração Telegram expõe somente o alias `candidaturas` para `/opt/agent-projects/candidaturas`.
- O conector autoriza somente o ID de usuário já autorizado no `vagas_bot_02`; token e ID não aparecem em Git, argumentos ou logs.
- `opencode serve` escuta somente em `127.0.0.1`; nenhuma porta do servidor OpenCode é publicada.
- `vagas_bot_01`/Hermes e `vagas_bot_02`/OpenCode não podem operar como gateways Telegram simultâneos.
- O runtime Node compatível fica isolado; não substituir o Node.js de sistema.
- Preservar permissões OpenCode e governança existentes; desabilitar apenas a edição de perfis de permissão pelo Telegram.
- Configuração, estado persistente e logs do conector ficam fora do projeto; não reescrever `.env`, dados de candidatura ou skills.
- Preservar todas as mudanças não relacionadas já existentes no worktree; atualizar instruções ativas sem remover histórico do roadmap.
- Não criar nem executar testes automatizados neste trabalho sem solicitação explícita; a ativação depende de verificações operacionais descritas abaixo.

## Review Focus

- Chamada de troca enquanto uma run celular está `running`/`reserved` ou uma sessão OpenCode ainda está executando: o seletor recusa e mantém o gateway atual.
- Serviço parado, unit ausente ou estado de configuração divergente: status consulta serviços observados e sinaliza erro em vez de inferir o modo salvo.
- Usuário/credenciais Telegram ausentes ou inválidos: serviço falha fechado sem iniciar polling.
- Eventos SSE sem diretório correspondente ou de outro projeto: não são encaminhados ao bot.
- Falha ao iniciar o runtime de destino: no máximo um gateway Telegram permanece ativo e a mensagem de status identifica a recuperação necessária.

---

### Task 1: Auditar e preparar o conector fixado

**Files:**
- Create: `/opt/agent-services/opencode-telegram-connector/` (checkout do conector; caminho final confirmar com layout do host)
- Create: `/opt/agent-services/opencode-telegram-connector/connector.config.mjs`
- Create: `/etc/opencode-telegram-connector.env` (segredos, modo `0600`, dono root)
- Create: diretório externo de estado/logs conforme usuário de serviço

**Interfaces:**
- Entrada: especificação aprovada, conector no commit `d54a14683960e0848dc5cc8d3c0d5dd142ed006d`, OpenCode instalado no host.
- Saída: checkout reproduzível, runtime Node isolado >=20, config contendo apenas `candidaturas`, autorização do usuário existente e `permissionControl: false`; comando `setup:check` aprovado.

- [x] Revisar no checkout fixado o código de configuração, autorização, roteamento SSE por diretório, comandos `/projects`/`/bind`/`/permissions`, persistência e dependências; confirmar compatibilidade do endpoint OpenCode 1.18.33 pela SDK local e `/session/status?directory=...`.
- [x] Instalar Node.js 24.19.0 em `/opt/agent-services/node-v24.19.0`, verificar o SHA-256 contra o arquivo oficial e confirmar que `/usr/bin/node` continua em 18.19.1.
- [x] Instalar o checkout em `/opt/agent-services/opencode-telegram-connector`, detached no commit fixado; não há dependências npm de runtime.
- [x] Criar configuração com apenas `candidaturas`, caminho absoluto canônico, host `127.0.0.1`, porta 4196, `autoStart: true`, modo background e `permissionControl: false`.
- [x] Criar arquivo de ambiente root-only para o ID autorizado e credential file systemd root-only para o token já existente de bot02; não copiar nem alterar segredos de bot01.
- [x] Executar `setup:check`: 9 itens passaram e um aviso esperado informou que o servidor ainda estava parado; `getMe` confirmou a identidade do bot. O check não imprime nem grava segredos em arquivos do projeto.

### Task 2: Instalar serviço OpenCode Telegram

**Files:**
- Create: `/etc/systemd/system/opencode-telegram-connector.service`
- Create: diretórios externos de configuração/estado/logs usados pela unit

**Interfaces:**
- Consome: checkout e configuração validados na Task 1.
- Produz: unit systemd única para conector e servidor OpenCode gerenciado, com reinício controlado, diretório de trabalho explícito e segredos lidos por `EnvironmentFile`.

- [x] Definir a unit com `User=root` para preservar o binário e a autenticação OpenCode existentes, `WorkingDirectory` canônico, `EnvironmentFile` externo e `LoadCredential` para o token; o token não é herdado pelo `opencode serve`.
- [x] Definir lifecycle sob systemd para o conector e seu processo OpenCode, porta configurada em loopback e sem publicação de porta.
- [x] Fazer `systemd-analyze verify` e recarregar systemd. A unit ficou inicialmente desativada/parada antes do seletor executar a troca.
- [x] Confirmar modo inicial observado: Hermes ativo, conector parado, porta 4196 sem listener e bot02 sem polling até a ativação pelo seletor.

### Task 3: Criar seletor de runtime mutuamente exclusivo

**Files:**
- Modify: `scripts/bot_runtime_switch.py` ou Create: `scripts/agent_runtime_select.py` (decidir após inspecionar interfaces atuais)
- Modify: `package.json` (comando operacional, se útil)
- Modify: units/Compose do Hermes somente nas referências necessárias para start/stop/status

**Interfaces:**
- Consome: unit Hermes atual de bot01, unit OpenCode da Task 2, banco canônico de controle de runs celulares.
- Produz: comandos `status`, `select hermes`, `select opencode`; status reflete units/processos observados e modo selecionado.

- [x] Mapear o lifecycle: Hermes é container Docker `hermes-vagas-bot-01`; `candidaturas-compose.service` está desativado. A unit dedicada `candidaturas-hermes-bot.service` controla somente `vagas_bot_01`.
- [x] Implementar status com modo selecionado, unidades/processo observados e saúde do servidor; modos conflitantes ou inconsistentes retornam erro.
- [x] Antes da troca, consultar runs celulares vigentes/reservas não expiradas e `/session/status` filtrado por diretório; falhar fechado se SQLite/API estiver indisponível. Registros anteriores ao início da geração atual são tratados como históricos, sem serem reescritos.
- [x] Implementar parada confirmada do runtime atual, start/health do destino e rollback seguro para Hermes se a ativação OpenCode falhar.
- [x] Tornar seleções já ativas idempotentes e serializar chamadas por `flock` em `/run/lock`.
- [x] Falhar fechado em estados desconhecidos do systemd/Docker e em schema SQLite incompleto; proteger inícios das units com `Conflicts=` e prechecks de gateway.
- [x] Revisão independente encontrou e corrigiu deadlock entre o lock do seletor e `ExecStartPre`; os comandos de precheck são despachados antes do lock. Docker direto continua fora da proteção das units.
- [x] Verificar estado inicial, seleção OpenCode e status final; não simulei uma falha de start nem criei uma run artificial. O modo OpenCode ativo confirma somente um gateway.

### Task 4: Habilitar o bot02 e validar a conexão real

**Files:**
- Runtime config/secrets externos da Task 1
- Units da Task 2 e Task 3

**Interfaces:**
- Consome: serviços instalados e seletor com status confiável.
- Produz: modo OpenCode selecionável após reboot, bot02 autorizado e conectado ao único projeto preconfigurado.

- [x] Inspecionar status: runs registradas tinham última atualização em 10/09, anteriores ao container atual (11/09), nenhuma reserva vigente e nenhum log Hermes nos últimos 10 minutos; elas foram preservadas.
- [x] Selecionar `opencode`; bot01 foi parado antes de bot02 iniciar, unit ativa e `opencode serve` saudável apenas em `127.0.0.1:4196`.
- [ ] Aguardar o usuário autorizado enviar o primeiro turno para confirmar sessão Telegram no diretório canônico; connector `getMe` validou a identidade e polling iniciou, mas um bot não pode simular a mensagem do usuário.
- [ ] Anexar do SSH com `opencode attach` à sessão exibida pelo bot e confirmar a sessão compartilhada.
- [x] Habilitar `candidaturas-runtime.service` para restaurar o modo salvo no boot; estado Telegram persistente fora do projeto, token fora do ambiente herdado e fora de logs/status. Nenhum arquivo de candidatura ou skill foi alterado pela instalação.

### Task 5: Atualizar documentação operacional e modo ativo

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/roadmap.md`
- Modify: `README.md` e/ou `TELEGRAM_HARNESS_RUNBOOK.md`
- Create: `docs/runbooks/opencode-telegram-connector.md`

**Interfaces:**
- Consome: nomes finais de units, seletor, paths externos, porta, comandos e diagnóstico.
- Produz: instruções atuais coerentes e histórico do runtime anterior preservado.

- [x] Documentar status, seleção Hermes/OpenCode, bloqueio durante runs, attach SSH, logs e recuperação de falhas de transição.
- [x] Atualizar `AGENTS.md` com os modos e limites, preservando as regras de skills canônicas.
- [x] Acrescentar RUNTIME-037 e registrar a decisão atual em roadmap sem apagar o histórico.
- [x] Atualizar o runbook Telegram/Harness como histórico e apontar para as instruções correntes.
- [x] Revisar o diff e sincronizar os arquivos de escopo no checkout operacional sem sobrescrever as alterações sujas já existentes; roadmap marca `RUNTIME-037` parcialmente implantado.

## Handoff checks

- `systemctl is-active` e `systemctl is-enabled` refletem apenas o runtime escolhido.
- `ss -lntp` mostra a porta OpenCode escutando em `127.0.0.1`, nunca em `0.0.0.0`/IP público.
- `opencode attach` entra na mesma sessão e diretório apresentados pelo bot.
- Um comando de status após reboot reporta o serviço observado como modo ativo.
- Verificar `git status --short` para confirmar que worktree preexistente permanece preservado e segredos continuam fora de Git.
