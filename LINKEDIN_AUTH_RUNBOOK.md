# Runbook: Autenticacao LinkedIn

Este guia explica como autenticar a sessao LinkedIn usada pela skill `linkedin-job-extractor`.

Ele cobre dois cenarios:

- `macOS / MacBook`: login local com navegador visivel do Playwright
- `Ubuntu / RPi5`: login remoto via `Xvfb + x11vnc + noVNC`, acessado do MacBook por tunel SSH

## Quando Usar

Use este procedimento quando:

- `npm run linkedin:extract:authenticated -- --url "<url>"` falhar dizendo que o LinkedIn exige login
- a sessao em `.career-state/browser/linkedin/` expirou
- o agente nao conseguir extrair vaga ou postagem do LinkedIn por falta de autenticacao

## Regra Principal

Nao deixe o agente tentar resolver login "no meio" da extracao.

Fluxo correto:

1. autenticar a sessao manualmente
2. confirmar que a autenticacao foi persistida
3. repetir a extracao em modo autenticado

Exemplo:

```bash
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

## Decisao Rapida

Use esta regra antes de executar qualquer comando:

- se o projeto esta rodando no `MacBook`, siga a secao `Fluxo A`
- se o projeto esta rodando no `RPi5 / Ubuntu`, siga a secao `Fluxo B`
- se um agente estiver operando no servidor Linux sem desktop visivel, ele deve bloquear a extracao, apontar para este runbook e pedir a autenticacao remota via noVNC

## Raiz Do Projeto

Todos os comandos deste runbook assumem a raiz atual do projeto:

```bash
cd "$(git rev-parse --show-toplevel)"
```

Execute esse comando a partir de qualquer subpasta do clone Git. Ele resolve a raiz local do repositorio no MacBook, Ubuntu ou RPi5.

Se voce rodar comandos fora da raiz, o npm pode falhar ao procurar `package.json`.

## Pre-Requisito Comum

Depois de `npm install`, garanta que o Chromium do Playwright exista na maquina que vai rodar a extracao:

```bash
npx playwright install chromium
```

## Fluxo A: MacBook Com Navegador Local

Use este fluxo quando o comando sera executado diretamente no macOS.

### 1. Entrar Na Pasta Do Projeto

```bash
cd "$(git rev-parse --show-toplevel)"
```

### 2. Validar O Modo Local

```bash
npm run linkedin:browser:status
```

Saida esperada no MacBook:

```text
mode=macos-local
gateway=not_used
```

### 3. Abrir O Login Manual

```bash
npm run linkedin:auth
```

O Playwright abre um navegador visivel no proprio MacBook. Faca login manualmente.

### 4. Nao Usar Google SSO

Nao clique em `Entrar com Google`.

O Google costuma bloquear Chromium controlado por automacao com aviso de navegador nao seguro.

Use:

- login nativo do LinkedIn por e-mail e senha
- codigo ou link de verificacao do proprio LinkedIn
- 2FA do LinkedIn, se solicitado

Se sua conta usa apenas Google SSO, primeiro defina uma senha nativa do LinkedIn em um navegador normal, depois volte para `npm run linkedin:auth`.

### 5. Confirmar Que A Sessao Foi Persistida

Quando `npm run linkedin:auth` detecta a sessao autenticada, ele fecha o navegador Playwright e encerra o comando.

Saida esperada:

```json
{
  "ok": true,
  "authenticated": true,
  "user_data_dir": ".career-state/browser/linkedin",
  "current_url": "..."
}
```

### 6. Repetir A Extracao

Depois do login:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Para post:

```bash
npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

Esse modo nao tenta login manual. Se a sessao expirou, ele falha rapido e voce deve repetir `npm run linkedin:auth`.

## Fluxo B: RPi5 / Ubuntu Com noVNC Via Tunel SSH Para O MacBook

Use este fluxo quando a extracao roda no servidor Linux e voce precisa controlar o navegador remoto a partir do MacBook.

