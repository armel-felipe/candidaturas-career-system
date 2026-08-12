---
name: linkedin-job-extractor
instruction_modules: [runtime-core, intake-fit-map]
description: >
  Extrai a descrição completa de uma vaga do LinkedIn ou de uma postagem do LinkedIn que divulgue uma vaga, usando
  sessão local autenticada em navegador Playwright. Use quando o usuário pedir para abrir um link do LinkedIn, capturar
  a descrição da vaga, salvar a vaga localmente ou preparar uma vaga/postagem do LinkedIn para análise/CV no sistema de
  candidaturas. Também use quando o usuário pedir "avalie a vaga em", "analise a vaga em", "gera CV para" ou
  equivalente seguido de URL `linkedin.com/jobs/view/...`, `linkedin.com/jobs/...`, `linkedin.com/job/...`,
  `linkedin.com/feed/update/...` ou `linkedin.com/posts/...`.
---

# LinkedIn Job Extractor

## Governança

Manutenção canônica desta skill: `.agents/skills/linkedin-job-extractor/SKILL.md`.

Antes de executar esta skill, leia este arquivo. Leitura não conta como execução; a execução só termina quando a vaga
for extraída, salva e validada, ou quando houver bloqueio explícito.

## Escopo

Esta skill extrai uma URL de vaga ou postagem do LinkedIn exclusivamente pelos scripts locais do projeto, reaproveita
uma sessão persistente e salva a descrição completa em `inbox/job_descriptions/`.

Regra dura: não usar `browser_navigate`, navegador genérico do agente, `web_search` ou busca web para abrir/analisar URL do LinkedIn. Essas ferramentas não usam a sessão persistida em `.career-state/browser/linkedin/`, tendem a bater em login/timeout e não persistem a vaga no fluxo canônico.

Gatilhos obrigatórios:

- `https://www.linkedin.com/jobs/view/4405127989/`
- qualquer URL contendo `linkedin.com/jobs/view/`
- qualquer URL contendo `linkedin.com/jobs/` ou `linkedin.com/job/` em pedido de avaliação, análise, CV, carta, pitch,
  habilidades ou registro de candidatura
- qualquer URL contendo `linkedin.com/feed/update/`, `linkedin.com/posts/` ou `linkedin.com/pulse/` quando o usuário
  pedir extração/análise de uma vaga divulgada em postagem

Não automatizar login por usuário/senha. O login deve ser manual no navegador aberto pelo Playwright, com sessão
persistida localmente em `.career-state/browser/linkedin/`.

Durante login manual, não usar `Entrar com Google`/SSO Google. O Google costuma bloquear Chromium controlado por
automação com aviso de navegador não seguro. Preferir login nativo do LinkedIn por e-mail/senha ou link/código de
verificação do próprio LinkedIn. Se a conta usa apenas Google SSO, definir uma senha no LinkedIn pelo navegador normal
do usuário antes de tentar autenticar a sessão Playwright.

Não tentar contornar captcha, 2FA, bloqueio anti-bot, paywall, limitação de conta ou termos de uso do LinkedIn. Se a
página bloquear a automação, declarar execução bloqueada.

## Comando

Quando o pedido envolver análise, FIT_MAP, CV, FERAS, carta ou habilidades, usar preferencialmente o intake:

```bash
npm run intake:linkedin-job -- --url "<url-da-vaga>"
npm run intake:linkedin-post -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

O intake chama os extratores autenticados, salva a descrição, registra `active_intake`, recria o template FIT_MAP e devolve `next_required_step`.

Para URL de vaga (`/jobs/` ou `/job/`), em execução automatizada/agente, usar sempre:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Para URL de postagem (`/feed/update/`, `/posts/` ou `/pulse/`), usar:

```bash
npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

Se a postagem contiver um link de vaga LinkedIn, o script de postagem delega automaticamente para
`scripts/linkedin_extract_job.js`. Se não houver link de vaga, `--company` e `--role` são obrigatórios para salvar a
descrição com segurança.

Se retornar erro de sessão expirada, a execução está bloqueada até autenticar manualmente com:

```bash
npm run linkedin:auth
```

O comando interativo abaixo é permitido apenas em uso manual supervisionado:

```bash
npm run linkedin:extract -- --url "<url-da-vaga>"
```

Para evitar timeout do agente durante login manual, separar autenticação e extração:

```bash
# Rodar uma vez quando a sessão LinkedIn expirar.
npm run linkedin:auth

# Em fluxo automatizado/agente, extrair apenas se a sessão já estiver válida.
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Opções úteis:

```bash
npm run linkedin:auth
npm run linkedin:extract -- --url "<url-da-vaga>" --no-save-job
npm run linkedin:extract -- --url "<url-da-vaga>" --headless
npm run linkedin:extract -- --url "<url-da-vaga>" --headless --no-login-prompt
npm run linkedin:extract -- --url "<url-da-vaga>" --timeout-ms 90000
npm run linkedin:extract -- --url "<url-da-vaga>" --login-wait-ms 600000
npm run linkedin:post:extract -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

Comportamento de autenticação:

- por padrão, o script reaproveita `.career-state/browser/linkedin/`;
- `npm run linkedin:auth` abre/valida a sessão e sai sem extrair vaga;
- em execução automática, preferir `npm run linkedin:extract:authenticated -- --url "<url>"` para falhar rápido quando a sessão expirar, sem aguardar login manual dentro do agente;
- se a sessão já estiver autenticada, segue direto;
- no macOS, abre navegador visível local para login manual;
- se `--headless` for usado, o script tenta headless primeiro e faz fallback para navegador visível somente quando o login
  manual for necessário;
