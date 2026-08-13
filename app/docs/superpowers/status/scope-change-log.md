# Controle de mudanças de escopo

**Baseline atual:** `ARCH-DATA-ANCHORED-2026-08-13`
**Especificação principal:** [`2026-08-13-data-anchored-cellular-orchestration.md`](../specs/2026-08-13-data-anchored-cellular-orchestration.md)
**Atualizado em:** 2026-08-13

## Finalidade

Este registro impede que decisões novas entrem silenciosamente no projeto e que
uma implementação seja considerada concluída com requisitos diferentes dos que
foram aprovados. Toda mudança relevante deve ter um ID estável e apontar para os
requisitos, arquivos, testes e decisões afetados.

## Categorias

| Categoria | Uso | Exige nova aprovação de baseline? |
|---|---|---:|
| `clarificação` | esclarece texto sem mudar comportamento ou escopo | não |
| `implementação` | escolhe como cumprir requisito já aprovado | não, se não alterar o contrato |
| `adição` | inclui capacidade, requisito ou componente novo | sim |
| `redução` | remove ou adia parte aprovada | sim |
| `desvio` | comportamento diferente do requisito aprovado | sim |
| `correção` | corrige defeito sem mudar o requisito | não |
| `emergencial` | contenção necessária para segurança, dados ou operação | revisão posterior obrigatória |

## Estados

`proposto` → `em análise` → `aprovado` → `em implementação` → `em verificação` →
`concluído`

Estados alternativos: `rejeitado`, `adiado`, `cancelado`, `bloqueado`.

Uma mudança `adição`, `redução` ou `desvio` não pode entrar em implementação
enquanto não estiver `aprovado`.

## Registro de mudanças

| ID | Data | Categoria | Resumo | Requisitos afetados | Estado | Baseline |
|---|---|---|---|---|---|---|
| `CHG-0001` | 2026-08-13 | `adição` | Adotar execução celular ancorada em dados, SQLite como autoridade e sessão nova por célula | `ARCH-01` a `ARCH-12` | `aprovado` | `ARCH-DATA-ANCHORED-2026-08-13` |
| `CHG-0002` | 2026-08-13 | `adição` | Criar matriz de conformidade e controle formal de mudanças de escopo | controle de governança | `aprovado` | `ARCH-DATA-ANCHORED-2026-08-13` |
| `CHG-0003` | 2026-08-13 | `implementação` | Executar Fase A: caminho explícito do control plane, registros bounded de runtime e diagnóstico Hermes read-only | `ARCH-02`, `ARCH-09`, `ARCH-10`, `ARCH-12` | `concluído` | `ARCH-DATA-ANCHORED-2026-08-13` |

### Evidência de CHG-0003

- Commits: `b1ede05`, `b98d76c`, `2ba3860`, `a5ecdc4`.
- Foco: caminho explícito do SQLite, schema/API de observabilidade, diagnóstico
  Hermes read-only e consumo do caminho compartilhado pelo status celular.
- Testes focados: 20 aprovados.
- Suíte sem os cinco grupos já bloqueados por ambiente/contrato pré-existente:
  318 aprovados.
- Suíte completa: 337 aprovados e 15 falhas abertas; nenhuma falha adicional foi
  atribuída aos arquivos da Fase A. As falhas estão registradas no handoff da
  Fase A e incluem Node.js ausente, scripts Windows na fixture `.venv-test`,
  contrato de `enquadramento.json` ausente em testes legados e uma integração
  celular de CV que bloqueia por esse mesmo contrato.
- Runtime: `/tmp/phase_a_runtime_diagnosis_ready.json` registrou o control plane
  como `ready`, os dois perfis Hermes como `ok`, 55/57 sessões e 12.534/15.703
  mensagens, sem conteúdo de mensagem no relatório.

Limitação aceita nesta mudança: os gateways Telegram ainda não registram cada
execução no control plane nem usam o executor celular. Isso permanece divergente
e é escopo das fases de integração posteriores.

## Template para nova mudança

Copiar este bloco para uma nova linha e completar antes de alterar o escopo:

```yaml
change_id: CHG-0000
date_utc: YYYY-MM-DD
requester: <nome ou agente>
category: clarification|implementation|addition|reduction|deviation|correction|emergency
title: <título curto>
summary: <o que muda>
reason: <por que a mudança é necessária>
affected_requirements:
  - ARCH-00
affected_files: []
scope_in:
  - <o que passa a fazer parte>
scope_out:
  - <o que continua fora>
context_impact: none|low|medium|high
data_integrity_impact: none|low|medium|high
runtime_impact: none|low|medium|high
backward_compatibility: none|low|medium|high
alternatives_considered: []
decision: proposed|approved|rejected|deferred|cancelled
approver: <responsável pelo projeto>
implementation_plan: <link para plano>
verification_plan: <testes e runtime esperados>
rollback_plan: <como desfazer ou conter>
implementation_commit: <hash ou não iniciado>
verification_evidence: []
final_status: proposed|in_progress|verified|blocked|superseded
```

## Critério para aprovação

Uma mudança de escopo só deve ser aprovada quando for possível responder:

1. Qual requisito ou limite existente ela altera?
2. Por que o baseline atual não é suficiente?
3. Qual é o impacto no contexto dos agentes, no SQLite e no runtime?
4. O que não será feito por causa dessa decisão?
5. Como a mudança será testada e revertida?

## Relação com implementação

O change log não substitui o plano técnico. O fluxo obrigatório é:

```text
mudança proposta
  → análise de impacto
  → aprovação ou rejeição
  → plano de implementação
  → execução
  → evidências
  → atualização da matriz de arquitetura
  → encerramento da mudança
```

Se a implementação revelar que o requisito aprovado não é viável, deve abrir uma
mudança `desvio` ou `redução`. Não é permitido alterar a especificação aprovada
silenciosamente para fazer o resultado parecer conforme.

## Auditoria mínima por mudança concluída

Uma mudança só pode ser marcada como `concluída` quando houver:

- diff/commit identificável;
- testes focados e resultado;
- teste de integração ou justificativa formal de que não se aplica;
- evidência de runtime quando a mudança altera o caminho de produção;
- matriz de arquitetura atualizada;
- documentação operacional atualizada;
- rollback conhecido.
