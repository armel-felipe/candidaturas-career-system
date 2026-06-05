# Migração MacBook-First

Este guia descreve como portar este projeto do servidor Linux/Raspberry Pi para um MacBook como ambiente principal. A meta é manter o mesmo fluxo operacional, com ajustes mínimos e explícitos para macOS.

## 1. Escopo Da Migração

O core do projeto deve continuar igual:

- skills canônicas em `.opencode/skills/`
- entrypoint do agente em `AGENTS.md`
- scripts oficiais via `package.json`
- estado local em `.career-state/`
- entradas de vaga em `inbox/`
- documentos finais em `outputs/`
- integração Notion via `scripts/notion_sync.py` e `scripts/notion_query.py`

O MacBook deve substituir o servidor como máquina operacional, não criar uma segunda árvore paralela de scripts.

## 2. Pré-Requisitos No Mac

Instalar ferramentas base:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git node python
brew install --cask libreoffice
```

Verificar versões:

```bash
git --version
node --version
npm --version
python3 --version
/Applications/LibreOffice.app/Contents/MacOS/soffice --version
```

Instalar ou configurar o Hermes Agent no Mac e garantir que `hermes` esteja no `PATH`:

```bash
command -v hermes
hermes --version
```

Se o Hermes não estiver disponível no Mac, o pipeline local ainda roda validações e gates, mas as etapas `applications:agent-heartbeat`, `analyze`, `generate` e `repair` que chamam modelo ficam bloqueadas.

## 3. Clonar Ou Copiar O Projeto

Preferir `git clone` para preservar histórico:

```bash
mkdir -p ~/projetos
cd ~/projetos
git clone <repo-url> candidaturas
cd candidaturas
```

Se o projeto ainda não estiver em repositório remoto, copiar a pasta inteira preservando arquivos ocultos:

```bash
rsync -av --exclude node_modules --exclude outputs/_tmp <origem>/candidaturas/ ~/projetos/candidaturas/
```

Não copiar `node_modules`; reinstalar no Mac.

## 4. Instalar Dependências Do Projeto

```bash
cd ~/projetos/candidaturas
npm install
```

Validar `package.json` e estrutura:

```bash
node -e "JSON.parse(require('fs').readFileSync('package.json','utf8')); console.log('package.json ok')"
npm run validate:structure
```

## 5. Arquivos Sensíveis E Credenciais

Levar ou recriar os arquivos locais necessários:

- `.env`
- credenciais OAuth do Gmail, se existirem fora de `.env`
- cookies/sessão do LinkedIn, se o fluxo de extração depender de login persistido
- `.career-state/applications_v2/config.json`, se quiser manter a mesma configuração de modelo/fila

Depois validar:

```bash
npm run notion:list
npm run gmail:review -- --subject "Teste" --body "Teste de validação local."
```

Não testar criação real de draft Gmail sem aprovação explícita no fluxo normal.

## 6. Ajuste Obrigatório: LibreOffice No macOS

`scripts/docx/convert_pdf.sh` deve procurar `libreoffice` ou `soffice` no `PATH` e também o caminho padrão do app macOS:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice
```

Esse ajuste já faz parte do script oficial.

Validar conversão:

```bash
npm run docx:pdf -- --docx-path outputs/felipe_armel_cv_template.docx --output-dir outputs/_tmp/libreoffice_test
ls -l outputs/_tmp/libreoffice_test/felipe_armel_cv_template.pdf
```

## 7. Runtime Check

O projeto possui `scripts/runtime_check.sh`, que valida ferramentas base, LibreOffice e estrutura. Rodar:

```bash
npm run runtime:check
```

## 8. Notion E Orquestração

O fluxo recomendado continua:

```bash
npm run applications:config
npm run applications:heartbeat -- --dry-run --max-per-run 1
npm run applications:agent-heartbeat -- --max-per-run 1
```

