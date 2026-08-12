# Telegram via Harness

## Estado atual

O gateway Hermes do perfil `candidaturas` recebe mensagens Telegram diretamente. Para
fazer todas as mensagens passarem pelo supervisor, use o hook `pre_llm_call` deste projeto.

O hook:

1. recebe a mensagem do gateway;
2. chama `telegram_harness_adapter.py`;
3. deduplica pelo identificador unico do turno, permitindo repetir mensagens como `menu` e `1`;
4. executa `HarnessSupervisor`;
5. quando houver `reply_text`, grava a resposta deterministica por sessao;
6. o plugin `career-harness-output` substitui a saida do modelo por esse texto antes da entrega;
7. nos demais fluxos, injeta o resultado compacto para a resposta final do gateway.

O usuario sempre interage por mensagens. Opcoes de menu que dependem de um dado
abrem uma continuacao conversacional (por exemplo, pedir o ID do Notion ou a URL
do LinkedIn); opcoes completas executam o workflow imediatamente.

Subagentes recebem `CAREER_HARNESS_SUBAGENT=1`, evitando recursao do hook.

## Validar sem alterar o perfil

```bash
./scripts/python.sh scripts/install_hermes_harness_hook.py
```

## Instalar

```bash
./scripts/python.sh scripts/install_hermes_harness_hook.py --apply
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes hooks list
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes hooks doctor
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes gateway restart --accept-hooks
```

O instalador cria `config.yaml.bak.harness` antes da alteracao.
Ele tambem instala e habilita o plugin `career-harness-output`, usado pelo hook
`transform_llm_output` para impedir que o modelo resuma, escolha ou reescreva menus.

## Rodar em uma pasta local

Este perfil e pro projeto `candidaturas` e usa:

- `terminal.cwd: /home/ubuntu/projetos/candidaturas`
- hook `pre_llm_call` apontando para os scripts desse mesmo projeto

Se voce quiser o mesmo stack em outra pasta local, o caminho mais seguro e criar
um segundo profile para essa pasta e instalar o hook de novo a partir dela. Nao
reaproveite este profile mudando apenas a pasta atual do shell, porque o gateway
de Telegram continua lendo o `terminal.cwd` salvo no profile.

## Testar sem Telegram

```bash
npm run harness:telegram -- --message "status das candidaturas" --message-id teste-1 --route-only
```

Remova `--route-only` para executar o workflow.

Para vagas coladas, use cabecalhos explicitos:

```text
Empresa: Nome da empresa
Cargo: Nome do cargo
Analise esta vaga
<descricao completa>
```

Sem `Empresa:` e `Cargo:`, textos longos sao bloqueados antes do FIT_MAP para evitar
reutilizacao acidental da vaga ativa.

## Migrar para outro harness

O Telegram nao depende da implementacao interna do runner. Altere `analysis_runner` e
`generation_runner` em `.career-state/applications_v2/config.json`.

Exemplo Codex:

```yaml
analysis_runner:
  kind: codex
  command: codex
  timeout_minutes: 90
generation_runner:
  kind: codex
  command: codex
  timeout_minutes: 90
```

Depois execute uma vaga por vez e confira os arquivos em
`.career-state/applications_v2/<ID>/requests/`.

Se `hermes gateway status` indicar definicao launchd stale, o gateway ainda pode rodar
como processo de background. Confirme com `pgrep` e pelo log de conexao Telegram antes
de reinstalar o servico.

## LinkedIn em servidor sem XServer

Os comandos autenticados do LinkedIn escolhem automaticamente o modo correto:

- em macOS ou em qualquer ambiente com `DISPLAY`/`WAYLAND_DISPLAY`, abrem browser visivel
- em servidor Linux sem XServer, caem para `headless`

```bash
npm run linkedin:extract:authenticated -- --url "<url-da-vaga>"
npm run linkedin:post:extract:authenticated -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"
```

Se a sessao persistente do browser travar, limpe apenas o estado local do projeto
antes de tentar de novo:

```bash
rm -rf /home/ubuntu/projetos/candidaturas/.career-state/browser/linkedin
```