## Importante Sobre O Estado Atual Do Repositorio

No estado atual do projeto, o wrapper:

```bash
npm run linkedin:browser:start
```

nao sobe o gateway Linux/noVNC. Ele entra em modo `macos-local`.

Para `Ubuntu / RPi5`, use por enquanto os scripts Linux abaixo, exatamente como estao no repositorio:

- `scripts/install_linkedin_browser_gateway_deps 2.sh`
- `scripts/start_linkedin_browser_gateway 2.sh`
- `scripts/status_linkedin_browser_gateway 2.sh`
- `scripts/stop_linkedin_browser_gateway 2.sh`

Se esse comportamento mudar no futuro, atualize este runbook junto com os wrappers canonicos.

### 1. Preparar Dependencias No Servidor

No RPi5/Ubuntu, dentro da raiz do projeto:

```bash
bash "scripts/install_linkedin_browser_gateway_deps 2.sh"
npx playwright install chromium
```

O script instala:

- `xvfb`
- `x11vnc`
- `fluxbox`
- `novnc`
- `websockify`

### 2. Subir O Gateway Grafico No Servidor

Ainda no servidor:

```bash
bash "scripts/start_linkedin_browser_gateway 2.sh"
```

Saida esperada, ou equivalente:

```text
xvfb=started pid=...
fluxbox=started pid=...
x11vnc=started pid=...
novnc=started pid=...
display=:99
novnc_url=http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080
ssh_tunnel=ssh -L 6080:127.0.0.1:6080 <usuario>@<servidor>
```

Guarde principalmente estes valores:

- `display`
- `novnc_url`
- comando de `ssh_tunnel`

### 3. Conferir O Estado Do Gateway

No servidor:

```bash
bash "scripts/status_linkedin_browser_gateway 2.sh"
```

Saida esperada:

```text
xvfb=running
fluxbox=running
x11vnc=running
novnc=running
DISPLAY=:99
NOVNC_PORT=6080
NOVNC_URL=http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080
```

Se algum processo estiver `stopped`, nao prossiga para o login; suba o gateway novamente.

### 4. Criar O Tunel SSH Do MacBook Para O Servidor

No terminal do MacBook, abra o tunel com os valores devolvidos pelo servidor:

```bash
ssh -L 6080:127.0.0.1:6080 <usuario-no-servidor>@<host-ou-ip-do-rpi5>
```

Exemplo:

```bash
ssh -L 6080:127.0.0.1:6080 felipe@192.168.0.50
```

Mantenha essa sessao SSH aberta durante todo o login.

### 5. Abrir O Navegador Remoto No MacBook

No navegador normal do MacBook, abra:

```text
http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080
```

Voce deve ver o desktop virtual do servidor Linux.

### 6. Iniciar O Login Do LinkedIn No Servidor

Em outro terminal conectado ao servidor:

```bash
DISPLAY=:99 npm run linkedin:auth
```

Esse comando abre o Chromium do Playwright dentro do display virtual do Linux. Voce vai enxergar essa janela pela pagina do noVNC aberta no MacBook.

### 7. Fazer O Login Manual Pelo noVNC

No navegador do MacBook, dentro da sessao noVNC:

- interaja com a janela do Chromium remoto
- faca login com e-mail e senha do LinkedIn
- conclua verificacoes do LinkedIn
- conclua 2FA, se solicitado

Nao use Google SSO aqui tambem.

### 8. Confirmar Que A Sessao Foi Persistida No Servidor

Quando o login terminar, o comando `DISPLAY=:99 npm run linkedin:auth` deve encerrar com algo como:

```json
{
  "ok": true,
  "authenticated": true,
  "user_data_dir": ".career-state/browser/linkedin",
  "current_url": "..."
}
```

Isso significa que a sessao foi salva no `user_data_dir` do proprio servidor Linux.

### 9. Rodar A Extracao Autenticada No Servidor

Depois do login concluido:

