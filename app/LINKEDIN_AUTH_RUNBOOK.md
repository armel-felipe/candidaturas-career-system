# Runbook: Autenticação LinkedIn

Este runbook cobre a renovação manual da sessão LinkedIn usada pelo extrator
de vagas e posts.

## Ambientes atuais

- Servidor: `srv1876742`
- Raiz do deployment no host: `/opt/agent-projects/candidaturas`
- Serviço do agente: `vagas_bot_01`
- Container: `hermes-vagas-bot-01`
- Raiz do projeto no container: `/workspace/candidaturas`
- Estado persistente de `vagas_bot_01` no host:
  `/opt/agent-projects/candidaturas/workspaces/vagas_bot_01/state`
- Estado visto pelo processo no container:
  `/workspace/candidaturas/.career-state`
- noVNC do bot 01: host loopback `127.0.0.1:6081`, container `0.0.0.0:6080`

O agente roda no container como UID/GID `10000`. Portanto, instalar pacotes
com `apt-get` dentro do agente não é o procedimento correto. As dependências
gráficas são incorporadas à imagem Docker.

## Quando usar

Use este procedimento quando:

- `npm run linkedin:extract:authenticated` indicar sessão expirada;
- a sessão em `.career-state/browser/linkedin` não estiver autenticada;
- o LinkedIn exigir login, checkpoint ou verificação manual.

O fluxo é:

1. preparar/recriar a imagem;
2. iniciar o gateway gráfico no mesmo container do agente;
3. abrir o noVNC por túnel SSH;
4. concluir o login manual;
5. repetir a extração autenticada;
6. desligar o gateway.

Não automatize senha, CAPTCHA ou 2FA.

## Fluxo A: MacBook com navegador local

Quando o Playwright roda diretamente no MacBook:

```bash
cd <raiz-do-projeto>
npx playwright install chromium
npm run linkedin:browser:status
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

O navegador abre localmente. Use login nativo do LinkedIn por e-mail/senha e os
mecanismos de verificação do próprio LinkedIn. Evite Google SSO no navegador
controlado pelo Playwright.

## Fluxo B: servidor atual com Docker e noVNC

### 1. Preparar a imagem no host

No servidor atual:

```bash
cd /opt/agent-projects/candidaturas
docker compose build vagas_bot_01
docker compose up -d --force-recreate vagas_bot_01
```

A imagem instala `xvfb`, `x11vnc`, `fluxbox`, `novnc` e
`websockify`. Não use `sudo apt-get` dentro do container.

Valide as dependências:

```bash
docker compose exec --user 10000 -T vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:browser:install-deps'
```

Saída esperada:

```text
gateway_dependencies=present
gateway_dependencies_source=Docker image
```

### 2. Iniciar o gateway no container

Ainda no servidor:

```bash
docker compose exec --user 10000 -T vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:browser:start'
```

Confira:

```bash
docker compose exec --user 10000 -T vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:browser:status'
```

A saída deve indicar `xvfb=running`, `fluxbox=running`,
`x11vnc=running`, `novnc=running`, `DISPLAY=:99` e:

```text
NOVNC_PUBLIC_PORT=6081
NOVNC_URL=http://127.0.0.1:6081/vnc.html?host=127.0.0.1&port=6081
```

### 3. Abrir o túnel SSH no computador com navegador

No MacBook ou outra máquina do operador, mantenha este túnel aberto:

```bash
ssh -L 6081:127.0.0.1:6081 <usuario>@srv1876742
```

Abra no navegador local:

```text
http://127.0.0.1:6081/vnc.html?host=127.0.0.1&port=6081
```

A porta é publicada apenas no loopback do servidor; ela não fica exposta
publicamente. Dentro do container, o websockify escuta na interface do
container para que o encaminhamento Docker funcione; o host continua limitado
a `127.0.0.1`.

### 4. Iniciar o login do LinkedIn

Em outro terminal no servidor:

```bash
cd /opt/agent-projects/candidaturas
docker compose exec --user 10000 -T -e DISPLAY=:99 vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:auth'
```

Faça o login na janela Chromium exibida pelo noVNC. Ao concluir, o comando
deve informar `authenticated: true` e fechar o navegador.

### 5. Rodar a extração autenticada

```bash
docker compose exec --user 10000 -T -e DISPLAY=:99 vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"'
```

Para post:

```bash
docker compose exec --user 10000 -T -e DISPLAY=:99 vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:post:extract:authenticated -- --url "<url-do-post>" --company "<empresa>" --role "<cargo>"'
```

O perfil persistente usado é o do mesmo agente:

```text
/workspace/candidaturas/.career-state/browser/linkedin
```

### 6. Encerrar o gateway

Quando terminar:

```bash
cd /opt/agent-projects/candidaturas
docker compose exec --user 10000 -T vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:browser:stop'
```

## Troubleshooting

### Dependência ausente

Se o preflight indicar dependência ausente, execute no host:

```bash
cd /opt/agent-projects/candidaturas
docker compose build vagas_bot_01
docker compose up -d --force-recreate vagas_bot_01
```

Depois repita o preflight dentro do container. Não tente instalar com `sudo`
dentro do agente.

### O gateway está parado

```bash
cd /opt/agent-projects/candidaturas
docker compose exec --user 10000 -T vagas_bot_01 sh -lc \
  'cd /workspace/candidaturas && npm run linkedin:browser:start'
```

### Tela preta

Confira o status. Se `xvfb` ou `fluxbox` estiverem parados, pare e inicie
novamente o gateway. Consulte os logs persistidos em
`/workspace/candidaturas/.career-state/browser-gateway/logs`.

### Porta inacessível

Confirme:

- o túnel SSH está aberto;
- o container está ativo;
- `docker port hermes-vagas-bot-01 6080` mostra `127.0.0.1:6081`;
- o navegador local usa a porta `6081`.

### LinkedIn continua pedindo login

Repita o login no mesmo container que executa a extração. Não copie o perfil
para outro agente ou para o host; o estado de `vagas_bot_01` é separado do
estado de `vagas_bot_02`.

## O que não fazer

- não instalar dependências no host esperando alterar a imagem do agente;
- não executar `apt-get` ou `sudo` dentro do container;
- não publicar o noVNC em `0.0.0.0`;
- não colocar senha do LinkedIn em script;
- não automatizar CAPTCHA ou 2FA;
- não usar os scripts temporários com sufixo ` 2`;
- não usar navegador genérico ou busca web para substituir a sessão autenticada.
