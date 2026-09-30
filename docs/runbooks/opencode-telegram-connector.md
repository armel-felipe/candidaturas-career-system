# Runtime Telegram: Hermes e OpenCode

## Estado atual

O modo selecionado é `opencode`: `vagas_bot_02` atende pelo conector e
`opencode serve` escuta apenas em `127.0.0.1:4196`. O container do
`vagas_bot_01` está parado; a configuração Hermes foi preservada. O serviço
`candidaturas-runtime` restaura o último modo selecionado após reboot.

## Selecionar um runtime

Execute no VPS como root (ou via `sudo`):

```bash
python3 scripts/agent_runtime_select.py status
python3 scripts/agent_runtime_select.py select opencode
python3 scripts/agent_runtime_select.py select hermes
```

O seletor verifica o serviço observado, o schema e os registros do banco SQLite
de runs celulares, o estado de sessão do OpenCode e atividade recente do Hermes.
Estados desconhecidos ou uma run ativa impedem a troca. As units
`opencode-telegram-connector` e `candidaturas-hermes-bot` também verificam o
gateway oposto antes de iniciar. Uma falha ao iniciar OpenCode para o conector
e tenta restaurar Hermes.

Use somente `candidaturas-runtime select ...` para alternar. Inícios via
systemd das duas units são guardados contra o gateway oposto ativo. Comandos
Docker diretos e outros processos `opencode serve` não passam por esses guards;
não os use enquanto um runtime estiver selecionado.
Para verificar após reboot, use `systemctl status candidaturas-runtime` e o
comando `status` acima.

## Conversa Telegram e sessão OpenCode

No modo `opencode`, envie `/projects` a `vagas_bot_02` e vincule a conversa ao
único alias disponível, `candidaturas`. Use `/new` para iniciar uma sessão ou
`/sessions` para escolher uma já existente. `/status` mostra a sessão atual.

No terminal SSH conectado ao mesmo VPS, anexe ao servidor e à sessão exibida
pelo bot:

```bash
opencode attach http://127.0.0.1:4196 --dir /opt/agent-projects/candidaturas --session <SESSION_ID>
```

Não execute outro `opencode` sem `attach` durante o modo OpenCode. O servidor
carrega o `opencode.json` e o `AGENTS.md` da raiz canônica do projeto.

## Serviços e logs

```bash
systemctl status candidaturas-runtime opencode-telegram-connector
journalctl -u opencode-telegram-connector -f
ss -lntp | grep ':4196'
```

A porta `4196` deve aparecer somente em `127.0.0.1`. Token e estado do
conector ficam em `/etc/opencode-telegram-connector*` e
`/var/lib/opencode-telegram-connector`, fora do Git e da árvore do projeto.
O token é entregue à unit como systemd credential, sem variável de ambiente
herdada pelo processo `opencode serve`.

## Recuperação

- `selected=...` diferente dos serviços observados: não inicie serviços à mão;
  inspecione o estado e use o seletor para recuperar o modo pretendido.
- `active_cell_runs` ou `recent_hermes_activity`: aguarde a execução terminar e
  repita a seleção.
- `active_opencode_sessions`: aguarde as sessões concluírem e repita.
- `opencode_session_status_unavailable`: mantenha o runtime atual; confira o
  serviço e os logs antes de nova tentativa.
- Falha na ativação do OpenCode: o seletor interrompe o conector e tenta
  restaurar Hermes. Confirme o modo com `status` antes de continuar.

O seletor ignora registros SQLite `running` anteriores à geração atual do
runtime. Neste host, os registros antigos precedem a inicialização atual do
container Hermes e as reservas estão expiradas; eles são preservados e não são
reescritos pela instalação.
