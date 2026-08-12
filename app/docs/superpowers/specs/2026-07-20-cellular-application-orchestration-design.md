# Orquestração Celular de Candidaturas — Design

## Objetivo

Permitir que um único workspace autoritativo processe duas ou mais candidaturas em paralelo, cada uma por meio de células com entradas, saídas, entregáveis, validações, proveniência e recuperação explícitas. O sistema deve impedir mistura de contexto entre vagas e permitir reparos locais sem reiniciar o processo inteiro.

## Decisões

- O workspace é executado por uma única máquina por vez: Mac ou RPi5. Não há execução concorrente em cópias sincronizadas por Git, rclone ou nuvem.
- Candidaturas são isoladas por `application_id`; toda operação de candidatura exige esse identificador.
- SQLite é o plano de controle transacional. Arquivos JSON/Markdown/DOCX são o plano de dados legível e auditável.
- O fluxo de uma candidatura é um DAG compilado antes da execução. Agentes executam nós liberados; não escolhem a sequência nem usam estado global.
- Uma célula pode ser refeita dentro do mesmo run. Cada tentativa é preservada; apenas uma revisão validada é publicada.
- Ao concluir uma célula, o contexto conversacional pode ser descartado. A retomada usa um handover compacto, o índice de evidências e fontes autorizadas.

## Escopo

Entram neste desenho: intake, normalização de vaga, FIT_MAP, CV, FERAS, carta/apresentação, habilidades, Notion, revisão, entrega e reparo. Também entram locks de recursos compartilhados, isolamento de paths, versionamento de entradas e invalidação seletiva.

Não entram neste desenho: execução concorrente da mesma pasta em dois computadores, armazenamento de textos grandes dentro do SQLite, alteração automática de fatos canônicos do candidato, envio automático de e-mail ou candidatura final em plataformas externas.

## Modelo de Estado

O sistema separa estado mutável, histórico imutável e artefatos:

```text
SQLite (controle transacional)
  applications | runs | nodes | node_attempts | artifacts | locks | dependencies

.career-state/applications_v2/<application_id>/
  identity.json                 identidade e aliases duradouros
  state.json                    projeção mutável do estado atual
  plans/<run_id>.json           DAG compilado para o run
  cells/<node_id>/<attempt>/    manifestos, handovers e staging imutáveis
  derived/                      contexto normalizado versionado
  artifacts/                    revisões publicadas de artefatos textuais
  reviews/                      relatórios de validação
```

`state.json` é apenas uma projeção conveniente. O SQLite decide reservas, locks e estado operacional; o manifesto da tentativa prova como um resultado foi produzido.

## Tipos de Manifesto

### Manifesto de célula

Há um manifesto por tentativa de nó. Ele contém:

- identificadores: `application_id`, `run_id`, `node_id`, `attempt` e versão do contrato;
- entradas tipadas por path, hash, revisão e fonte;
- capability allowlist de leitura e escrita;
- contexto compacto permitido ao executor;
- saídas, artefatos e hashes publicados;
- validators executados, versão, resultado e path do relatório;
- estado: `planned`, `reserved`, `running`, `repairing`, `validated`, `blocked`, `superseded` ou `cancelled`;
- motivo de bloqueio, estratégia de reparo e dependências invalidadas;
- recibos de efeitos externos, como `page_id`/URL do Notion e entrega por rclone.

### Manifesto de entregável

Cada CV, FERAS, carta, lista de habilidades ou atualização Notion publicada recebe um manifesto de proveniência: artefato, hash, revisão, célula produtora, entradas, validators e status de entrega. Ele permite responder qual FIT_MAP e quais fatos produziram um documento específico.

### Manifesto de conclusão do run

Ao encerrar o run, um `run_completion_manifest.json` lista nós aprovados, entregáveis finais, revisões, pendências, bloqueios e handover de retomada. Ele não resume nem substitui os manifestos de célula.

## Grafo Compilado Antes da Execução

O planejador recebe `application_id` e os entregáveis solicitados, cria um DAG e valida o plano antes de reservar qualquer agente.

```text
capturar_fonte → normalizar_vaga → analisar_fit
                                      ├→ registrar_notion_inicial
                                      ├→ compor_cv → renderizar_cv → revisar_cv → entregar_cv → sincronizar_notion_final
                                      ├→ gerar_feras → revisar_feras
                                      ├→ gerar_carta → revisar_carta
                                      └→ gerar_habilidades → revisar_habilidades
```

O planejador deve:

1. resolver as células exigidas por cada entregável;
2. garantir que o grafo seja acíclico e que cada nó tenha contrato disponível;
3. atribuir paths exclusivos por candidatura, nó e tentativa;
4. checar versões de fatos canônicos, schemas e fontes obrigatórias;
5. calcular dependências, invalidações e locks de recursos;
6. verificar que paths de artefatos finais não colidem;
7. persistir o plano antes de iniciar qualquer execução.

O executor só libera um nó quando todas as dependências tiverem status `validated`. Nós independentes podem rodar em paralelo.

## Contrato de Célula

Cada definição de célula declara, de forma versionada:

- entradas obrigatórias e opcionais;
- schema do handover de entrada;
- saídas obrigatórias;
- entregáveis que pode publicar;
- validators obrigatórios;
- locks por candidatura e por recurso externo;
- células descendentes que ficam obsoletas se sua saída mudar;
- regras de reparo local;
- condições de sucesso, bloqueio e reuso idempotente.

Exemplo conceitual de `compose_cv`:

```json
{
  "requires": ["fit_map.validated", "candidate_facts.readonly", "cv_input_pack"],
  "writes": ["artifacts/cv_content/<revision>.json"],
  "validators": ["cv:validate-content", "validate-provenance"],
  "invalidates": ["render_cv", "review_cv", "deliver_cv", "sync_notion_final"],
  "repair_scope": "cv_content_only"
}
```

## Isolamento e Concorrência

Dois agentes podem trabalhar em vagas diferentes porque cada nó recebe uma capability allowlist. O executor recusa qualquer leitura ou escrita que não esteja no manifesto do nó.

Regras obrigatórias:

- não existe fallback silencioso para `.career-state/fit_map.json`, `cv_content.json`, `workflow_state.json` ou diretório derivado global;
- comandos de candidatura falham sem `application_id`;
- toda escrita ocorre primeiro em `cells/<node>/<attempt>/staging/`;
- publicação ocorre somente após validators aprovados e por operação atômica;
- fatos canônicos são montados como leitura somente durante o run;
- o worker não recebe permissão para varrer o workspace ou consultar paths por convenção;
- o runtime registra qualquer tentativa de acesso fora da allowlist como violação de execução.

Locks são de dois tipos:

| Lock | Escopo | Efeito |
|---|---|---|
| `application:<id>` | candidatura | impede dois nós mutáveis incompatíveis da mesma vaga |
| `linkedin-session` | workspace | serializa a sessão autenticada do LinkedIn |
| `notion-write` | workspace | serializa mutações remotas e preserva recibos |
| `delivery:<target>` | workspace | impede publicação concorrente no mesmo destino |
| `git-sync` | workspace | impede sincronização durante mutação |
| `candidate-facts-update` | workspace | protege atualização da base canônica |

SQLite deve usar WAL e transações curtas: a transação reserva ou conclui um nó; o trabalho de agente, rendering e revisão ocorrem fora da transação.

## Reparos Dentro do Mesmo Run

Uma falha não descarta as saídas anteriores nem reinicia o DAG. O orquestrador cria uma nova tentativa do menor nó reparável e preserva a tentativa anterior como `superseded` ou `blocked`.

| Falha | Menor reparo permitido | Nós reexecutados |
|---|---|---|
| validade/proveniência de conteúdo CV | `compose_cv` | composição, render, revisão e entrega do CV |
| formatação DOCX | `render_cv` | render e revisão do CV |
| blocker ATS textual | `compose_cv` | composição, render e revisão do CV |
| FIT_MAP inválido ou fato não sustentado | `analisar_fit` | FIT_MAP e todos os descendentes dependentes |
| descrição da vaga mudou | `normalizar_vaga` | normalização e todos os descendentes |
| falha em Notion | `sincronizar_notion_*` | apenas a sincronização Notion |

O número máximo de tentativas e quais blockers são reparáveis são propriedades explícitas do contrato da célula. Uma tentativa nunca sobrescreve uma revisão aprovada; uma nova revisão só passa a ativa após validação.

## Contexto Compacto e Retomada

Ao terminar uma célula validada, o orquestrador gera:

- `handover_summary.json`: fatos, decisões, restrições e resultados mínimos da próxima célula;
- `evidence_index.json`: ponteiros tipados, hashes e permissões para consultas objetivas;
- `decision_log.json`: decisões que alteram a composição, como idioma, seleção de experiências e gaps declarados.

O executor seguinte recebe o resumo, não o histórico conversacional. Pode abrir uma fonte do índice de evidências somente quando a tarefa exigir uma lacuna objetiva; a abertura é registrada no manifesto. O encerramento de um run preserva o handover final, permitindo retomar sem repetir intake, FIT_MAP ou geração já validados.

## Fontes Canônicas e Personalização

Os fatos canônicos devem ter identificadores e revisões, não regras fixas por vaga. Uma composição pode selecionar experiências, escolher aliases por idioma, ordenar fatos e escolher evidências adequadas à vaga. Ela não pode alterar empresa, período, graduação, idioma ou métrica sem uma revisão explícita da fonte canônica.

Cada item de CV deve referenciar `experience_id` e, para claims relevantes, `evidence_id`. O validador de proveniência resolve esses IDs e aceita personalização de redação e seleção, mas bloqueia alteração factual.

## Migração Incremental

O projeto será migrado em fatias independentes:

1. plano de controle SQLite, modelos de célula, locks e executor de plano;
2. intake e normalização com contextos derivados por candidatura;
3. FIT_MAP e sua validação/proveniência;
4. composição, renderização, revisão e entrega de CV;
5. Notion com recibo persistido e atualização idempotente;
6. FERAS, carta/apresentação e habilidades como ramos adicionais;
7. remoção dos fallbacks globais e testes de compatibilidade/migração.

Em cada fatia, o caminho anterior permanece disponível apenas como compatibilidade explícita e não pode ser usado por runs celulares novos.

## Critérios de Aceite

1. Dois agentes processam candidaturas diferentes no mesmo workspace sem compartilhar arquivo de estado, fingerprint ou contexto compacto.
2. Uma candidatura bloqueada não impede um nó independente de outra candidatura, exceto quando ambas disputam um lock de recurso compartilhado.
3. Todo entregável final possui manifesto de proveniência e relatórios de validação associados.
4. Um reparo de CV não reexecuta FIT_MAP nem modifica artefatos de outra candidatura.
5. A alteração de uma fonte invalida exatamente os descendentes declarados pelo grafo.
6. Um novo agente retoma uma candidatura usando o handover e o índice de evidências, sem depender do histórico conversacional.
7. O executor bloqueia acessos de arquivo fora da capability allowlist.
8. O sistema detecta e bloqueia execução ativa em uma segunda cópia do workspace.