- se `--no-login-prompt` for usado, o script nunca abre navegador visível e falha quando a sessão não estiver válida;
- o script não depende de `Enter`: após abrir o navegador, aguarda o login manual até `--login-wait-ms` e continua
  quando detectar sessão válida.

## Login Manual No MacBook

No macOS, não use gateway noVNC. O login manual acontece em uma janela local do Playwright:

```bash
npm run linkedin:auth
```

Depois da autenticação:

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
```

Os comandos `linkedin:browser:*` continuam existindo apenas como wrappers de compatibilidade; no MacBook eles informam
`mode=macos-local` e não iniciam gateway remoto.

## Workflow Operacional

1. Confirmar se a URL é:
   - vaga: `linkedin.com/jobs/`, `linkedin.com/job/` ou página equivalente de vaga no LinkedIn;
   - postagem: `linkedin.com/feed/update/`, `linkedin.com/posts/`, `linkedin.com/pulse/` ou equivalente.
2. Não chamar `browser_navigate`, `web_search` nem navegador genérico do agente.
3. Para vaga, executar `npm run linkedin:extract:authenticated -- --url "<url>"` em fluxos automatizados.
4. Para postagem, executar
   `npm run linkedin:post:extract:authenticated -- --url "<url>" --company "<empresa>" --role "<cargo>"`.
   - Se empresa/cargo não estiverem explícitos no pedido ou no contexto, bloquear e pedir esses dois valores.
   - Se o script encontrar link de vaga dentro da postagem, a extração da vaga será delegada automaticamente.
   - Se não encontrar link de vaga, a postagem será salva como origem da descrição.
5. Se a sessão estiver expirada, bloquear a execução e autenticar com `npm run linkedin:auth` seguindo `LINKEDIN_AUTH_RUNBOOK.md`.
6. Se o script informar que login é necessário:
   - aguardar o usuário fazer login manualmente no navegador aberto;
   - não pedir nem registrar senha;
   - não usar `Entrar com Google`; usar login nativo do LinkedIn por e-mail/senha ou código;
   - retomar somente depois de `npm run linkedin:auth` retornar `authenticated=true`.
7. Validar a saída do script:
   - arquivo Markdown salvo em `inbox/job_descriptions/`;
   - para vaga, metadados salvos em `.career-state/linkedin_job_extract.json`;
   - para postagem, bruto salvo em `inbox/linkedin_posts/` e metadados salvos em `.career-state/linkedin_post_extract.json`;
   - descrição com texto substantivo, não só cabeçalho ou aviso de login.
8. Se `--no-save-job` não for usado, o script também chama `scripts/save_job_description.py` para registrar a vaga no
   fluxo canônico antes do FIT_MAP.
9. Após extração bem-sucedida, se o usuário pediu análise, executar `career-fit-analysis` a partir da descrição salva. Em novos fluxos, preferir `intake:linkedin-job`/`intake:linkedin-post`, que já faz a transição para o draft.
10. Se o usuário pediu para atualizar uma vaga existente no Notion com a descrição extraída, executar primeiro dry-run:
    `python3 scripts/notion_sync.py update-description-record <id_unico> --job-description <arquivo.md> --source-url "<url>" --dry-run`.
    Só executar sem `--dry-run` depois de confirmação explícita.
11. Se o usuário pediu para criar/faça/registrar a vaga extraída no Notion antes de análise/FIT_MAP, executar primeiro
    dry-run:
    `python3 scripts/notion_sync.py create-description-record --job-description <arquivo.md> --company "<empresa>" --role "<cargo>" --source-url "<url>" --dry-run`.
    Só executar sem `--dry-run` depois de confirmação explícita.

## Critérios de Conclusão

Concluído somente se:

- a descrição completa foi extraída;
- o arquivo em `inbox/job_descriptions/` existe;
- para vaga, `.career-state/linkedin_job_extract.json` aponta para o arquivo gerado;
- para postagem, `.career-state/linkedin_post_extract.json` aponta para o bruto em `inbox/linkedin_posts/` e para a
  vaga salva ou para o link de vaga delegado;
- quando aplicável, `scripts/save_job_description.py` executou com sucesso.

Bloqueado se:

- LinkedIn exigir captcha, 2FA não concluído, verificação de segurança ou login que o usuário não conseguiu concluir;
- o link não for uma vaga;
- a postagem não trouxer link de vaga e empresa/cargo não tiverem sido informados;
- a página carregar sem a descrição da vaga;
- o ambiente não permitir navegador headful e a sessão ainda não estiver autenticada.

Nunca apresentar a skill como concluída se apenas abriu o navegador ou apenas leu a página sem persistir o artefato.

## Execucao Multiagente

Quando acionada pelo maestro, esta skill deve operar como `linkedin-agent`.

Entrada obrigatoria:
- ler primeiro `.career-state/agent_requests/linkedin_request.json` ou `.career-state/agent_requests/linkedin_request.md`
- usar somente comandos permitidos no request

Saida obrigatoria:
- salvar a descrição em `inbox/job_descriptions/`
- atualizar metadados em `.career-state/linkedin_job_extract.json` ou `.career-state/linkedin_post_extract.json`
- quando a extracao for para analise, deixar `active_intake` pronto para `fit-map-agent`

Proibido neste modo:
- usar browser generico, web_search ou navegador do agente
- automatizar login, senha, captcha ou 2FA
- analisar a URL sem persistir a descrição
- criar scripts temporarios na raiz