```bash
DISPLAY=:99 npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Para post:

```bash
DISPLAY=:99 npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

Se voce estiver usando o fluxo canonico de intake, a autenticacao continua sendo manual, mas a extracao final deve voltar para os wrappers de intake:

```bash
npm run intake:linkedin-job -- --url "<url-da-vaga>"
```

ou

```bash
npm run intake:linkedin-post -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

### 10. Encerrar O Gateway Quando Terminar

No servidor:

```bash
bash "scripts/stop_linkedin_browser_gateway 2.sh"
```

## Comandos Uteis

MacBook:

```bash
npm run linkedin:browser:status
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

RPi5 / Ubuntu:

```bash
bash "scripts/status_linkedin_browser_gateway 2.sh"
DISPLAY=:99 npm run linkedin:auth
DISPLAY=:99 npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
bash "scripts/stop_linkedin_browser_gateway 2.sh"
```

Extracao sem salvar no fluxo canonico:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>" --no-save-job
```

## Troubleshooting

### `npm error enoent Could not read package.json`

Voce esta fora da pasta do projeto.

Corrigir no MacBook:

```bash
cd "$(git rev-parse --show-toplevel)"
```

No servidor Ubuntu/RPi5, use o mesmo comando a partir de uma subpasta do clone.

### `LinkedIn exige login, mas não há DISPLAY/WAYLAND_DISPLAY`

Isso acontece quando o login manual foi exigido em ambiente Linux sem interface visivel.

Corrigir:

1. subir o gateway com `bash "scripts/start_linkedin_browser_gateway 2.sh"`
2. abrir o tunel SSH
3. abrir o noVNC no MacBook
4. repetir o login com `DISPLAY=:99 npm run linkedin:auth`

### O noVNC Abre, Mas A Tela Fica Preta

Cheque no servidor:

```bash
bash "scripts/status_linkedin_browser_gateway 2.sh"
```

Se `xvfb` ou `fluxbox` nao estiverem `running`, reinicie o gateway.

### Porta 6080 Nao Abre No MacBook

Confirme:

- o tunel SSH continua aberto
- o gateway no servidor esta `running`
- o `NOVNC_PORT` nao foi alterado

Se a porta mudou, use o valor exibido em `.career-state/browser-gateway/env` ou na saida do script de status.

### Google Diz Que O Navegador Nao E Seguro

Nao use Google SSO. Use login nativo do LinkedIn.

### Login Concluiu, Mas Extracao Falha

Repita a autenticacao no mesmo ambiente onde a extracao roda:

- MacBook: `npm run linkedin:auth`
- RPi5 / Ubuntu: `DISPLAY=:99 npm run linkedin:auth`

Depois rode novamente a extracao autenticada.

Se o LinkedIn pedir captcha, verificacao de seguranca adicional ou bloquear a automacao, a execucao deve ser tratada como bloqueada.

## O Que Nao Fazer

- nao colocar senha LinkedIn em script
- nao automatizar captcha ou 2FA
- nao usar Google SSO no navegador Playwright
- nao deixar o agente esperando login dentro da extracao da vaga
- nao usar navegador generico ou web search para "substituir" o extrator autenticado
- no Linux, nao assumir que `npm run linkedin:browser:start` sobe o noVNC; hoje isso nao acontece

## Resumo Rápido

MacBook:

```bash
cd "$(git rev-parse --show-toplevel)"
npx playwright install chromium
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

RPi5 / Ubuntu + MacBook com noVNC:

```bash
# no servidor
bash "scripts/install_linkedin_browser_gateway_deps 2.sh"
npx playwright install chromium
bash "scripts/start_linkedin_browser_gateway 2.sh"
DISPLAY=:99 npm run linkedin:auth
DISPLAY=:99 npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"

# no MacBook, em paralelo, mantenha o tunel SSH aberto
ssh -L 6080:127.0.0.1:6080 <usuario>@<servidor>
```
