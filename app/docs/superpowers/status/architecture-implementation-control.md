# Controle de implantação da arquitetura

**Baseline:** `ARCH-DATA-ANCHORED-2026-08-13`
**Especificação:** [`2026-08-13-data-anchored-cellular-orchestration.md`](../specs/2026-08-13-data-anchored-cellular-orchestration.md)
**Atualizado em:** 2026-08-14
**Responsável pelo controle:** projeto Career Job Application System

## Finalidade

Este documento controla a diferença entre a arquitetura aprovada e o que está
realmente implantado. A existência de classes, tabelas, skills ou testes não é
suficiente para marcar um item como implantado: é necessário provar que o caminho
de produção o utiliza.

## Estados permitidos

| Estado | Significado |
|---|---|
| `não iniciado` | não há implementação relevante ou evidência suficiente |
| `desenhado` | existe especificação, mas não há implementação utilizável |
| `parcial` | parte do contrato existe, mas há lacunas conhecidas |
| `implementado não integrado` | código e testes existem, mas o caminho real não o utiliza |
| `em validação` | integrado em ambiente controlado, aguardando evidência final |
| `verificado` | implementação integrada, evidência de runtime e gates aprovados |
| `bloqueado` | há impedimento objetivo que impede avanço |
| `divergente` | o comportamento real contradiz a arquitetura aprovada |
| `substituído` | item retirado por mudança de baseline aprovada |

## Regra de evidência

Um item só pode avançar para `verificado` quando o registro contiver:

1. arquivos ou módulos responsáveis;
2. teste(s) automatizado(s) relevante(s);
3. comando(s) executado(s) e resultado observado;
4. evidência do caminho de produção, quando o item for de integração;
5. data, commit ou identificador de mudança;
6. limitações remanescentes, se houver.

Testes unitários podem provar um contrato local. Não provam, sozinhos, que o
gateway, o heartbeat ou os dois bots estão usando esse contrato.

## Matriz de conformidade inicial

| ID | Requisito da arquitetura aprovada | Estado inicial | Evidência atual | Lacuna para verificação |
|---|---|---|---|---|
| `ARCH-01` | Cada célula inicia sessão nova, sem `resume` | `em validação` | `SubprocessAgentRunner` implementa runner controlado em processo Python novo; piloto não contém `resume` | validar o mesmo contrato com os runners reais dos bots |
| `ARCH-02` | SQLite compartilhado é a autoridade operacional | `em validação` | `CAREER_CONTROL_DB_PATH` e mount comum foram configurados; control plane vazio provisionado em `/opt/agent-projects/candidaturas/control-plane/career.db` | autoridade/ledger e migração controlada ficam para fases posteriores |
| `ARCH-03` | Inputs da tentativa são registrados antes do agente | `em validação` | Fase C usa `CellRequestBuilder` persistido e piloto registrou `cell_inputs=1` antes do Harness | runner/gateway externo ainda não está integrado |
| `ARCH-04` | Handover e outputs são publicados antes da liberação seguinte | `em validação` | piloto registrou `cell_handovers=1`, `validation_receipts=3`, `artifacts=1` e terminou `validated` | publicação em execução real dos bots ainda não foi observada |
| `ARCH-05` | Request do agente é projeção compacta do estado persistido | `em validação` | Fase C materializa somente `cell_requests`; piloto validou hash e rejeitou adulteração | `AgentRequestBuilder` legado e gateway Hermes ainda coexistem |
| `ARCH-06` | Telegram é dispatcher fino | `divergente` | Fase D adicionou D0 read-only com contrato completo de autoridade, evidências canônicas D1/D2 compactas e gate D3 fail-closed; no host real o transporte segue sem prova via Harness | provisionar authority ledger e runner reais para observar Telegram → Harness → célula sobre o `config.yaml` canônico do `vagas_bot_01` |
| `ARCH-07` | `processe-a-vaga` compila para células pequenas | `parcial` | contratos celulares já definem vários nós | impedir o uso direto da skill monolítica no caminho de produção |
| `ARCH-08` | Limite de contexto bloqueia payload excessivo antes do runner | `em validação` | `CellRequestBuilder` rejeita projeção acima de 128 KiB; piloto registrou request bounded e tokens estimados | medição do runner real ainda fica para integração/telemetria |
| `ARCH-09` | Workers são substituíveis e consultam estado comum | `em validação` | caminho comum do control plane e APIs de registro existem; bancos Hermes e estados legados continuam separados | integrar todos os workers e retirar autoridade operacional dos perfis |
| `ARCH-10` | Alterações de código têm registro, testes e impacto | `em validação` | matriz, change log, plano e commits de Fase A existem | aplicar gates automaticamente e registrar evidência de cada execução |
| `ARCH-11` | Falhas bloqueiam ou reparam, sem sessão interminável | `em validação` | adulteração de request, allowlist fora da aplicação e falha do controlled worker bloqueiam sem publicar; runtime termina `blocked` | limite de repetição/contexto no runner externo ainda não integrado |
| `ARCH-12` | Execução completa deixa trilha auditável no SQLite | `em validação` | piloto registrou inputs, request, handover, receipts, artifact, runtime e duas observações no SQLite | gateway e heartbeat reais ainda não estão conectados ao registro celular |

