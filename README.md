# Candidaturas Career System

Sistema local-first para organizar e executar candidaturas profissionais com base em evidências. O projeto transforma uma vaga em um fluxo rastreável de análise de aderência, posicionamento, CV, pitch, carta, habilidades ATS e atualização do tracker no Notion.

O runtime prioritário é o OpenCode. O projeto também oferece integração com Hermes, Codex e Telegram por meio do `HarnessSupervisor`.

> Este é um sistema pessoal e operacional. O repositório contém código, contratos, skills e documentação; credenciais, dados de candidaturas e artefatos gerados permanecem locais.

## O que ele faz

- recebe vagas por texto, URL, LinkedIn ou ID do Notion;
- normaliza a entrada e preserva o fingerprint da descrição;
- constrói e valida um `FIT_MAP` com evidências do candidato;
- gera conteúdo de CV e DOCX com gates de qualidade e ATS;
- produz FERAS, carta de apresentação e habilidades para Gupy/Mercado Livre;
- prepara atualizações no Notion e drafts no Gmail com aprovação explícita;
- executa candidaturas em pacotes isolados por `application_id`;
- mantém requests, estados, receipts e relatórios para retomada e auditoria;
- suporta heartbeat e execução celular com isolamento de workspace.

## Arquitetura

```text
mensagem ou fonte da vaga
        |
        v
intake -> FIT_MAP -> artefato especializado -> gates locais -> entrega/aprovação
        |
        +--> Notion, Gmail draft ou OneDrive, quando autorizado
```

Principais camadas:

- `src/career/`: schemas, services, tasks e workflow estruturados;
- `scripts/career_cli.py`: CLI oficial do projeto;
- `.agents/skills/`: skills canônicas e seus workflows;
- `HarnessSupervisor`: roteamento de mensagens e continuidade de sessão;
- `.career-state/applications_v2/<ID>/`: memória e estado por candidatura;
- `outputs/`: artefatos finais locais;
- `control-plane/`: banco SQLite de controle compartilhado pelos runtimes.

O estado operacional não deve ser selecionado por ponteiros globais legados. Para uma candidatura, use sempre o `application_id` canônico.

## Requisitos

- Linux ou macOS;
- Python 3.11 ou superior;
- Node.js 18 ou superior;
- npm;
- OpenCode, Hermes ou Codex, conforme o runtime escolhido;
- LibreOffice para conversão/validação de documentos, quando necessário;
- credenciais opcionais para Notion, Gmail, LinkedIn, Ollama Cloud e rclone.

## Instalação

```bash
git clone git@github.com:armel-felipe/candidaturas-career-system.git
cd candidaturas-career-system

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
cp .env.example .env
```

Preencha apenas as integrações que serão usadas. O arquivo `.env` não deve ser commitado. A configuração de runtime fica em `.career-state/` e também é local, portanto uma instalação nova deve ser inicializada conforme o fluxo escolhido.

Valide a estrutura antes de operar:

```bash
npm run validate:structure
```

## Uso rápido

### OpenCode

Na raiz do repositório:

```bash
opencode
```

Exemplos de pedidos dentro da sessão:

```text
Analise esta vaga: <texto da vaga>
Gere o CV para a vaga ativa
Gere o FERAS para esta vaga
Selecione as habilidades para o Gupy
Crie um draft de email de candidatura
```

O OpenCode carrega `AGENTS.md`, que define a governança, a ordem das skills e os comandos canônicos.

### Intake por texto

Para texto salvo em arquivo:

```bash
npm run intake:paste -- \
  --company "Empresa" \
  --role "Cargo" \
  --text-file /caminho/vaga.txt
```

Para uma URL externa:

```bash
npm run intake:url -- --url "https://exemplo.com/vaga"
```

Para uma vaga do LinkedIn, use o wrapper autenticado do projeto:

```bash
npm run intake:linkedin-job -- --url "https://www.linkedin.com/jobs/view/<id>/"
```

