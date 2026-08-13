# Controle de implantação da arquitetura

**Baseline:** `ARCH-DATA-ANCHORED-2026-08-13`
**Especificação:** [`2026-08-13-data-anchored-cellular-orchestration.md`](../specs/2026-08-13-data-anchored-cellular-orchestration.md)
**Atualizado em:** 2026-08-13
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
| `ARCH-01` | Cada célula inicia sessão nova, sem `resume` | `desenhado` | `SubprocessAgentRunner` implementa runners novos | conectar o caminho Telegram/heartbeat ao runner celular |
| `ARCH-02` | SQLite compartilhado é a autoridade operacional | `em validação` | `CAREER_CONTROL_DB_PATH` e mount comum foram configurados; control plane vazio provisionado em `/opt/agent-projects/candidaturas/control-plane/career.db` | autoridade/ledger e migração controlada ficam para fases posteriores |
| `ARCH-03` | Inputs da tentativa são registrados antes do agente | `não iniciado` | requests e manifests existem em arquivos | criar persistência e guard de `cell_inputs` |
| `ARCH-04` | Handover e outputs são publicados antes da liberação seguinte | `parcial` | `CellStore`, manifests e handover existem | execução real atual não registra tentativas/artefatos celulares |
| `ARCH-05` | Request do agente é projeção compacta do estado persistido | `implementado não integrado` | `agent_requests.py` e requests versionados | provar que o gateway não injeta histórico ou skill monolítica |
| `ARCH-06` | Telegram é dispatcher fino | `divergente` | containers iniciam gateway Hermes direto | instalar e validar integração com Harness/CellExecutor |
| `ARCH-07` | `processe-a-vaga` compila para células pequenas | `parcial` | contratos celulares já definem vários nós | impedir o uso direto da skill monolítica no caminho de produção |
| `ARCH-08` | Limite de contexto bloqueia payload excessivo antes do runner | `não iniciado` | há compressão Hermes, não gate de admissão celular | implementar medição, limite e bloqueio pré-runner |
| `ARCH-09` | Workers são substituíveis e consultam estado comum | `em validação` | caminho comum do control plane e APIs de registro existem; bancos Hermes e estados legados continuam separados | integrar todos os workers e retirar autoridade operacional dos perfis |
| `ARCH-10` | Alterações de código têm registro, testes e impacto | `em validação` | matriz, change log, plano e commits de Fase A existem | aplicar gates automaticamente e registrar evidência de cada execução |
| `ARCH-11` | Falhas bloqueiam ou reparam, sem sessão interminável | `parcial` | estados de célula e reparo existem no código | validar no caminho real e adicionar limite de repetição/contexto |
| `ARCH-12` | Execução completa deixa trilha auditável no SQLite | `em validação` | control plane possui schema e tabelas de runtime; diagnóstico mede workers/runs/observações | execuções reais ainda não estão conectadas ao registro celular |

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
