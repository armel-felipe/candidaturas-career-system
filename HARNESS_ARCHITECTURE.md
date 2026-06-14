# Arquitetura Harness Puro

## Porta de entrada

Toda mensagem de usuario deve entrar por:

```bash
npm run harness -- --message "<mensagem>" --channel <cli|telegram|codex|opencode>
```

Para classificar sem executar:

```bash
npm run harness:route -- --message "<mensagem>" --channel <canal>
```

`HarnessSupervisor` e a fonte unica de roteamento. Os comandos antigos continuam disponiveis,
mas os aliases de agente, heartbeat e status delegam ao supervisor.

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