Não use navegador genérico, `curl` ou a API do LinkedIn para substituir esse fluxo.

### CLI estruturada

```bash
npm run career -- workflow summary
npm run career -- applications list-active
npm run context:doctor
```

Os aliases `npm run ...` disponíveis estão definidos em [package.json](package.json).

## Fluxo de candidatura

1. Faça o intake da vaga e persista a descrição.
2. Preencha e valide o `FIT_MAP` da mesma candidatura.
3. Finalize o mapa, registre keywords e gere os derivados necessários.
4. Gere o artefato pedido, como CV, FERAS ou carta.
5. Execute os gates objetivos de validação e revisão.
6. Faça a entrega ou atualização externa somente com a autorização adequada.

Para processamento automático:

```bash
npm run applications:config
npm run applications:heartbeat -- --dry-run --max-per-run 1
npm run applications:agent-heartbeat -- --max-per-run 3
```

O heartbeat não envia emails automaticamente e não deve marcar uma candidatura como `Aplicação Feita`; o envio real permanece sob controle do candidato.

## Integrações

### Notion

O acesso é feito exclusivamente pelos scripts locais. Exemplos:

```bash
npm run notion:list
npm run notion:templates
npm run notion:link-record -- <id>
npm run notion:memory:sync -- --refresh missing
```

Criação e atualização de páginas exigem pedido explícito, salvo o caminho de manutenção de governança documentado no projeto.

### Gmail

O sistema cria drafts, nunca envia emails automaticamente:

```bash
npm run gmail:auth
```

O draft real só deve ser criado depois da revisão textual e da aprovação explícita do usuário.

### OneDrive via rclone

A entrega de CV usa `RCLONE_ONEDRIVE_REMOTE` e `RCLONE_ONEDRIVE_DELIVERY_DIR`. Para CVs personalizados, o destino canônico é `01_armel/Curriculos/personalizados`. Consulte [RCLONE_ONEDRIVE_DELIVERY.md](RCLONE_ONEDRIVE_DELIVERY.md).

## Testes e validações

```bash
npm test
npm run validate:structure
npm run runtime:verify -- --strict
```

Para investigar o estado local:

```bash
npm run workflow:summary
npm run context:doctor
npm run local:strict:doctor
npm run applications:doctor-concurrency
```

## Segurança e dados locais

- nunca commite `.env`, tokens OAuth, chaves, bancos SQLite ou dumps do Notion;
- não coloque descrições de vagas, histórico pessoal ou documentos em issues;
- não edite `career.db`, FIT_MAP ou receipts para contornar um gate;
- use os comandos oficiais para reset, migração, handoff e entrega;
- mantenha uma única cópia autoritativa do workspace executando as células;
- trate bloqueios de credencial, sessão ou autoridade como bloqueios reais.

O `.gitignore` exclui estado, inbox, outputs, workspaces, sessões e credenciais locais por desenho.

## Documentação

- [AGENTS.md](AGENTS.md): governança e regras operacionais canônicas;
- [COMO_USAR.md](COMO_USAR.md): manual detalhado de operação;
- [HARNESS_ARCHITECTURE.md](HARNESS_ARCHITECTURE.md): roteamento e isolamento;
- [TECHNICAL_BRIEF_AGENT_PIPELINE_V2.md](TECHNICAL_BRIEF_AGENT_PIPELINE_V2.md): pipeline celular e artefatos;
- [LINKEDIN_AUTH_RUNBOOK.md](LINKEDIN_AUTH_RUNBOOK.md): autenticação do LinkedIn;
- [TELEGRAM_HARNESS_RUNBOOK.md](TELEGRAM_HARNESS_RUNBOOK.md): operação via Telegram;
- [docs/roadmap.md](docs/roadmap.md): backlog técnico e evidências de execução;
- [.agents/skills/](.agents/skills/): workflows especializados.

## Licença

Consulte o arquivo de licença do repositório antes de reutilizar o código.