## Como atualizar a matriz

Cada mudança deve atualizar a linha afetada somente depois da verificação
correspondente. A atualização deve registrar o `CHG-ID` do [controle de mudanças](./scope-change-log.md).

Formato mínimo de evidência:

```text
CHG-ID: CHG-0000
Commit: <hash ou working-tree explicitamente identificado>
Arquivos: <paths>
Testes: <comando> → <resultado>
Runtime: <comando/fixture/log> → <resultado>
Estado anterior: <estado>
Estado novo: <estado>
Limitações: <nenhuma ou lista>
Verificado em: <UTC>
```

## Gates de implantação

### Gate 0 — baseline

- a especificação aprovada está identificada por ID e versão;
- a mudança possui registro no change log;
- o escopo e o fora de escopo estão explícitos.

### Gate 1 — implementação local

- o código atende ao contrato da linha;
- testes focados cobrem caminho válido e falhas principais;
- nenhum arquivo fora do escopo foi alterado sem registro.

### Gate 2 — integração

- o dispatcher/heartbeat real chama o componente;
- o runner real recebe somente request celular;
- os perfis Hermes não dependem do histórico da sessão anterior.

### Gate 3 — runtime

- uma execução controlada produz os registros esperados no SQLite;
- outputs, handovers e hashes podem ser consultados;
- a etapa seguinte não começa antes do commit da anterior;
- contexto e número de chamadas ficam dentro do limite.

### Gate 4 — promoção

- evidências dos gates anteriores estão registradas;
- a matriz é atualizada para `verificado`;
- o change log é encerrado;
- o status operacional e as instruções canônicas foram atualizados.

## Regras de interpretação

- `implementado não integrado` nunca pode ser apresentado como conclusão da
  arquitetura.
- Um teste que usa fixture não prova implantação em runtime; deve ser identificado
  como teste de fixture.
- Uma implementação anterior pode permanecer válida como componente, mas ficar
  `divergente` quando o caminho de produção não a utiliza.
- A matriz é um controle de status, não uma autorização para ampliar o escopo.
  Toda ampliação passa pelo change log.

## Evidência da Fase C

| Verificação | Resultado |
|---|---|
| Request SQLite → arquivo celular | `test_phase_c_request_bridge.py`: 2 aprovados; adulteração do JSON rejeitada pelo hash persistido |
| Runtime/Harness/runner | `test_cellular_runtime.py`, `test_phase_c_harness.py` e `test_controlled_agent_runner.py`: 5 aprovados no corte final; processo novo, sem `resume`, allowlist aplicada |
| Piloto controlado | `test_phase_c_pilot.py`: 1 aprovado; `status=completed`, `execution=[validated]`, `runtime=completed` |
| Evidência SQLite do piloto | 1 `cell_inputs`, 1 `cell_requests`, 1 `cell_handovers`, 3 `validation_receipts`, 1 `artifacts`, 1 `runtime_runs`, 2 `runtime_observations` |
| Regressão celular/runtime | comando focal da Fase C: `51 passed`; corte final de runner/Harness/piloto: `5 passed` |
| Limitações | Hermes/opencode reais não estão disponíveis; Telegram, Notion, OneDrive e Gmail permaneceram fora do piloto; os três arquivos sujos preexistentes não foram alterados |

## Evidência da Fase A

