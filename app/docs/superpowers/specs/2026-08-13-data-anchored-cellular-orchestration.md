# Especificação: Orquestração celular ancorada em dados

**Data:** 2026-08-13
**Status:** proposta aprovada conceitualmente; implementação ainda não iniciada
**Escopo:** pipeline de candidaturas executado por `vagas_bot_01`, `vagas_bot_02` e futuros workers

## 1. Decisão

O pipeline será executado como uma sequência de células independentes. Cada célula
receberá uma sessão nova do agente e consultará os dados persistidos da candidatura.
O histórico conversacional não será usado como fonte de continuidade operacional.

O SQLite será a autoridade do controle do processo. Arquivos grandes continuarão
sendo usados para descrições, FIT_MAPs, DOCX e outros artefatos, mas cada arquivo
será registrado no SQLite com tipo, versão, caminho, hash, origem e relação com a
etapa que o produziu.

Uma etapa só poderá ser liberada quando seus inputs estiverem registrados, seus
outputs tiverem sido produzidos, validados e publicados, e o handover da etapa
tiver sido persistido com sucesso.

## 2. Problema que esta arquitetura resolve

O caminho atual permite que um gateway Hermes mantenha uma sessão longa, carregue
skills extensas e acumule resultados de ferramentas. A compactação reduz o
histórico, mas não cria uma fronteira operacional confiável. Na prática, isso
produziu sessões com centenas de chamadas, requisições individuais próximas de
500 mil tokens e consumo cumulativo muito maior.

Também existem duas formas de continuidade que não devem ser confundidas:

- continuidade conversacional: o que o usuário disse ao bot;
- continuidade operacional: quais dados uma etapa precisa e quais resultados a
  etapa anterior realmente publicou.

Somente a segunda será usada para conduzir o pipeline.

## 3. Objetivos

1. Fazer cada etapa começar com uma sessão nova, sem `resume` da etapa anterior.
2. Permitir que qualquer worker consulte os mesmos dados canônicos da candidatura.
3. Registrar os inputs de uma sessão antes de iniciar o processo do agente.
4. Impedir que uma etapa seguinte seja iniciada antes da validação transacional da
   etapa anterior.
5. Reduzir o contexto entregue ao modelo a um pacote específico da etapa.
6. Permitir auditoria: candidatura, run, célula, tentativa, inputs, outputs,
   validações e hashes devem ser reconstruíveis.
7. Fazer com que a falha de um agente resulte em estado bloqueado ou reparável,
   e não em uma sessão interminável.
8. Permitir que `vagas_bot_01` e `vagas_bot_02` sejam workers substituíveis, sem
   depender da memória privada de um deles.

## 4. Fora do escopo

- preservar uma conversa longa do Telegram como memória do pipeline;
- colocar bytes de DOCX ou descrições extensas diretamente em colunas SQLite;
- permitir que o agente escolha livremente a próxima etapa;
- resolver nesta especificação a autenticação do LinkedIn, Notion ou Gmail;
- substituir Git como fonte de verdade do código do projeto;
- remover imediatamente os arquivos JSON existentes. A migração será uma etapa
  posterior, com compatibilidade controlada.

## 5. Topologia de autoridade

O sistema terá uma única autoridade operacional compartilhada:

```text
control plane compartilhado
  career.db
  applications_v2/<application_id>/
  projeto Git em app/

workers Hermes/Codex/OpenCode
  sessões privadas e descartáveis
  logs privados por perfil
  nenhum estado de candidatura autoritativo
```

Os bancos SQLite privados atualmente existentes em cada perfil não podem continuar
sendo autoridades independentes se os bots participarem do mesmo pipeline. Eles
deverão ser tratados como estado legado, cache ou fonte de migração até que exista
um único control plane compartilhado.

O SQLite compartilhado deverá usar WAL, transações explícitas, locks e leases de
workspace. Um worker não poderá publicar resultado se perdeu a lease ou se a
versão da entrada mudou durante a execução.

## 6. Modelo de dados

O modelo aproveita as tabelas já existentes em `career.db` e acrescenta o contrato
explícito de entradas e handovers.

### 6.1 Entidades principais

| Entidade | Função |
|---|---|
| `applications` | identidade e estado resumido da candidatura |
| `application_runs` | execução de um fluxo específico da candidatura |
| `cell_nodes` | DAG de etapas e dependências |
| `cell_attempts` | cada tentativa de execução de uma etapa |
| `records` | payloads estruturados versionados, quando apropriado |
| `artifacts` | arquivos grandes ou binários publicados |
| `cell_inputs` | inputs autorizados de uma tentativa |
| `cell_handovers` | resumo estruturado que libera a etapa seguinte |
| `validation_receipts` | comandos, resultados, hashes e timestamp das validações |
| `workflow_events` | trilha de eventos de alto nível |
| `resource_locks` | exclusão de recursos externos e compartilhados |

### 6.2 Registro de input

