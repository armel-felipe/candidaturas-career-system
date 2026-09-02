# Executor transacional do Harness — 2026-09-02

## Objetivo

Eliminar a coordenação concorrente por arquivos de estado do fluxo conversacional
dos bots. Cada mensagem passa a ter uma identidade, escopo e resultado duráveis
no SQLite autoritativo; o worker só pode executar um comando que tenha adquirido
por lease no banco.

## Escopo e decisão

Item relacionado: `HARNESS-019`.

O supervisor de domínio é preservado nesta primeira migração. A mudança troca a
fronteira de transporte: `hook -> comando SQLite -> worker -> resultado SQLite`.
Os diretórios `harness/dispatches`, `pipeline_intents`, `pending_input` e
`menu_state` deixam de poder selecionar aplicação ou indicar conclusão; serão
mantidos somente como espelho diagnóstico até a remoção após os canários.

## Etapas verificáveis

1. Criar `harness_commands` com idempotência por runtime/perfil/sessão/mensagem,
   claim transacional e resultado persistido.
2. Fazer o adapter enfileirar no banco e iniciar worker apenas para comando novo.
3. Fazer o worker reivindicar/finalizar o comando no banco e entregar a resposta
   persistida. Estados internos nunca viram bloqueio genérico.
4. Mover intenção, menu e confirmação para registros de sessão SQLite e remover
   sua leitura como autoridade.
5. Cobrir isolamento entre bots, replay, retomada após processo morto, sequência
   Notion -> CV e consulta do FIT_MAP da candidatura vinculada.
6. Executar testes focados, verificações estruturais/runtime e canários sem
   escrita externa antes de reativar ambos os bots para produção.

## Critério de aceite

Uma mesma mensagem não executa duas vezes; mensagens de dois bots no mesmo chat
não compartilham candidatura; reinício do worker retoma o comando correto; e a
resposta entregue é o resultado persistido daquele comando, não um fallback do
modelo ou de um arquivo legado.
