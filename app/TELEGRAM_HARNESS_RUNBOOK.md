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

Para o canary da Fase D, o staging seguro continua restrito ao profile `vagas_bot_01`:

```bash
./scripts/python.sh scripts/phase_d_canary.py preflight --compose deploy/hermes/compose.yaml --bot vagas_bot_01 --json
./scripts/python.sh scripts/phase_d_canary.py rollback-dry-run --compose deploy/hermes/compose.yaml --bot vagas_bot_01 --json
./scripts/python.sh scripts/phase_d_canary.py runner-probe --compose deploy/hermes/compose.yaml --bot vagas_bot_01 --json
```

No host atual, o `preflight` permanece `blocked` sem mutacoes: o compose resolve
`vagas_bot_01`, abre o SQLite em read-only e valida o contrato completo de
autoridade (`control_db_id`, `ledger_id`, `authority_epoch`,
`storage_identity`). O alvo canônico resolvido pelo compose é
`hermes/vagas_bot_01/config.yaml`. Mesmo assim, o gate continua `blocked`
porque o authority ledger do state root real continua ausente/inválido e
`CAREER_CONTROL_DB_ID` não está presente no ambiente.

O `rollback-dry-run` nao escreve nada, nao provisiona autoridade, nao chama
`processe-a-vaga` e serve apenas para verificar se existe backup reaproveitavel
para rollback. No host atual ele retorna `dry_run_ok` com `revertible=false`,
ou seja: o alvo continua restrito a `vagas_bot_01`, mas ainda nao existe backup
aproveitavel para restauracao.

O `runner-probe` continua `blocked` enquanto nao houver evidencias canonicas
coerentes de D0-D2 e um runner real disponivel; quando ele retornar comando de
request, o prompt deve permanecer redigido (`<request prompt redacted>`).
Enquanto esse gate real nao atravessar o Harness com runner disponivel,
`ARCH-06` permanece `divergente` e o canary nao pode ser declarado concluido.

O target real do canary e o `config.yaml` efetivamente consumido pelo Hermes no
mount host de `/opt/data/profiles/vagas_bot_01`, com backup correspondente em
`config.yaml.bak.harness`.

## Instalar

```bash
./scripts/python.sh scripts/install_hermes_harness_hook.py --apply
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes hooks list
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes hooks doctor
```

No fluxo genérico legado acima, o instalador cria `config.yaml.bak.harness`
antes da alteracao. No canary da Fase D, o wrapper resolve pelo compose o path
host exato de `vagas_bot_01/config.yaml`, exige que ele coincida com o target
calculado para `vagas_bot_01`, cria `config.yaml.bak.harness` antes da escrita
e tambem instala o plugin em `vagas_bot_01/plugins/career-harness-output`.
Ele tambem instala e habilita o plugin `career-harness-output`, usado pelo hook
`transform_llm_output` para impedir que o modelo resuma, escolha ou reescreva menus.
O apply so deve apontar para o config exato de `vagas_bot_01`; qualquer target de
`vagas_bot_02` deve ser rejeitado pelo wrapper de canary.

Para o fluxo canonico da Fase D, os entrypoints `preflight`, `stage-hook` e
`controlled-run` gravam evidencias compactas e atomicas em
`.career-state/phase_d_gates/`, e o D3 consome apenas o manifesto derivado
`.career-state/phase_d_runner_gate.json`. Se D0, D1 ou D2 estiverem
`blocked`, o manifesto nao pode marcar `approved=true`.

## Restart manual separado

O staging D1 nunca reinicia o gateway automaticamente. Se o apply foi validado e voce
decidir aceitar a mudanca no canary, o restart continua sendo um passo manual e separado:

```bash
HERMES_HOME="$HOME/.hermes/profiles/vagas" hermes gateway restart --accept-hooks
```

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
smoke_root=$(mktemp -d /tmp/phase-d-fixture-XXXXXX) && ./scripts/python.sh scripts/phase_d_canary.py route-smoke --root "$smoke_root" --message-id d1-1 --message "status das candidaturas" --route-only
./scripts/python.sh scripts/phase_d_canary.py route-smoke --message-id d1-1 --message "status das candidaturas" --route-only
```

No terceiro comando acima, a CLI cria um root efemero novo por execucao.
Nao reutilize um root fixo se quiser observar o primeiro passe `deduplicated=false`
seguido do replay `deduplicated=true`.

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
