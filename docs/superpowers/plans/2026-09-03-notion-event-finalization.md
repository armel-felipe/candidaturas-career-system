# Notion event finalization

## Objetivo

Corrigir a divergência em que a escrita do Notion era concluída, mas o
dispatcher classificava o turno como `dispatch_worker_missing_reply`, e evitar
novos blocos duplicados quando a mesma análise fosse reenviada.

## Escopo

- gerar uma confirmação determinística para `notion-update` concluído sem texto;
- recuperar `application_id`, `run_id` e `node_id` do request persistido do especialista;
- tornar o append da análise idempotente por comparação da sequência de blocos;
- preservar os blocos históricos já existentes no Notion;
- validar com testes focados, suíte completa e runtime dos dois containers.

## Evidência

- Caso reproduzido: `returncode=0`, `status=written`, aprovação consumida e
  executor `completed`, enquanto o dispatch externo registrava
  `dispatch_worker_missing_reply`.
- O registro 624 foi lido sem nova escrita e mantém a página correta.
- Teste red primeiro: dois casos falharam antes da implementação.
- Testes focados após a implementação: `40 passed`.
- Suíte completa após a implementação: `845 passed`, 3 warnings de depreciação
  já conhecidos.

## Estado

- [x] Reproduzir falha de resposta vazia.
- [x] Implementar fallback de resposta e propagação de escopo.
- [x] Implementar detecção de sequência de análise já presente.
- [x] Executar testes focados e suíte completa.
- [x] Publicar e validar nos dois containers.

## Publicação

- Commit: `2c573ce fix: finalize Notion events without duplicate analysis`.
- `vagas_bot_01` e `vagas_bot_02`: `running`, `restarts=0`, Telegram `connected`.
- Probes nos dois containers: confirmação de Notion e escopo `notion_624/run-624/notion-update`.
- `npm run runtime:verify -- --strict`: `blockers=[]`.
