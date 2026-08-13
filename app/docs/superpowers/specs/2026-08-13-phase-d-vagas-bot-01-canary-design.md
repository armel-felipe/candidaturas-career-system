# Especificação: canário de integração do `vagas_bot_01` — Fase D

**Data:** 2026-08-13
**Baseline:** `ARCH-DATA-ANCHORED-2026-08-13`
**Mudança:** `CHG-0006`
**Status:** aprovada para planejamento de implementação

## Objetivo

Validar a integração do caminho real de entrada do `vagas_bot_01` com o
Harness, o control plane SQLite e a execução celular, usando apenas uma
candidatura por vez. O `vagas_bot_02` permanece fora do experimento e não será
alterado nesta fase.

A Fase D não promove imediatamente os dois bots para a nova arquitetura. Ela
cria uma sequência de gates reversíveis para provar primeiro o transporte e a
rota, depois uma execução celular controlada e somente por último o runner real
disponível no ambiente.

## Contexto atual

O projeto já possui:

- `scripts/telegram_harness_adapter.py` para adaptar mensagens do Telegram ao
  `HarnessSupervisor`;
- instalador de hook Hermes com backup do perfil;
- `HarnessSupervisor` e `CellExecutor` integrados ao request celular do SQLite;
- runner controlado usado no piloto da Fase C;
- `vagas_bot_01` e `vagas_bot_02` iniciados atualmente por gateways Hermes
  independentes no `compose.yaml`.

A lacuna é operacional: o gateway ainda pode receber e encaminhar mensagens
diretamente ao modelo sem que o caminho celular seja provado em um perfil real.

## Decisão arquitetural

Adotar o hook por perfil no `vagas_bot_01` como canário. O gateway Hermes
continua responsável pelo transporte Telegram, enquanto o hook encaminha a
mensagem ao adapter/Harness. O Harness decide se a mensagem é conversa,
consulta, intake ou execução de candidatura. O modelo só participa quando o
fluxo determinístico não encerra a tarefa.

O entrypoint do gateway não será substituído. Isso mantém o transporte fora do
orquestrador e permite rollback removendo o hook e restaurando o backup do
perfil.

## Gates de implantação

### D0 — preflight read-only

Validar, sem escrever em perfil ou banco:

- perfil Hermes e `HERMES_HOME` do `vagas_bot_01`;
- presença e saúde do hook/plugin;
- existência do `telegram_harness_adapter.py` e dependências;
- caminho explícito do control plane SQLite;
- `CAREER_CONTROL_DB_ID`, ledger e autoridade do workspace;
- mounts de `.career-state`, `inbox`, `outputs` e control plane;
- disponibilidade do runner configurado;
- ausência de `vagas_bot_02` no conjunto de alvos.

Falha em qualquer item mantém o canário desabilitado e produz um blocker
objetivo. D0 não deve executar candidatura nem alterar configuração.

### D1 — transporte e roteamento

Instalar o hook somente no perfil do `vagas_bot_01`, com backup verificável, e
testar mensagens de baixo risco:

- `status das candidaturas`;
- menu/ajuda;
- `route-only` do adapter;
- mensagem repetida com o mesmo identificador para testar deduplicação.

Critérios: resposta determinística preservada, ausência de recursão do hook,
nenhuma alteração em Notion/OneDrive/Gmail e nenhuma escrita fora dos artefatos
do Harness.

### D2 — canário celular controlado

Selecionar uma única candidatura explicitamente autorizada para o canário.
Executar `analyze_fit` com `kind=controlled`, mantendo:

- uma nova sessão/processo por célula;
- request carregado de `cell_requests`;
- allowlist por tentativa;
- isolamento do Harness;
- `runtime_runs` e `runtime_observations` bounded;
- `cell_inputs`, handover, receipts, artefato e status terminal no SQLite.

O resultado esperado é `validated` ou `blocked`; nunca deve haver fallback para
`processe-a-vaga` ou para uma sessão Hermes longa.

### D3 — runner real, condicionado

Somente após D0, D1 e D2 aprovados, testar o runner real que estiver disponível
no ambiente do canário. O runner deve:

- receber apenas o request celular;
- iniciar processo novo;
- não usar `resume`;
- respeitar o mesmo allowlist;
- registrar runtime bounded;
- falhar fechado se o binário, configuração ou autoridade não forem válidos.

Se o runner real não estiver disponível, D3 permanece `blocked` sem alterar o
estado dos dois bots. O sucesso da Fase D não depende de inventar um runner ou
de contornar a ausência de binário.

## Fluxo operacional

```text
Telegram → gateway Hermes vagas_bot_01
  → hook pre_llm_call
  → telegram_harness_adapter
  → HarnessSupervisor
  → rota determinística / applications:agent-heartbeat
  → CellExecutor + request SQLite
  → runner controlado ou real, em processo novo
  → runtime ledger + isolamento + publicação celular
```

Mensagens comuns podem continuar no modelo do perfil quando o Harness não
encerrar a interação. Tarefas de candidatura não podem ignorar o Harness nem
usar estado global como fonte primária.

## Segurança e rollback

- O alvo de configuração é exclusivamente `vagas_bot_01`.
- Cada instalação de hook cria backup do arquivo do perfil.
- O canário usa uma allowlist explícita de candidatura e não a fila inteira.
- O estado operacional permanece bloqueado quando houver mismatch de banco,
  ledger, identidade, request, allowlist ou runner.
- Rollback: desabilitar/remover o hook do perfil canário, restaurar o backup,
  parar o processamento celular da candidatura canário e preservar os registros
  SQLite para auditoria.
- Não apagar banco Hermes, mensagens Telegram, artefatos ou registros do
  control plane durante rollback.

## Fora do escopo

- alteração ou ativação do `vagas_bot_02`;
- migração dos bancos privados Hermes;
- troca do gateway Telegram por um dispatcher próprio;
- processamento em lote da fila;
- Notion, OneDrive ou Gmail reais no primeiro canário;
- remover imediatamente caminhos legados não celulares;
- afirmar que Telegram está verificado antes de D1/D2/D3.

## Evidências exigidas

Cada gate deve registrar apenas projeções compactas:

- comando e resultado do preflight;
- perfil alvo e backup criado, sem tokens;
- request hash, runtime ID, status e contagens SQLite;
- isolamento e lista de paths alterados;
- candidatura/run/node/attempt;
- blocker objetivo em caso de falha;
- confirmação de que `vagas_bot_02` não foi alterado.

Não registrar no SQLite prompt completo, histórico Telegram, descrição longa da
vaga ou stdout ilimitado.

## Critério de conclusão

CHG-0006 pode ser encerrada somente quando:

1. D0 e D1 forem aprovados no perfil `vagas_bot_01`;
2. D2 produzir uma execução celular controlada com trilha SQLite completa;
3. rollback for testado ou demonstrado por dry-run seguro;
4. D3 for marcado como `verificado` ou `bloqueado` com causa objetiva;
5. `vagas_bot_02` permanecer sem alteração;
6. `ARCH-06` só avançar para `em validação` se houver evidência real do
   transporte pelo Harness; caso contrário, permanecer `divergente`.
