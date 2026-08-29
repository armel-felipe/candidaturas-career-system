# Especificação: modo serial do pacote-base de candidatura

## Objetivo

Permitir que `.agents/skills/processe-a-vaga/SKILL.md` execute o pacote-base de
uma candidatura celular em estágios de alto nível, um estágio por invocação,
parando até que os artefatos, validators e receipts do estágio atual estejam
válidos.

O modo serial deve usar a mesma candidatura, a mesma `run_id`, o mesmo DAG
persistido, os mesmos manifests, leases, tentativas e handlers da execução
celular atual. A mudança é de política de consumo do DAG, não uma segunda
implementação do pipeline.

## Escopo

Incluído:

- fechamento do `TEST-009`, atualizando a expectativa stale do planner;
- persistência de `execution_mode=serial` no plano celular;
- barreira de estágio no executor, com no máximo um estágio lógico por
  invocação;
- integração do modo serial à CLI, ao serviço celular e à skill
  `processe-a-vaga`;
- status de continuação que diferencie `running`, `awaiting_agent`,
  `awaiting_approval`, `blocked` e `completed`;
- cobertura de retries, reparos, receipts externos, isolamento por aplicação e
  paralelismo entre candidaturas distintas.

Fora do escopo:

- substituir ou remover o modo wave existente;
- aumentar o número de subagentes ou permitir fan-out dentro da mesma
  candidatura;
- alterar a autoridade do SQLite, os paths por `application_id` ou o contrato
  de entrega do OneDrive;
- executar envio de email ou candidatura em site externo;
- declarar uma candidatura concluída sem `core_package_sealed`.

## Política de execução

O plano serial do pacote-base (`cv` + `notion`) expõe os seguintes estágios:

| Estágio | Células permitidas | Condição para avançar |
|---|---|---|
| `normalize` | `capture_source`, `normalize_job` | job normalizado e validado |
| `analyze` | agente `analyze_fit` e célula `analyze_fit` | FIT_MAP final, draft/binding e provenance válidos |
| `cv` | `compose_cv`, `render_cv`, `review_cv` | CV renderizado e review aprovado |
| `delivery` | `deliver_cv` | receipt OneDrive verificado como `delivered` |
| `notion` | `sync_notion_initial`, `sync_notion_final` | receipts Notion e atualização final validados |
| `seal` | reconciliação/finalização | `core_package_sealed` persistido |

As células internas de `cv` continuam sendo executadas e validadas em ordem;
`cv` só é considerado concluído depois de `review_cv`. Reparos de qualquer
célula do estágio devolvem o estágio ao estado pendente e não autorizam
`delivery` ou `notion` na mesma continuação.

Embora alguns nós Notion sejam estruturalmente elegíveis mais cedo no DAG
legado, o scheduler serial não os reserva antes do estágio `delivery`. Isso
preserva a sequência operacional do pacote-base: CV aprovado, OneDrive
confirmado, Notion atualizado. O modo wave permanece compatível com os planos
legados até haver migração explícita.

## Invariantes de segurança

1. `application_id` e `run_id` são obrigatórios e permanecem constantes em
   todas as continuações.
2. O plano persistido é imutável; `execution_mode` faz parte do payload que é
   comparado entre arquivo e SQLite.
3. Uma chamada serial não reserva nem consome nó fora do estágio atual.
4. Uma tentativa externa sem draft/binding ou sem receipt válido não é tratada
   como concluída.
5. `awaiting_agent` e `awaiting_approval` nunca são convertidos em
   `completed`.
6. O máximo de um agente externo ativo por candidatura continua valendo; o
   heartbeat pode processar candidaturas diferentes em paralelo.
7. Falha ou expiração de lease é reconciliada pela API existente antes de
   qualquer reparo; nenhum banco, manifest ou artefato é editado manualmente.
8. Entrega só ocorre depois do review aprovado; Notion só ocorre depois do
   receipt de entrega validado no modo serial do pacote-base.

## Compatibilidade e recuperação

- Planos sem `execution_mode` carregam como `wave`, permitindo ler runs antigas.
- `applications:plan` aceita `--execution-mode wave|serial`, com `wave` como
  default de compatibilidade.
- `applications:run --run-agent` lê o modo do plano e aplica a política
  correspondente; não é permitido trocar o modo de uma run existente por
  argumento ad hoc.
- `applications:resume`, `applications:repair` e o Harness retomam o mesmo
  `run_id`; reparar não cria uma nova run nem libera descendentes.
- A skill chama explicitamente `--execution-mode serial` ao criar o plano e
  usa `inspect-run`/`resume` para descobrir a próxima ação.

## Critério de aceitação

Uma run descartável com `cv` e `notion` deve demonstrar, em inspeção de
receipts e `cell_nodes`, a ordem dos estágios `normalize → analyze → cv →
delivery → notion → seal`; cada invocação deixa no máximo o estágio atual
consumido; falhas de agente, review, aprovação ou entrega deixam a run
retomável e não reservam estágio posterior. O mesmo conjunto de testes deve
provar que duas candidaturas diferentes ainda podem ser processadas em
paralelo sem cruzar artefatos ou leases.
