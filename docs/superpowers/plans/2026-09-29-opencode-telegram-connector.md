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

- [ ] Revisar no checkout fixado o código de configuração, autorização, roteamento SSE por diretório, comandos `/projects`/`/bind`/`/permissions`, persistência e dependências; registrar limitações e confirmar compatibilidade do endpoint OpenCode com a versão instalada.
- [ ] Instalar Node.js LTS compatível em diretório isolado do conector, sem alterar `/usr/bin/node`, e registrar versão/checksum usado.
- [ ] Instalar o checkout no caminho externo ao projeto e fixar dependências pelo lockfile existente; não publicar nem editar o código fonte upstream para a primeira instalação.
- [ ] Criar configuração com um projeto `candidaturas`, caminho absoluto canônico, host `127.0.0.1`, porta dedicada, `autoStart: true`, modo background e `permissionControl: false`; não configurar aliases adicionais.
- [ ] Criar arquivo de ambiente root-only usando as credenciais já existentes de bot02 sem exibir valores, incluindo um único `TELEGRAM_ALLOWED_USER_ID`; não copiar nem alterar segredos de bot01.
- [ ] Executar o comando de diagnóstico suportado pelo conector (`setup:check`) e inspecionar permissões/arquivos; resultado esperado: config válida, usuário permitido definido, OpenCode e projeto resolvíveis, sem segredo impresso.

### Task 2: Instalar serviço OpenCode Telegram

**Files:**
- Create: `/etc/systemd/system/opencode-telegram-connector.service`
- Create: diretórios externos de configuração/estado/logs usados pela unit

**Interfaces:**
- Consome: checkout e configuração validados na Task 1.
- Produz: unit systemd única para conector e servidor OpenCode gerenciado, com reinício controlado, diretório de trabalho explícito e segredos lidos por `EnvironmentFile`.

- [ ] Definir a unit com usuário de serviço existente apropriado, `WorkingDirectory` do projeto, `EnvironmentFile` externo, `ExecStart` apontando ao Node isolado/conector e dependência de rede; aplicar hardening systemd compatível sem retirar acesso RW canônico já exigido pelo projeto.
- [ ] Definir lifecycle para que o conector encerre o `opencode serve` que iniciou ao parar a unit; porta do servidor fixa em loopback e não encaminhada pelo Docker/proxy.
- [ ] Fazer `systemd-analyze verify` da unit e recarregar systemd; não iniciar Telegram ainda.
- [ ] Confirmar estado inicial observado: unit instalada/parada, porta OpenCode sem listener exposto externamente, gateway bot02 ainda desligado.

### Task 3: Criar seletor de runtime mutuamente exclusivo

**Files:**
- Modify: `scripts/bot_runtime_switch.py` ou Create: `scripts/agent_runtime_select.py` (decidir após inspecionar interfaces atuais)
- Modify: `package.json` (comando operacional, se útil)
- Modify: units/Compose do Hermes somente nas referências necessárias para start/stop/status

**Interfaces:**
- Consome: unit Hermes atual de bot01, unit OpenCode da Task 2, banco canônico de controle de runs celulares.
- Produz: comandos `status`, `select hermes`, `select opencode`; status reflete units/processos observados e modo selecionado.

- [ ] Mapear comandos reais e lifecycle atual de `hermes-vagas-bot-01`; identificar se bot01 depende de Compose ou systemd e preservar o estado atual até a troca explícita.
- [ ] Implementar status que relata runtime selecionado, serviço ativo/inativo e servidor OpenCode; estados conflitantes/ambos ativos são reportados como erro operacional.
- [ ] Antes da troca, recusar se o banco canônico contém run `running`/`reserved` ou se o OpenCode server reporta sessão ativa; falhar fechado se a checagem do banco/API não puder ser concluída.
- [ ] Implementar troca ordenada: parar e confirmar o gateway atual, iniciar e confirmar somente o destino; em falha, parar o destino parcial, garantir que no máximo um gateway permaneça ativo e retornar comandos de recuperação.
- [ ] Tornar seleções repetidas idempotentes e proteger operações concorrentes com lock externo à árvore de candidatura.
- [ ] Executar verificação operacional do seletor nos estados ambos parados, Hermes ativo, OpenCode ativo, execução ativa e falha de start simulada sem enviar mensagens nem iniciar um segundo polling.

### Task 4: Habilitar o bot02 e validar a conexão real

**Files:**
- Runtime config/secrets externos da Task 1
- Units da Task 2 e Task 3

**Interfaces:**
- Consome: serviços instalados e seletor com status confiável.
- Produz: modo OpenCode selecionável após reboot, bot02 autorizado e conectado ao único projeto preconfigurado.

- [ ] Inspecionar status e atividade do bot01 antes da janela de ativação; se houver run ativa, manter serviços sem troca até o fluxo terminar.
- [ ] Selecionar `opencode`; confirmar bot01 parado, unit do conector ativa, servidor acessível apenas em loopback e conexão Telegram autorizada.
- [ ] Confirmar com uma mensagem controlada do usuário autorizado que Telegram cria/usa sessão cujo diretório é `/opt/agent-projects/candidaturas`; verificar que eventos sem diretório ou de outro projeto não são encaminhados.
- [ ] No SSH do VS Code, usar `opencode attach` com URL local e diretório/sessão retornados pelo conector; confirmar que terminal e Telegram veem a mesma sessão.
- [ ] Reiniciar/recarregar a unit e confirmar recuperação sem duplicar polling; confirmar que segredo não aparece em logs/status e que nenhum arquivo de candidatura/skill foi alterado pela instalação.

### Task 5: Atualizar documentação operacional e modo ativo

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/roadmap.md`
- Modify: `README.md` e/ou `TELEGRAM_HARNESS_RUNBOOK.md`
- Create: `docs/runbooks/opencode-telegram-connector.md`

**Interfaces:**
- Consome: nomes finais de units, seletor, paths externos, porta, comandos e diagnóstico.
- Produz: instruções atuais coerentes e histórico do runtime anterior preservado.

- [ ] Documentar status, seleção Hermes/OpenCode, bloqueio durante runs, attach SSH, logs e recuperação de cada falha de transição.
- [ ] Atualizar `AGENTS.md` para descrever o modo configurado depois da ativação e os limites de diretório/runtime; remover proibições que conflitem com a decisão aprovada sem enfraquecer regras do projeto não relacionadas.
- [ ] Acrescentar entrada de roadmap que supersede a decisão bot01-only de 2026-09-06, preservando a linha histórica e vinculando esta especificação/plano.
- [ ] Atualizar README/runbook onde descrevem a operação corrente para diferenciar o modo selecionável da arquitetura antiga, sem apagar procedimentos históricos úteis.
- [ ] Revisar `git diff` e status para confirmar que só arquivos do escopo foram incluídos e nenhum arquivo de segredo/dado/skill foi staged.

## Handoff checks

- `systemctl is-active` e `systemctl is-enabled` refletem apenas o runtime escolhido.
- `ss -lntp` mostra a porta OpenCode escutando em `127.0.0.1`, nunca em `0.0.0.0`/IP público.
- `opencode attach` entra na mesma sessão e diretório apresentados pelo bot.
- Um comando de status após reboot reporta o serviço observado como modo ativo.
- Verificar `git status --short` para confirmar que worktree preexistente permanece preservado e segredos continuam fora de Git.
