# Runbook: Login LinkedIn No MacBook

Este guia explica como autenticar a sessão LinkedIn usada pela skill `linkedin-job-extractor` no macOS.

## Quando Usar

Use este procedimento quando:

- `npm run linkedin:extract:authenticated` falhar dizendo que LinkedIn exige login;
- a sessão em `.career-state/browser/linkedin/` expirou;
- o agente não conseguir extrair uma vaga do LinkedIn por falta de autenticação.

## Regra Principal

Não deixe o agente tentar logar durante a extração da vaga. Primeiro autentique a sessão manualmente, depois rode a extração em modo autenticado.

Fluxo correto:

```bash
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

## 1. Entrar Na Pasta Do Projeto

No terminal do MacBook:

```bash
cd "/Users/mac/Library/Mobile Documents/com~apple~CloudDocs/llm server/projetos/candidaturas"
```

Se você rodar `npm run linkedin:auth` fora dessa pasta, o npm vai falhar procurando `package.json`.

## 2. Preparar Playwright

Depois de rodar `npm install`, instale o Chromium do Playwright se ainda não estiver instalado:

```bash
npx playwright install chromium
```

## 3. Autenticar LinkedIn

Rode:

```bash
npm run linkedin:auth
```

O Playwright abre um navegador visível no MacBook. Faça login manualmente.

## 4. Não Usar Google SSO

Não clique em `Entrar com Google`.

O Google costuma bloquear Chromium controlado por automação com aviso de navegador não seguro.

Use:

- login nativo do LinkedIn por e-mail/senha;
- código/link de verificação do próprio LinkedIn;
- 2FA do LinkedIn, se solicitado.

Se sua conta LinkedIn usa apenas Google SSO, abra o LinkedIn no navegador normal do MacBook e defina uma senha LinkedIn primeiro. Depois volte ao navegador aberto pelo Playwright e entre com e-mail/senha.

## 5. Tela Fechou Depois Do Login

Isso é esperado.

Quando `npm run linkedin:auth` detecta a sessão autenticada, ele fecha o navegador Playwright e encerra o comando.

O terminal deve mostrar algo como:

```json
{
  "ok": true,
  "authenticated": true,
  "user_data_dir": ".career-state/browser/linkedin",
  "current_url": "..."
}
```

## 6. Extrair Vaga Depois Do Login

Com a sessão autenticada:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Esse modo não tenta login manual. Se a sessão expirou, ele falha rápido e você deve repetir `npm run linkedin:auth`.

## 7. Comandos Úteis

Checar modo local:

```bash
npm run linkedin:browser:status
```

Autenticar novamente:

```bash
npm run linkedin:auth
```

Extrair sem salvar no fluxo canônico:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>" --no-save-job
```

## 8. Problemas Comuns

### `npm error enoent Could not read package.json`

Você está fora da pasta do projeto.

Corrigir:

```bash
cd "/Users/mac/Library/Mobile Documents/com~apple~CloudDocs/llm server/projetos/candidaturas"
```

### O Navegador Não Abre

Confirme que o Chromium do Playwright está instalado:

```bash
npx playwright install chromium
```

Depois rode novamente:

```bash
npm run linkedin:auth
```

### Google Diz Que O Navegador Não É Seguro

Não use Google SSO. Use login nativo do LinkedIn.

### Login Concluiu, Mas Extração Falha

Rode:

```bash
npm run linkedin:auth
```

Se retornar `authenticated=true`, tente novamente:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Se o LinkedIn pedir captcha, verificação de segurança adicional ou bloquear a automação, a execução deve ser tratada como bloqueada.

## 9. O Que Não Fazer

- Não colocar senha LinkedIn em script.
- Não automatizar captcha ou 2FA.
- Não usar Google SSO no navegador Playwright.
- Não deixar o agente esperando login dentro da extração da vaga.
- Não usar o gateway noVNC no MacBook; ele é compatibilidade Linux apenas.

## 10. Resumo Rápido

```bash
cd "/Users/mac/Library/Mobile Documents/com~apple~CloudDocs/llm server/projetos/candidaturas"
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```
