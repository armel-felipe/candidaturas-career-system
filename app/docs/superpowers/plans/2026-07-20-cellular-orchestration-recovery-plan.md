# Plano de Recuperação — Orquestração Celular

## Estado auditado

| Bloco | Estado | Evidência |
|---|---|---|
| Controle transacional (Task 1) | aprovado | `c076405`, `716af64`, `0ea0aac` |
| Contratos e DAG (Task 2) | aprovado | `acb7170`, `730ecfe` |
| Manifests e staging (Task 3) | aprovado | `f08c3cf`, `c44a740` |
| Executor e reparo (Task 4) | aprovado | `51ce54f`, `b736737` |
| CLI (Task 5) | implementado, pendente de re-revisão | `ce300e3`, `45e53f0` |
| Intake/FIT_MAP (Task 6) | não iniciado | — |
| CV (Task 7) | não iniciado | — |
| Notion e entregáveis auxiliares (Task 8) | não iniciado | — |
| Migração, segurança de workspace e teste paralelo (Task 9) | não iniciado | — |

## Mudança de estratégia

O restante não será executado como uma longa cadeia de microtarefas. Cada fatia abaixo produz um comportamento completo, tem um único gate integrado e só então avança. Um finding de revisão retorna para a mesma fatia; não cria uma nova sequência independente.

## Fatia A — Fechar o núcleo já implementado

1. Re-revisar `45e53f0` contra os quatro findings da Task 5.
2. Rodar um teste de integração do núcleo: criar duas candidaturas temporárias, compilar dois planos, reservar nós distintos, executar handlers falsos, publicar múltiplos artefatos, finalizar os dois runs e inspecioná-los pela CLI.
3. Exigir que `applications inspect-run` mostre status real, artefatos e próximo nó; que nenhuma candidatura leia/escreva paths da outra.
4. Atualizar o painel de status com evento, commit, testes e gate.

Critério de saída: CLI e núcleo celular funcionam juntos para duas candidaturas simuladas no mesmo SQLite, sem estado global ou conclusão falsa.

## Fatia B — Intake, contexto normalizado e FIT_MAP por candidatura

1. Substituir chamadas celulares que usam `configure_derived_dir`, `configure_state_store_path` e paths globais por interfaces que recebem `ApplicationPaths` explícitos.
2. Implementar handlers `capture_source`, `normalize_job` e `analyze_fit` usando apenas paths da candidatura.
3. Persistir fingerprint da vaga, revisão dos fatos canônicos, FIT_MAP e handover como artefatos publicados.
4. Testar duas vagas em paralelo, alteração da descrição e invalidação apenas de descendentes.

Critério de saída: duas descrições geram dois packs/FIT_MAPs independentes; mudar A não muda B nem reutiliza contexto global.

## Fatia C — CV completo e revisável por célula

1. Tornar composição, renderização, revisão e entrega do CV handlers explícitos do DAG.
2. Fazer cada experiência referenciar fatos canônicos (`experience_id`, `evidence_id`) e validar proveniência antes do DOCX.
3. Remover qualquer dependência celular de FIT_MAP/CV content globais e garantir diretório/arquivo de saída por candidatura.
4. Executar dois CVs de idiomas distintos em paralelo e validar idioma, datas, graduação, seções e revisão objetiva em ambos.

Critério de saída: dois CVs aprovados em paralelo, cada um com proveniência completa e sem cruzamento de idioma, dados ou artefatos.

## Fatia D — Notion e demais entregáveis

1. Implementar FERAS, carta e habilidades como ramos independentes após FIT_MAP.
2. Implementar Notion inicial/final com lock global, hash de requisição e recibo idempotente.
3. Implementar entrega de CV com recibo e lock de destino.
4. Testar que CV bloqueado não bloqueia FERAS; repetição de Notion não duplica escrita.

Critério de saída: todos os entregáveis solicitados possuem manifesto, revisão aplicável e recibo externo quando houver efeito remoto.

## Fatia E — Migração, operação e aceitação final

1. Migrar estado legado sem declarar aprovação inexistente.
2. Implementar lease do workspace para impedir duas cópias Mac/RPi5 ativas, preservando duas vagas paralelas na mesma cópia.
3. Rodar teste de dois processos reais no mesmo workspace, com candidatura A e B independentes e locks externos serializados.
4. Atualizar AGENTS, career-system e o painel de status; commitá-los junto ao comportamento final.
5. Rodar suíte completa, testes de integração, diagnóstico runtime e revisão ampla do branch.

Critério de saída: uma única pasta processa duas vagas em paralelo, retoma por manifestos e bloqueia execução concorrente em cópia distinta.

## Regra operacional de sequência

Após cada gate aprovado: registrar o resultado no painel versionado, despachar imediatamente a próxima fatia e não encerrar a execução por checkpoint. O painel é um artefato rastreado do repositório, não um arquivo temporário não versionado.