Cada tentativa deverá ter uma lista imutável de inputs registrada antes do início
do agente. Cada item deverá conter, no mínimo:

```text
run_id
node_id
attempt
input_name
record_type             # record ou artifact
record_id / artifact_id
source_node_id
source_attempt
version
content_hash
path                    # obrigatório para artifact; opcional para record
required=true|false
created_at
```

O agente receberá uma referência a essa lista, não uma cópia arbitrária do estado
inteiro. O dispatcher materializará um `request.json` e um `request.md` compactos
para leitura humana e compatibilidade com os runners, mas esses requests serão
projeções do SQLite, não a autoridade primária.

### 6.3 Arquivos grandes

Descrições, FIT_MAPs, `cv_content`, cartas, FERAS, relatórios e DOCX permanecerão
em diretórios versionados por candidatura e etapa. O registro SQLite deverá guardar
o hash do conteúdo e a relação de dependência. O caminho sozinho nunca será
suficiente para considerar um input válido.

### 6.4 Handover

O handover será pequeno e voltado para a próxima etapa. Ele deverá conter:

- identidade da candidatura, run, célula e tentativa;
- status final da etapa;
- versões e hashes dos outputs publicados;
- decisões e fatos necessários para a próxima célula;
- referências a evidências, sem duplicar documentos longos;
- validações executadas;
- timestamp e versão do contrato.

O handover não será um resumo livre da conversa. Será um registro estruturado,
validável e associado aos artefatos publicados.

## 7. Contrato de execução de uma célula

O executor deverá seguir esta ordem:

1. Consultar o SQLite e localizar o próximo `cell_node` elegível.
2. Reservar a célula com worker, lease e número de tentativa.
3. Resolver as dependências e montar a lista de inputs autorizados.
4. Persistir `cell_inputs`, o manifest da tentativa e o request projetado.
5. Verificar que todos os inputs obrigatórios existem, estão validados e têm hash.
6. Iniciar um processo novo do agente, sem `resume` e sem histórico Telegram.
7. Permitir que o agente leia apenas os inputs e referências definidos no contrato.
8. Receber outputs em staging, sem publicação parcial no destino canônico.
9. Executar os validadores determinísticos da célula.
10. Publicar outputs, handover, recibos e hashes em uma transação autorizada.
11. Marcar a tentativa e o nó como `validated` somente após a publicação completa.
12. Liberar os nós dependentes apenas depois do commit dessa transação.

Se qualquer ponto entre 3 e 10 falhar, a célula não libera dependentes. O estado
deverá ser `blocked`, `repairing` ou `cancelled`, conforme a causa.

## 8. Contrato de saída e transição

Uma célula não será considerada concluída porque o processo do agente terminou com
exit code zero. Ela só será concluída quando:

- todos os artefatos obrigatórios existirem;
- o output obedecer ao contrato da célula;
- os validadores obrigatórios passarem;
- o handover referenciar a mesma candidatura, run, tentativa e hashes;
- o SQLite registrar os artifacts e receipts;
- o nó for marcado `validated` dentro da transação final.

A próxima sessão só poderá ser criada depois que a consulta de elegibilidade retornar
as dependências como `validated` e encontrar os inputs registrados para a nova
tentativa.

## 9. Decomposição do pipeline

`processe-a-vaga` deixará de ser uma instrução monolítica para um único agente. Ele
será o nome de um fluxo que compila para células pequenas, por exemplo:

```text
capture_source
  → normalize_job
  → analyze_fit
  → compose_cv → render_cv → review_cv → deliver_cv
                  ├→ generate_feras → review_feras
                  ├→ generate_cover_letter → review_cover_letter
                  └→ generate_habilidades → review_habilidades
```

As ramificações poderão executar em paralelo quando não disputarem o mesmo recurso.
Sincronizações externas, como Notion, OneDrive e Gmail, permanecerão protegidas por
locks e aprovações próprias.

Nenhuma skill de alto nível deverá instruir o agente a carregar todas as etapas,
todos os documentos e todos os comandos do pipeline. O agente receberá somente:

- contrato da célula;
- objetivo da tentativa;
- inputs autorizados;
- outputs permitidos;
- validadores;
- limites operacionais;
- instruções de bloqueio e encerramento.

## 10. Limites de contexto e comportamento do worker

Os limites serão propriedades do contrato da célula, não recomendações textuais.
Como política inicial para calibragem:

- alvo de contexto de entrada: até 12 mil tokens;
- limite duro de admissão: 32 mil tokens;
- limite de chamadas de ferramenta por tentativa: definido por célula;
- limite de bytes por output de ferramenta: definido por ferramenta;
- timeout e máximo de tentativas: definidos no contrato;
- detecção de repetição sem mudança de estado: encerra e bloqueia a tentativa.

Se o pacote exceder o limite, o executor deverá interromper antes de iniciar o
agente e produzir um diagnóstico de contexto. Não deverá enviar o pacote grande
esperando que o modelo faça compactação.