| Verificação | Resultado |
|---|---|
| `CAREER_CONTROL_DB_PATH` em ambos os serviços | mesmo caminho de container e mesmo bind mount em `docker compose config` |
| Banco de controle provisionado | `control-plane/career.db`, identidade `control_9c0aceb3a5cf4441abf5417fc55f5ffc` |
| Diagnóstico read-only Hermes | `vagas_bot_01` e `vagas_bot_02` reportados como `ok`, sem conteúdo de mensagens |
| Testes focados da Fase A | 20 aprovados |
| Suíte de regressão disponível sem bloqueios externos conhecidos | 318 aprovados |
| Suíte completa no ambiente atual | 337 aprovados, 15 falhas abertas não atribuídas aos arquivos da Fase A |

Os gateways atuais continuam fora do control plane por design de migração: o
diagnóstico observa seus bancos privados, mas a integração que registrará cada
execução real e os fará iniciar células novas ainda não foi promovida para
`verificado`.

## Evidência da Fase B

| Verificação | Resultado |
|---|---|
| Testes focados de persistência e executor | `47 passed` em `test_cell_contract_persistence.py`, `test_database.py`, `test_cell_store.py` e `test_cell_executor.py` |
| Regressão de células/intake/runtime | `114 passed, 1 deselected`; o caso isolado é o teste legado de aprovação CV bloqueado por `enquadramento.json` ausente |
| Request pré-handler | fixture do executor consultou `cell_inputs` e `cell_requests` antes do handler; `request.json` e `request.md` materializados |
| Commit final | fixture registrou `cell_handovers`, `validation_receipts` com SHA-256 do relatório, artefatos e `validated` na mesma transição; dependente ficou pronto depois |
| Integridade | hash alterado, input vazio posteriormente ampliado, request acima do limite e handover com identidade errada foram rejeitados |
| Suíte completa pós-commit | `344 passed, 15 failed`; as falhas estão fora da Fase B: Node.js ausente, `enquadramento.json` ausente e scripts Windows preexistentes em `.venv-test` |
| Limitações | não prova ainda gateway Telegram, runner externo, medição real de tokens ou produção nos dois bots |

## Evidência da Fase D

| Verificação | Resultado |
|---|---|
| D0 host preflight | snapshot read-only de 2026-08-14 via `run_preflight(...)` contra `deploy/hermes/compose.yaml` → `status=blocked`, `mutations=[]`; o compose resolve `hermes/vagas_bot_01/config.yaml`, lê `control_db_id=control_4b9e3ce0922c4025a32fb950d6c1e55a` e bloqueia corretamente por ledger ausente/inválido, `CAREER_CONTROL_DB_ID` ausente e `authoritative_storage` divergente do storage físico atual |
| D1 rollback/staging | `test_phase_d_canary.py` prova target exclusivo `vagas_bot_01`, backup `config.yaml.bak.harness`, rejeição explícita de `vagas_bot_02` e geração de evidência canônica; no host, `rollback_dry_run(...)` continua apenas preview operacional read-only (`dry_run_ok`, `revertible=false`, `mutations=[]`) |
| D2 canário controlado | `test_phase_d_canary.py` + `test_phase_d_canary_integration.py`: relatório compacto sem `stdout`/`stderr` crus, `request_hash`/allowlists coerentes, `application_id` existente bloqueado sem mutação e snapshot do `bot02` idêntico |
| D3 runner gate | `test_phase_d_runner_gate.py`: manifesto/evidências D0-D2 versionados, estados coerentes, rejeição de `kind=controlled`, fail-closed sem fallback e prompt redigido; sem manifesto canônico ou runner real disponível, o host permanece `blocked` |
| Regressão focal atual da Fase D | `46 passed` em `test_phase_d_canary.py`, `test_phase_d_canary_integration.py` e `test_phase_d_runner_gate.py` |
| Suíte proporcional do plano — histórico preservado | mesmo comando do plano registrou `94 passed` antes desta onda final; a evidência foi preservada na governança |
| Suíte proporcional atual com as novas regressões | o mesmo comando do plano agora executa `107 passed` após a inclusão dos testes de autoridade, manifesto canônico, `config.yaml` e bloqueio de `application_id` existente |
| Limitações | D1/D2 seguem suportados por fixture/teste; D0 continua bloqueado no host por autoridade ausente/inválida e D3 não foi promovido sem runner real, portanto ainda não há evidência real de transporte Telegram → Harness → célula |
