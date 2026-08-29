# Plano de correção — perfil Hermes no subprocesso celular

Plano: `2026-08-28-cellular-profile-env` — concluído em 2026-08-28.

## Diagnóstico confirmado

- `hermes/vagas_bot_01/.env` contém a entrada de credencial do Ollama e é
  montado no container como `/opt/data/profiles/vagas_bot_01/.env`.
- O gateway é iniciado com `--profile vagas_bot_01`, portanto carrega o
  diretório e o `.env` do perfil.
- `SubprocessAgentRunner` iniciava o agente celular apenas como
  `hermes --accept-hooks -z ...`, sem `--profile`. Com `HERMES_HOME=/opt/data`,
  o novo processo procurava `/opt/data/.env`, que não existe.
- O erro `No usable credentials found for provider 'ollama-cloud'` era,
  portanto, um erro de seleção de perfil, não ausência da credencial no perfil.

## Item do roadmap

- `CELLULAR-006`: encaminhar o nome do perfil Hermes ao subprocesso celular.

## Implementação

1. Adicionar teste regressivo que exija `--profile <nome>` no comando Hermes
   quando `CAREER_HERMES_PROFILE_NAME` estiver presente.
2. Alterar o runner para aceitar perfil explícito do request/configuração e
   usar `CAREER_HERMES_PROFILE_NAME` como fallback seguro.
3. Declarar `CAREER_HERMES_PROFILE_NAME` nos serviços `vagas_bot_01` e
   `vagas_bot_02` dos dois compose canônicos.
4. Validar sem imprimir segredos: presença da entrada no `.env` do perfil,
   ausência de chave em `config.yaml`, comando gerado com o perfil correto e
   execução do canário até o provedor.

## Evidência de execução

- `hermes/vagas_bot_01/.env` e `hermes/vagas_bot_02/.env` foram confirmados
  com a entrada de credencial sem expor o valor.
- O teste regressivo verifica que o comando celular contém o perfil explícito
  e que um perfil informado no request vence o fallback do ambiente.
- Os dois compose canônicos declaram `CAREER_HERMES_PROFILE_NAME`.
- 26 testes focados, `validate:structure` e `git diff --check` passaram.

## Critério de saída

O subprocesso celular iniciado por cada bot deve resolver o mesmo perfil usado
pela sessão Telegram, carregar o `.env` daquele perfil e não procurar a raiz
`/opt/data/.env`. Nenhum segredo deve ser adicionado a YAML, código, comando,
log ou manifest.