O histórico Telegram será limitado à interface: últimas mensagens necessárias para
responder ao usuário e o identificador da candidatura/run. Ele não será anexado ao
request da célula.

## 11. Fronteira entre bot e executor

O gateway Telegram será um dispatcher fino:

1. autentica e deduplica a mensagem;
2. identifica candidatura e intenção;
3. consulta o estado no SQLite;
4. cria ou retoma uma execução formal;
5. enfileira ou inicia a próxima célula elegível;
6. responde com estado curto, links e bloqueios.

O gateway não deverá executar diretamente uma skill completa em uma sessão Hermes
persistente. O Harness/CellExecutor deverá ser o único caminho de produção para
etapas de candidatura.

## 12. Conhecimento do projeto e alterações de código

Código compartilhado deve ser entendido pelo repositório e pelos testes, não pela
memória privada de um bot. Toda alteração feita por um worker de manutenção deverá
ter, no mínimo:

- arquivos alterados;
- objetivo da mudança;
- diff ou commit identificável;
- testes e validações executados;
- status de revisão;
- eventual impacto nas skills e contratos.

Workers de candidatura não deverão alterar scripts centrais durante uma execução
normal. Manutenção do projeto será uma classe de trabalho separada, com lock e
registro próprio, para evitar que dois perfis produzam mudanças incompatíveis no
mesmo código.

## 13. Critérios de aceitação arquitetural

A arquitetura será considerada implementada somente quando os testes demonstrarem:

1. Uma nova célula inicia processo novo e não reutiliza sessão Hermes anterior.
2. Não é possível iniciar uma célula sem `cell_inputs` persistidos.
3. Um input ausente, stale ou com hash divergente bloqueia a execução.
4. Uma falha de validação não libera nenhum dependente.
5. Um handover inconsistente não é publicado.
6. Dois workers não conseguem publicar a mesma tentativa ou perder a lease sem
   invalidação.
7. O request projetado contém apenas os inputs permitidos pela célula.
8. O limite de contexto bloqueia payload acima do limite antes do runner.
9. O estado de uma candidatura é consultável por qualquer worker autorizado.
10. Uma mudança feita por um bot em uma sessão anterior é descoberta pelo próximo
    worker via repositório/registro persistido, e não por memória conversacional.
11. Um fluxo completo de candidatura preenche `application_runs`, `cell_nodes`,
    `cell_attempts`, `cell_inputs`, `artifacts`, `cell_handovers` e recibos.
12. A execução real não depende do gateway Hermes persistente atual.

## 14. Migração em fases

### Fase A — autoridade e observabilidade

- definir o caminho único do `career.db` compartilhado;
- registrar o perfil do worker e o run em todas as execuções;
- adicionar diagnóstico de contexto por sessão e por célula;
- manter o caminho atual somente como legado observável.

### Fase B — contratos de input e handover

- implementar `cell_inputs`, `cell_handovers` e recibos versionados;
- fazer o request ser uma projeção do SQLite;
- validar hashes e dependências antes de iniciar o runner;
- testar transições e falhas sem alterar o fluxo de produção ainda.

### Fase C — execução celular real

- conectar o dispatcher ao Harness/CellExecutor;
- iniciar workers em processos novos e sem `resume`;
- impedir execução direta de `processe-a-vaga` pelo gateway;
- executar uma candidatura piloto ponta a ponta.

### Fase D — desativação do caminho monolítico

- reduzir o gateway Hermes a interface/dispatcher;
- remover ou bloquear skills monolíticas no caminho de produção;
- migrar candidaturas existentes e validar seus registros;
- acompanhar contexto, falhas, retries e tempo por célula.

## 15. Questões que permanecem para a implementação

Estas questões não alteram a decisão arquitetural, mas precisam ser fechadas no
plano de implementação:

- caminho físico do SQLite compartilhado entre os containers;
- se `records` armazenará pequenos JSONs completos ou apenas ponteiros para arquivos;
- limites específicos de cada célula;
- mecanismo de fila entre dispatcher e workers;
- política de aprovação humana para Notion, OneDrive e Gmail;
- estratégia de migração dos 175 diretórios de candidatura já existentes;
- política de compatibilidade para o caminho Hermes legado durante a transição.

## 16. Governança da implantação e do escopo

A implantação desta arquitetura será controlada por dois registros versionados:

- [`architecture-implementation-control.md`](../status/architecture-implementation-control.md),
  que compara cada requisito aprovado com a implementação e sua evidência;
- [`scope-change-log.md`](../status/scope-change-log.md), que registra adições,
  reduções, desvios, correções e decisões emergenciais.

Código existente, testes unitários ou documentação anterior não serão tratados
como prova de implantação no caminho de produção sem evidência de integração e
runtime. Uma mudança que altere este baseline deverá ser aprovada antes de entrar
em implementação, salvo contenção emergencial com revisão posterior obrigatória.
