# Arquitetura Harness Puro

## Porta de entrada

Para o usuario, a porta de entrada e sempre uma mensagem em linguagem natural no
Codex, OpenCode, Hermes ou Telegram. Ele nunca precisa executar os comandos abaixo.

Internamente, cada interface encaminha a mensagem por:

```bash
npm run harness -- --message "<mensagem>" --channel <cli|telegram|codex|opencode>
```

Para classificar sem executar:

```bash
npm run harness:route -- --message "<mensagem>" --channel <canal>
```

`HarnessSupervisor` e a fonte unica de roteamento. Os comandos antigos continuam disponiveis,
mas os aliases de agente, heartbeat e status delegam ao supervisor.

## Menu inicial

O supervisor agora pode responder a pedidos como `menu`, `opcoes`, `nova sessao` e
`o que posso fazer` com um menu estruturado de entrada.

Objetivo do menu:

- reduzir atrito na abertura de uma sessao nova;
- expor os atalhos canonicos ja existentes;
- variar conforme exista ou nao uma vaga ativa em `.career-state/workflow_state.json`.

Sem vaga ativa, o menu prioriza:

- ver vagas salvas no LinkedIn;
- avaliar vaga do Notion por ID;
- avaliar vaga do LinkedIn por URL;
- colar nova vaga para analise.

Com vaga ativa, o menu prioriza:

- retomar trabalho em andamento;
- continuar analise da vaga ativa;
- gerar CV;
- gerar pitch / FERAS;
- gerar carta;
- gerar habilidades ATS/Gupy;
- atualizar ou criar vaga no Notion;
- trocar para outra vaga por LinkedIn, Notion ou texto colado.

Formato esperado do retorno:

```json
{
  "status": "completed",
  "kind": "session_menu",
  "menu_context": "active_job|no_active_job",
  "headline": "...",
  "active_intake": {
    "company": "...",
    "role": "...",
    "next_required_step": "..."
  },
  "sections": [
    {
      "id": "new_job_sources",
      "title": "Entradas de vaga",
      "items": [
        {
          "id": "linkedin_saved_jobs",
          "title": "Ver vagas salvas no LinkedIn",
          "description": "...",
          "prompt": "listar minhas vagas salvas",
          "recommended": true
        }
      ]
    }
  ]
}
```

Comportamento adicional:

- o payload inclui `display_text`, pronto para CLI/Telegram;
- o supervisor persiste `.career-state/harness/menu_state.json` com as opcoes numeradas do ultimo menu;
- respostas curtas como `1`, `2` ou `3` resolvem a intencao correspondente do ultimo menu exibido;
- se a intencao depender de ID, URL ou texto, o supervisor persiste `pending_input.json` e pede somente esse dado;
- exemplos de parametro nunca sao executados como valores reais;
- uma opcao completa, como vagas salvas, executa o workflow em vez de apenas exibir um comando.

## Fluxo

```text
canal
  -> HarnessSupervisor.classify
  -> intake ou request especialista
  -> processo novo do runner
  -> guard de outputs
  -> gates locais
  -> proxima etapa, aprovacao ou resposta
```

O modelo nao e fonte de estado. Estado, memoria e resultados ficam no filesystem.

## Especialistas

- `fit-map-agent`: grava apenas o draft analitico.
- `cv-agent`: produz conteudo, DOCX e relatorios de aprovacao.
- `cover-letter-agent`: produz carta local.
- `feras-agent`: produz FERAS e pitch.
- `habilidades-agent`: produz arquivos separados para Gupy e Mercado Livre.
- `notion-agent`: prepara dry-run e aguarda aprovacao.
- `email-agent`: prepara preview/dry-run e aguarda aprovacao.
- `linkedin-agent`: extrai e persiste a descricao usando sessao autenticada.

`analyze`, `generate` e `repair` do heartbeat usam o mesmo supervisor e iniciam um processo
novo por etapa.

## Requests e memoria

Requests automaticos por candidatura:

```text
.career-state/applications_v2/<ID>/requests/<run_id>/
  manifest.json
  request.json
  request.md
  result.json
  validation.json
  stdout.log
  stderr.log
```

Requests manuais:

```text
.career-state/agent_requests/runs/<request_id>/
```

Cada request define objetivo, inputs compactos, outputs permitidos, comandos e validacoes.
Arquivos longos entram somente como fallback.

## Runners

Os runners suportados sao:

```yaml
analysis_runner:
  kind: hermes
  command: hermes
  timeout_minutes: 90

generation_runner:
  kind: codex
  command: codex
  timeout_minutes: 90
```

Valores aceitos para `kind`: `hermes`, `opencode` e `codex`.

Codex usa `codex exec --ephemeral`, portanto cada tarefa recebe uma sessao nova.
Hermes usa oneshot sem `--resume`. OpenCode usa `opencode run`.

## Isolamento

O projeto aplica:

- lock exclusivo do heartbeat;
- processo novo por tarefa;
- requests imutaveis por `run_id`;
- deteccao de escrita fora dos outputs permitidos;
- bloqueio de FIT_MAP stale;
- aprovacao persistida para Notion e Gmail;
- deduplicacao de mensagens Telegram.

O guard detecta mutacoes, mas nao substitui sandbox do sistema operacional. Para maior
isolamento, use Codex com `workspace-write` ou um runner em container.

## Aprovacoes

Notion e Gmail criam registros em:

```text
.career-state/approvals/<approval_id>.json
```

Para aprovar:

```bash
npm run harness:approve -- <approval_id>
```

Para executar a acao aprovada:

```bash
npm run harness:execute-approval -- <approval_id>
```

Somente comandos Notion em whitelist e criacao de draft Gmail sao aceitos. Email nunca e enviado.
