# Especificação: integração do runtime celular — Fase C

**Data:** 2026-08-13  
**Baseline:** `ARCH-DATA-ANCHORED-2026-08-13`  
**Mudança:** `CHG-0005`  
**Status:** aprovada para planejamento de implementação

## Decisão

A Fase C consolidará o caminho celular já existente em `applications_v2` com o
control plane implementado na Fase B. O heartbeat continuará selecionando as
candidaturas, mas a execução de cada célula usará os inputs e o request
persistidos no SQLite, o Harness fará o isolamento do processo e o
`CellExecutor` fará a publicação/validação terminal.

O piloto inicial usará um runner controlado de teste. Ele terá o mesmo contrato
do `SubprocessAgentRunner`, iniciará um processo novo para cada etapa e produzirá
um FIT_MAP draft determinístico somente no allowlist da tentativa. O piloto
provará a topologia e os gates sem depender de `opencode`, Hermes ou de uma
sessão Telegram disponível no ambiente.

## Estado encontrado

O repositório já possui:

- `_run_cellular_heartbeat` e `_process_cellular_application` para a fila;
- `HarnessSupervisor.run_application_stage` e `SubprocessAgentRunner`;
- `CellExecutor.prepare_ready_node`, `run_ready` e leases de workspace;
- `cell_inputs`, `cell_requests`, `cell_handovers` e `validation_receipts` da
  Fase B.

A lacuna é que `_write_cellular_analyze_request` ainda cria uma projeção própria
em arquivos, sem consultar o `CellRequestBuilder` persistido. O Harness também
registra o processo, mas não registra a sessão no `runtime_runs` nem verifica a
identidade/hash do request SQLite antes do runner.

## Escopo

### Dentro

1. Fazer o heartbeat usar o request celular gerado a partir de
   `cell_requests`/`cell_inputs`.
2. Registrar worker, run, sessão, métricas bounded e status do runner em
   `runtime_control`.
3. Fazer o Harness validar identidade da candidatura, run, tentativa, hash do
   request e allowlists antes de iniciar o processo.
4. Adicionar um runner controlado de teste que respeite o contrato de processo
   novo, não aceite `resume` e escreva somente o output permitido.
5. Executar um piloto ponta a ponta `normalize_job → analyze_fit → compose_cv`
   ou, quando o ambiente não possuir os recursos de CV, até `analyze_fit` com
   publicação e handover verificáveis.
6. Registrar evidência em `CHG-0005` e atualizar a matriz sem marcar Telegram
   como integrado.

### Fora

- ativar o runner real dos bots sem o binário/configuração correspondente;
- conectar o gateway Telegram diretamente ao pipeline nesta fase;
- migrar bancos Hermes ou candidaturas existentes;
- executar ações externas de Notion, OneDrive ou Gmail no piloto;
- alterar os três arquivos sujos preexistentes do workspace.

## Fluxo aprovado

```text
heartbeat
  → reserva run/node/attempt no SQLite
  → registra cell_inputs
  → gera cell_requests + request.json/request.md
  → RuntimeControl inicia runtime_run
  → Harness valida identidade, hashes e allowlists
  → runner controlado em processo novo, sem resume
  → output somente no staging/allowlist
  → CellExecutor valida e publica
  → handover + validation_receipts + artifacts + status terminal
  → RuntimeControl finaliza runtime_run
```

O agente não receberá histórico Telegram nem o payload completo da candidatura.
O arquivo de request conterá referências, hashes, contrato, limites e objetivo
da célula. O conteúdo grande continuará sendo lido somente pelos caminhos
explicitamente autorizados.

## Contratos principais

### Runner controlado

```python
class ControlledAgentRunner:
    def run(self, request: AgentRunRequest) -> AgentRunResult: ...
```

O runner criará um subprocesso Python efêmero com `-m career...` ou um script
controlado equivalente, receberá apenas o caminho do request e uma operação
declarada, e retornará `command`, `returncode`, `stdout` e `stderr`. A operação
de teste só poderá criar o arquivo de draft previsto no request; qualquer
tentativa fora do allowlist deverá resultar em isolamento bloqueado.

### Runtime observability

Cada execução deverá registrar:

- `worker_id`, `run_id`, `application_id`, `node_id` e `session_id`;
- request bytes/hash e status do processo;
- observações bounded de contexto, chamadas e duração;
- erro resumido quando houver falha.

Não serão registrados prompt completo, histórico de conversa ou stdout ilimitado
no SQLite. Logs continuam em arquivos de execução com caminhos auditáveis.

### Sem fallback monolítico

Se o runner controlado ou real estiver indisponível, o resultado será
`awaiting_agent`/`blocked` com motivo persistido. O heartbeat não poderá chamar
`processe-a-vaga` nem iniciar o gateway Hermes como fallback da célula.

## Falhas e recuperação

- request/hash divergente: bloquear antes do subprocesso;
- allowlist inválida: bloquear antes do subprocesso;
- subprocesso com exit code diferente de zero: finalizar runtime como erro e
  devolver a tentativa para estado reparável, sem liberar dependentes;
- output fora do allowlist: Harness bloqueia e não publica;
- perda de lease: não permitir commit terminal nem publicação autorizada;
- reinício após falha: reler o mesmo `run_id`/tentativa ou criar nova tentativa
  segundo as regras existentes, sem criar runs infinitos.

## Verificação

Os testes devem cobrir:

1. request celular originado do SQLite, não de payload paralelo;
2. processo novo e ausência de `resume` no comando;
3. runner controlado escrevendo output permitido;
4. tentativa de escrita fora do allowlist sendo bloqueada;
5. `runtime_runs` e `runtime_observations` registrados;
6. publicação de handover/recibo antes da próxima célula;
7. falha do runner sem fallback monolítico;
8. piloto ponta a ponta em workspace temporário, com dois workers/candidaturas
   quando a fixture permitir.

O piloto será considerado aprovado somente com evidência de consulta ao SQLite,
arquivos de request, isolamento do Harness, processo novo e status terminal do
run. Isso não promoverá automaticamente `ARCH-06` para verificado: Telegram
continua fora do escopo.
