---
name: linkedin-saved-jobs
description: >
  Use esta skill para listar as vagas salvas do LinkedIn/Rastreador de vagas
  e descobrir qual URL linkedin.com/jobs/view/... deve entrar no intake de
  análise FIT_MAP. Acione quando o usuário pedir "lista de vagas salvas",
  "minhas vagas", "rastreador de vagas", "saved jobs", "linkedin salvas",
  "vagas que salvei" ou quiser escolher uma vaga salva para analisar.
---

# LinkedIn Saved Jobs Selector

## Governança

Manutenção canônica desta skill: `.agents/skills/linkedin-saved-jobs/SKILL.md`.
Script principal: `scripts/linkedin_saved_jobs_extractor.js`.

## Escopo

Esta skill é um seletor operacional de URL. Ela usa a sessão autenticada local do
LinkedIn para listar as vagas salvas no Rastreador de vagas
(`https://www.linkedin.com/jobs-tracker/`) e devolver ao usuário uma lista curta
de vagas com URL canônica. Depois que o usuário escolhe uma vaga, a análise
começa obrigatoriamente pelo intake oficial.

Ela extrai:
- Título do cargo
- Nome da empresa
- Localização
- ID único da vaga e URL
- As páginas operacionais recentes do Rastreador de vagas

Usa a mesma sessão persistente do LinkedIn em `.career-state/browser/linkedin/` —
se a sessão estiver expirada, executar `npm run linkedin:auth` primeiro.

Esta skill não faz análise de aderência, não gera FIT_MAP, não extrai descrição
completa da vaga e não substitui `intake:linkedin-job`.

## Gatilhos

- "lista de vagas salvas"
- "minhas vagas do LinkedIn"
- "vagas que salvei"
- "saved jobs"
- "rastreador de vagas"
- "linkedin salvas"
- "extrai minhas vagas salvas"
- "qual vaga salva vamos analisar"

## Comando

```bash
npm run linkedin:saved-jobs:extract
```

O script navega para `https://www.linkedin.com/jobs-tracker/`, lê o contador da
aba `Salvas`, clica na paginação do próprio Rastreador (`Página 2`, `Próxima`
etc.), deduplica e salva em `inbox/linkedin_saved_jobs.json`.

Por padrão, o comando extrai as páginas necessárias para atingir o contador da
aba `Salvas`, respeitando o limite operacional padrão. Para manutenção ou
auditoria de paginação profunda, usar explicitamente:

```bash
npm run linkedin:saved-jobs:extract -- --all
npm run linkedin:saved-jobs:extract -- --max-pages 5
```

Quando o usuário pedir vagas salvas, executar este comando como próxima ação
concreta após ler esta skill. Não abrir navegador genérico, não fazer web search
e não ler `inbox/linkedin_saved_jobs.json` antigo como substituto da extração,
salvo se o usuário pedir explicitamente a última extração salva.

## Dependências

- Playwright (já instalado no projeto)
- Sessão LinkedIn persistida em `.career-state/browser/linkedin/`
  - Se expirada: executar `npm run linkedin:auth` primeiro

## Output

Arquivo: `inbox/linkedin_saved_jobs.json`
Estrutura:

```json
{
  "extractedAt": "2026-06-05T02:56:42.806Z",
  "source": "https://www.linkedin.com/jobs-tracker/",
  "mode": "recent",
  "expectedTotal": 11,
  "total": 10,
  "scannedPages": 2,
  "pageResults": [
    {
      "page": 1,
      "found": 10,
      "new": 10,
      "url": "https://www.linkedin.com/jobs-tracker/"
    }
  ],
  "jobs": [
    {
      "jobId": "4422954585",
      "title": "OPERATIONS MANAGER (CSM)",
      "company": "Dock",
      "location": "Barueri, SP (Híbrido)",
      "url": "https://www.linkedin.com/jobs/view/4422954585/"
    }
  ]
}
```

## Bloqueios conhecidos

- Se a sessão LinkedIn expirar, o script pode cair na tela de login.
  Rodar `npm run linkedin:auth` (abre navegador para login manual) e depois
  executar o script novamente.
- LinkedIn com detecção anti-bot pode exigir modo headful (`headless: false`).
  Se falhar em headless, trocar para headful no script.
- Se a página do LinkedIn mudar e o script extrair vagas sem título, empresa ou
  URL, a execução deve ser tratada como bloqueada até corrigir o parser.

## Workflow Operacional

1. Ler `.agents/skills/career-system/SKILL.md` e este arquivo.
2. Executar `npm run linkedin:saved-jobs:extract`.
3. Se falhar por sessão expirada, executar `npm run linkedin:auth` e repetir o
   extrator. Se a autenticação exigir ação manual do usuário, declarar bloqueio.
4. Validar o arquivo gerado com projeção compacta:

```bash
jq '{extractedAt, mode, total, scannedPages, pageResults, jobs: [.jobs[] | {jobId,title,company,location,url}]}' inbox/linkedin_saved_jobs.json
```

5. Listar as vagas em formato curto: índice, título, empresa, localização e URL.
6. Perguntar qual vaga o usuário quer analisar.
7. Depois da escolha, executar somente:

```bash
npm run intake:linkedin-job -- --url "<url-da-vaga-escolhida>"
```

8. Após o intake, seguir `next_required_step`. Se for `fill_fit_map_draft`, a
   próxima skill é `career-fit-analysis` e o agente deve preencher
   `.career-state/fit_map.draft.json`; não entregar análise textual usando apenas
   a lista de vagas salvas.

## Regras de Conduta

- Não usar `browser_navigate`, web search, curl ou navegador genérico para listar
  ou analisar vagas salvas do LinkedIn.
- Não usar `npm run linkedin:extract:authenticated` como substituto do intake
  quando o objetivo for análise/FIT_MAP.
- Não apresentar a lista como atual se o extrator não tiver rodado nesta execução.
- Não considerar a skill concluída sem `inbox/linkedin_saved_jobs.json` persistido
  e validado.
- Não prosseguir para FIT_MAP com URL digitada de memória; usar a URL salva no
  JSON recém-extraído.
- Não usar `--all` no fluxo normal de escolha de vaga para FIT_MAP; essa opção
  varre histórico antigo e só deve rodar quando o usuário pedir varredura completa.
