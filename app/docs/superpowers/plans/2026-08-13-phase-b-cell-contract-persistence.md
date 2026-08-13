# Plano da Fase B — contrato celular persistido no SQLite

> **Objetivo:** tornar cada tentativa celular auto-descritiva e verificável antes
> de iniciar o agente, e liberar a etapa seguinte somente depois do registro
> transacional de outputs, handover e validações.

## Recorte aprovado

Esta fase implementa o control plane da execução celular. Não integra ainda o
gateway Telegram nem substitui os bancos Hermes privados. A autoridade será o
SQLite compartilhado; manifests, descrições, FIT_MAPs, DOCX e demais arquivos
continuarão no filesystem, referenciados por caminho, versão e SHA-256.

## Modelo de dados

- `cell_inputs`: lista imutável de referências autorizadas por tentativa, com
  origem, versão, caminho, hash e obrigatoriedade.
- `cell_handovers`: um handover estruturado por tentativa, com hash do payload e
  referência ao arquivo quando existir.
- `validation_receipts`: recibos individuais dos validadores, com comando,
  resultado, relatório e hash do relatório.
- `cell_requests`: projeção compacta do contrato e dos inputs persistidos. O
  request é recriável e não é autoridade independente.

As tabelas usam chaves únicas por `run_id/node_id/attempt` e nomes de input ou
validador. Nenhum payload longo ou conteúdo de conversa será colocado no banco.

## Ordem operacional

1. Reservar o nó e materializar o manifest.
2. Registrar inputs e projeção do request em uma transação antes do handler ou
   runner começar.
3. Revalidar existência, identidade e SHA-256 dos inputs imediatamente antes da
   execução.
4. Executar o handler em staging e executar os validadores determinísticos.
5. Publicar artefatos e handover no filesystem.
6. Em uma transação imediata, registrar handover, recibos, artefatos e marcar a
   tentativa como `validated`.
7. Só então `list_ready_nodes` poderá liberar dependentes.

Se uma referência desaparecer ou mudar de hash, a tentativa será bloqueada e a
dependência não avançará. Concorrência de dois workers para a mesma tentativa
deve aceitar somente o commit que mantém worker e lease válidos.

Uma tentativa preparada para preenchimento externo pode completar referências
enquanto ainda está em `reserved`; o executor marca a tentativa como `running`
imediatamente antes do handler, congelando a lista a partir desse ponto.

## Limites do request

O request armazenará apenas contrato, identidade, referências e metadados
bounded. O builder rejeitará payload acima do limite configurado antes do agente
ser iniciado. A medição precisa ser conservadora e não depende de histórico de
Telegram.

## Estratégia de implementação e testes

Aplicar TDD em quatro grupos:

- [x] schema/API: persistência, idempotência e limites;
- [x] integridade: hash alterado, input ausente, dependência não validada e request
  inconsistente;
- [x] transição: handover/recibos/artefatos no commit final;
- [x] concorrência: tentativa ou commit stale não pode promover o nó.

Os testes de integração usam `CellExecutor` com handlers e validadores mínimos,
`tmp_path` e SQLite temporário. O caminho Telegram fica explicitamente sem teste
de integração nesta fase.

## Critério de conclusão

- [x] testes focados da Fase B aprovados;
- [x] regressão disponível executada, com bloqueios ambientais separados;
- [x] `git diff --check` e compilação Python executados;
- [x] matriz de arquitetura e `CHG-0004` atualizados com comandos e evidências;
- [x] nenhuma alteração nos três arquivos sujos preexistentes da Fase A.
