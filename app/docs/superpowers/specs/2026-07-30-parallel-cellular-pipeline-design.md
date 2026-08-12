# Pipeline celular para duas candidaturas em paralelo — Design

## Objetivo

Permitir que dois perfis Hermes processem vagas diferentes simultaneamente no
mesmo RPi5 e na mesma cópia do projeto, sem que uma candidatura altere o
contexto, os artefatos ou a decisão da outra.

## Decisão arquitetural

O modo de produção passa a ser o pipeline celular já previsto no projeto. A
unidade de isolamento é a candidatura, identificada pelo ID único do Notion.
O orquestrador local planeja e acompanha as execuções; Hermes só atua na etapa
e nos caminhos explicitamente autorizados para uma candidatura.

Não haverá worktrees, cópias do repositório ou bancos independentes por
agente. Há uma única cópia autoritativa no RPi5 e uma única SQLite de controle.

## Dados centralizados

Permanecem compartilhados e canônicos:

- cache e fila de candidaturas do Notion;
- fatos canônicos do candidato, regras editoriais e registros de tradução de
  keywords;
- SQLite `.career-state/career.db`, que guarda fila, leases, locks de recursos
  externos, tentativas e auditoria;
- configuração do orquestrador, incluindo limite de concorrência igual a dois.

Esses dados não representam a vaga em processamento. Eles servem de memória
comum e de coordenação.

## Dados isolados por candidatura

Cada candidatura usa `.career-state/applications_v2/<ID>/` para manter:

- descrição e normalização da vaga;
- FIT_MAP e sua proveniência;
- requests de análise, geração e reparo;
- conteúdo do CV, artefatos, revisões, manifestos e logs;
- estado e tentativas da própria candidatura.

Um agente não pode ler ou escrever a pasta de outra candidatura. O request de
cada etapa deve carregar `application_id`, `run_id`, `node_id`, fingerprint da
vaga e listas exatas de leitura/escrita permitidas.

## Fluxo operacional

1. O operador coloca duas vagas elegíveis na fila do Notion.
2. Um único heartbeat celular no RPi5 seleciona no máximo duas candidaturas e
   cria um run isolado para cada uma.
3. O orquestrador entrega a cada perfil Hermes somente seu request app-scoped:
   `analyze`, depois `generate`, e `repair` apenas se um gate local reprovar.
4. Os handlers locais validam, renderizam e revisam cada CV a partir dos
   artefatos daquela candidatura.
5. A SQLite permite paralelismo entre vagas, mas serializa recursos externos
   declarados: escrita no Notion e entrega no OneDrive.
6. O status final, os receipts e os artefatos ficam vinculados ao `run_id` e
   ao `application_id`; não há promoção por arquivos globais.

## Bloqueios preventivos

No modo paralelo, comandos legados que dependem de `.career-state/fit_map.json`,
`.career-state/cv_content.json` ou `outputs/` como estado corrente não podem
ser usados para processar vagas. Eles ficam restritos a compatibilidade
explícita de execução única.

O pipeline celular deve falhar fechado quando faltar `CAREER_CONTROL_DB_ID`,
quando o ID do banco não corresponder ao banco autoritativo ou quando um
artefato não tiver identidade e fingerprint da candidatura.

## Experiência do operador

O comando padrão será o heartbeat celular com `--max-per-run 2` e agentes
habilitados. Os dois perfis Hermes não receberão instruções para executar o
pipeline completo nem para manipular a raiz do projeto: receberão apenas a
etapa e o request emitido pelo orquestrador.

O status operacional exibirá, para cada vaga, ID, etapa, run, agente e próximo
passo. Uma falha em uma vaga não cancela nem altera a outra.

## Critérios de aceitação

- Dois subprocessos reais processam duas vagas diferentes no mesmo RPi5.
- Cada candidatura produz FIT_MAP, conteúdo e CV em caminhos distintos, todos
  vinculados ao respectivo ID e fingerprint.
- Nenhum agente grava `.career-state/fit_map.json`, `cv_content.json` ou
  `outputs/` durante a execução celular.
- Um bloqueio ou reparo da vaga A não muda o estado ou os artefatos da vaga B.
- Ações externas disputadas são serializadas e registradas por receipt.
- A configuração local contém o ID de controle exigido e o diagnóstico de
  concorrência passa antes do primeiro processamento real em paralelo.

## Fora de escopo

Não há execução em mais de uma máquina, sincronização entre hosts ou mudança
nas regras editoriais do CV. O foco é tornar seguro o uso de dois perfis Hermes
na única cópia do projeto hospedada no RPi5.
