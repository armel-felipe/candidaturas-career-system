---
name: bot-runtime-switch
description: Use when a vagas_bot_01 or vagas_bot_02 runtime must be directed between Hermes and OpenCode, when an agent is stuck awaiting_agent, or when the cellular runner needs a safe per-bot mode change without stopping the Telegram gateway.
compatibility: Requires Python 3.12, the project virtual environment, and the deployed Hermes compose file.
---

# Alternar runtime de um bot

Use esta skill para trocar somente o executor celular de um bot. O Hermes
continua recebendo mensagens do Telegram nos dois modos; OpenCode é executado
como runner da célula dentro do container selecionado.

## Ajuda / Manual de uso

### O que a skill faz

Ela seleciona **um único bot** e configura o executor das células celulares:

- `hermes`: o agente especialista é executado pelo Hermes;
- `opencode`: o agente especialista é executado pelo OpenCode;
- em ambos os casos, o Hermes continua sendo o gateway que recebe Telegram;
- a raiz no host é `/opt/agent-projects/candidaturas` e a mesma raiz aparece
  como `/workspace/candidaturas` dentro do container.

### O que acontece automaticamente

Ao trocar o modo, o comando:

1. valida o bot, o modo e a configuração específica daquele bot;
2. verifica o `career.db` autoritativo e bloqueia se houver célula `running` ou
   `reserved`;
3. salva um backup antes da primeira alteração;
4. ajusta `analysis_runner` e `generation_runner` com agente `build`, timeout,
   perfil e diretório de execução corretos;
5. grava a configuração e o lock de forma atômica;
6. mantém o `.env` intacto, incluindo `NOTION_TOKEN`;
7. deixa a próxima execução de `applications:run --run-agent` usar o runner
   selecionado, preservando o mesmo `application_id` e `run_id`.

Não é necessário reiniciar o Hermes para trocar o runner celular. A skill não
cria candidatura, não cria `run_id`, não executa automaticamente uma vaga e
não copia tokens para a linha de comando.

### Opções disponíveis

| Objetivo | Comando |
|---|---|
| Ver o modo e o lock | `npm run bot:runtime -- --bot vagas_bot_02 --status` |
| Selecionar OpenCode | `npm run bot:runtime -- --bot vagas_bot_02 --mode opencode` |
| Selecionar Hermes | `npm run bot:runtime -- --bot vagas_bot_02 --mode hermes --unlock` |
| Liberar lock sem trocar modo | `npm run bot:runtime -- --bot vagas_bot_02 --unlock` |

Use `vagas_bot_01` ou `vagas_bot_02` no lugar de `vagas_bot_02`, sempre um por
comando. A troca de modo é deliberada: se já houver outro modo travado, use
`--unlock` na mesma troca somente depois de confirmar que é isso que deseja.

### Fluxo completo de teste

```text
status → selecionar modo → planejar a célula → executar com --run-agent →
inspecionar o run → retomar com os mesmos IDs, se necessário → voltar ao modo anterior
```

Depois de selecionar OpenCode, a execução celular continua sendo feita pelo
comando oficial, dentro do bot escolhido:

```bash
docker compose -f app/deploy/hermes/compose.yaml exec -T --user 10000:10000 vagas_bot_02 \
  npm run applications:run -- --application-id <ID> --run-id <RUN_ID> --run-agent
```

Se o run retornar `awaiting_agent`, isso significa que a etapa aguarda o
agente; retome o mesmo par de IDs. Não planeje outra run para contornar o
estado. Use `applications:inspect-run` para descobrir o próximo nó.

### O que fazer quando terminar

Quando não houver célula `running` ou `reserved`, consulte o status e volte a
Hermes se o teste foi temporário:

```bash
npm run bot:runtime -- --bot vagas_bot_02 --status
npm run bot:runtime -- --bot vagas_bot_02 --mode hermes --unlock
```

O lock existe para impedir troca acidental ou concorrente. Não remova os
arquivos `runtime_mode.lock.json`, `runtime_mode.mutex` ou o `career.db` à mão.

## Regra central

Sempre informe exatamente um bot. Nunca edite o `.career-state` global nem
execute `opencode` diretamente na raiz do host. O caminho do projeto no host é
`/opt/agent-projects/candidaturas`; dentro do container ele é
`/workspace/candidaturas`, com estado e outputs isolados por bot.

## Comandos

Execute na raiz `/opt/agent-projects/candidaturas`:

```bash
# selecionar OpenCode para um bot
npm run bot:runtime -- --bot vagas_bot_02 --mode opencode

# voltar para Hermes; --unlock torna a troca deliberada
npm run bot:runtime -- --bot vagas_bot_02 --mode hermes --unlock

# consultar ou liberar o lock explicitamente
npm run bot:runtime -- --bot vagas_bot_02 --status
npm run bot:runtime -- --bot vagas_bot_02 --unlock
```

O comando bloqueia se houver uma célula em `running` ou `reserved`, se outro
modo já estiver travado sem `--unlock`, ou se o bot não for reconhecido. Ele
preserva o `.env` e cria `runtime_mode.config.backup.json` antes da primeira
alteração.

## Testar o modo selecionado

Confirme o binário no bot e use a mesma candidatura e `run_id`:

```bash
docker compose -f app/deploy/hermes/compose.yaml exec -T --user 10000:10000 vagas_bot_02 command -v opencode
docker compose -f app/deploy/hermes/compose.yaml exec -T --user 10000:10000 vagas_bot_02 \
  npm run applications:run -- --application-id <ID> --run-id <RUN_ID> --run-agent
```

O token do Notion permanece no `.env`; não o copie para comandos, config de
runner ou mensagens. Verifique a execução com `applications:inspect-run`.

## Erros comuns

- `runtime_mode_locked`: repetir com `--unlock` somente quando a troca for intencional.
- `active_cell_run`: aguardar a célula terminar; não remover lock manualmente.
- `--unlock` também é bloqueado durante uma célula ativa.
- `awaiting_agent`: retomar o mesmo `application_id` e `run_id`; não criar uma nova run.