Começar com `--max-per-run 1` até validar:

- leitura do Notion
- criação da pasta `.career-state/applications_v2/<ID>/`
- geração de requests
- chamada Hermes
- geração de DOCX
- reviewers
- atualização de status

Não instalar agendamento automático antes de um ciclo manual completo passar.

## 9. Agendamento Com launchd

No macOS, o caminho nativo é `launchd`. Para MacBook-first, instalar o heartbeat assim:

```bash
npm run applications:heartbeat:install-launchd -- --interval-minutes 60 --max-per-run 1 --run-agent
```

O atalho `npm run applications:heartbeat:install-task` aponta para o mesmo instalador `launchd`.

## 10. LinkedIn Browser Gateway

Os scripts atuais:

- `scripts/install_linkedin_browser_gateway_deps.sh`
- `scripts/start_linkedin_browser_gateway.sh`
- `scripts/status_linkedin_browser_gateway.sh`
- `scripts/stop_linkedin_browser_gateway.sh`

foram mantidos como wrappers de compatibilidade. No macOS, eles não iniciam noVNC; informam `mode=macos-local` e orientam usar o navegador local do Playwright.

No macOS, o caminho principal é Playwright com navegador visível local:

```bash
npm run linkedin:auth
npm run linkedin:extract:authenticated -- --url "<url_da_vaga>"
```

Antes de declarar a migração completa, testar:

```bash
npm run linkedin:extract -- <url_da_vaga>
```

Se o LinkedIn exigir login e o fluxo atual falhar, marcar extração LinkedIn como pendência macOS.

## 11. Gates De Aceitação

A migração só deve ser considerada concluída quando estes comandos passarem no Mac:

```bash
npm run validate:structure
npm run runtime:check
npm run fit-map:status
npm run habilidades:check
npm run runtime:diagnose
npm run validate:docx
npm run docx:pdf -- --docx-path outputs/felipe_armel_cv_template.docx --output-dir outputs/_tmp/libreoffice_test
```

E estes fluxos devem ser testados pelo menos uma vez:

- análise de uma vaga colada no chat;
- geração e aprovação de CV DOCX;
- conversão DOCX para PDF;
- leitura Notion;
- heartbeat dry-run;
- agent heartbeat com `--max-per-run 1`;
- Gmail dry-run/review, se o Mac for usado para drafts.

## 12. Regras De Não Regressão

Durante a migração:

- não recriar `.bat` ou `.ps1`;
- não criar pasta paralela de skills;
- não voltar a documentar `PowerShell`;
- não usar caminhos absolutos de máquina dentro de scripts gerados;
- preferir comandos do `package.json`;
- manter `AGENTS.md` como ponto de entrada canônico;
- rodar `npm run validate:structure` antes e depois de qualquer ajuste estrutural.

## 13. Ordem Recomendada De Execução

1. Preparar Mac com Homebrew, Node, Python, LibreOffice e Hermes.
2. Clonar/copiar o repo.
3. Rodar `npm install`.
4. Copiar `.env` e credenciais necessárias.
5. Confirmar que `convert_pdf.sh` detecta LibreOffice no macOS.
6. Rodar `npm run validate:structure`.
7. Rodar `npm run runtime:diagnose`.
8. Testar DOCX e PDF.
9. Testar Notion em modo leitura.
10. Testar heartbeat com `--dry-run --max-per-run 1`.
11. Testar `applications:agent-heartbeat -- --max-per-run 1`.
12. Só depois configurar agendamento automático.

## 14. Critério Final

O MacBook vira ambiente principal quando:

- todos os gates passam no Mac;
- Hermes consegue executar as etapas de agente;
- LibreOffice converte PDF;
- Notion e Gmail funcionam com credenciais locais;
- não há dependência operacional do servidor Linux para o fluxo principal;
- qualquer exceção, como LinkedIn browser gateway, está documentada como pendência deliberada.
