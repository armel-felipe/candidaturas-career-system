# Manutenção canônica autônoma com revisão independente

**Status:** aprovada para implementação, com escopo revisado
**Data:** 2026-09-01  
**Roadmap:** `MAINT-002`  
**Plano futuro:** `2026-09-01-autonomous-canonical-maintenance`

## Objetivo

Permitir que `vagas_bot_01` e `vagas_bot_02` solicitem correções canônicas sem
intervenção manual do operador para cada ajuste. O pedido será avaliado pelo
`HarnessSupervisor`, executado por um agente de manutenção com escrita isolada,
criticado por um agente revisor independente e aplicado somente quando todos os
gates determinísticos e a revisão atingirem o critério de aprovação.

O objetivo é remover o bloqueio operacional atual sem conceder aos agentes dos
bots escrita irrestrita no workspace de produção.

## Escopo

Incluído:

- alterações em arquivos versionados que façam parte do acervo canônico do
  projeto, respeitando uma allowlist exata por pedido;
- alterações em skills canônicas existentes, incluindo seu `SKILL.md`,
  referências, scripts e assets versionados, quando o pedido os especificar;
- alterações em código, testes, documentação e configurações versionadas que
  pertençam ao projeto e sejam necessárias para a correção;
- correções solicitadas por qualquer um dos dois bots;
- criação de especificação estruturada, patch, evidências e receipts;
- execução em worktree isolado e aplicação transacional no checkout canônico;
- commit automático após aprovação;
- recarga/reinício controlado dos dois bots e retomada do run original;
- repetição limitada quando o revisor apontar falhas corrigíveis.

Fora do escopo:

- edição para burlar provenance, FIT_MAP, review, delivery ou seal;
- alteração direta de `outputs/`, `.career-state/`, `control-plane/`, SQLite ou
  artefatos selados como manutenção de código;
- criação de uma nova skill, de uma nova pasta de skill ou de um namespace
  canônico inexistente;
- alteração de segredos, tokens, `.env`, chaves privadas, caches de runtime,
  dumps ou arquivos gerados não versionados;
- escrita externa em Notion, Gmail, OneDrive ou outros serviços sem os
  workflows e gates próprios;
- dar permissão de escrita no checkout canônico aos processos Hermes dos bots;
- usar temperatura do modelo como mecanismo de autorização.

### Política do acervo canônico

O supervisor considera elegível um arquivo rastreado pelo Git ou um novo
arquivo criado dentro de um diretório canônico já existente, desde que ele
esteja na `allowed_paths` do pedido e não pertença às exclusões acima. A
verificação é feita no commit-base e também no diff produzido pelo executor.

Uma skill só pode ser alterada quando sua pasta já existir no commit-base.
Qualquer tentativa de criar uma skill ou escapar do repositório é rejeitada
antes da execução do agente. A revisão independente complementa essa proteção,
mas não a substitui.

## Fluxo de estados

```text
requested -> policy_validated -> maintenance_running -> candidate_ready
           -> deterministic_checks_passed -> reviewer_approved -> applied
           -> committed -> agents_reloaded -> resumed
```

Qualquer falha produz um estado terminal ou de retry explícito, preservando o
pedido, a causa, os logs, o diff e os hashes. Um pedido não pode ser reportado
como concluído apenas porque o agente terminou sem erro.

## Contrato do pedido

O bot deve enviar um `MaintenanceRequest` versionado contendo, no mínimo:

- `request_id`, `requester_profile`, `application_id` e, quando aplicável,
  `run_id`;
- `objective` curto e factual;
- `spec`, com requisitos verificáveis e comportamento esperado;
- `evidence`, incluindo erro observado, arquivos relevantes e comando de
  reprodução;
- `allowed_paths`, com os caminhos exatos do acervo canônico que podem ser
  alterados;
- `roadmap_id`;
- `base_commit` e fingerprint do contexto usado;
- classificação de risco e indicação se a correção pode retomar o run.

O supervisor rejeita pedidos sem escopo de candidatura quando o contexto for
celular, sem spec verificável, sem evidência, com allowlist fora do acervo
canônico ou que tente criar uma skill. O pedido é idempotente por hash de
objetivo, spec, base e caminhos.

## Papéis

### HarnessSupervisor

É o ponto de entrada e o único componente que decide se o pedido pode avançar.
Ele valida a intenção contra `AGENTS.md`, o roadmap, a allowlist, o estado do
checkout e os gates aplicáveis. Não escreve código produzido pelo agente.

### Agente de manutenção

Recebe somente o pedido validado e trabalha em um worktree temporário baseado no
`base_commit`. Tem escrita no worktree, não no checkout canônico. Deve produzir
um diff revisável, resumo por requisito, testes executados e lista final de
arquivos alterados.

### Agente revisor

É uma execução separada, sem capacidade de escrever no worktree da manutenção.
Recebe a spec original, o diff, os resultados dos testes e as evidências. Deve
avaliar cada requisito, apontar regressões e emitir um relatório estruturado.
Não pode aprovar um diff que não tenha passado pelos gates determinísticos.

## Critério de aprovação

O limiar de `99%` será aplicado como score de conformidade verificável, não como
probabilidade subjetiva do modelo. A aprovação exige simultaneamente:

- 100% dos requisitos obrigatórios da spec cobertos;
- 100% dos arquivos alterados dentro da allowlist;
- todos os testes e gates obrigatórios aprovados;
- nenhum blocker, regressão conhecida ou alteração proibida;
- hashes do pedido, diff, base e resultados registrados;
- score do revisor independente `>= 99/100`.

Se qualquer hard gate falhar, o resultado é `rejected`, mesmo que o modelo
declare alta confiança. Warnings podem ser aceitos somente quando a política
do pedido os classificar explicitamente como não bloqueantes.

## Retry e bloqueio

Quando a reprovação for corrigível, o supervisor envia a crítica estruturada ao
agente de manutenção. O limite padrão será de três tentativas por pedido,
contadas de forma idempotente. Cada tentativa terá seu próprio diff, resultado
de testes e revisão.

Após o limite, ou diante de risco alto, conflito de base, allowlist inválida,
tentativa de burlar um gate ou ausência de evidência, o pedido fica `blocked`.
O retorno deve conter a causa objetiva e a ação necessária; não deve pedir ao
usuário um novo prompt que apenas repita o mesmo pedido.

## Aplicação e retomada

Depois da aprovação, o supervisor:

1. confirma que o checkout canônico ainda está na base esperada;
2. executa o `dry-run` do patch;
3. aplica o patch com a função canônica de manutenção;
4. roda a suíte e os gates pós-aplicação;
5. cria um commit com `request_id`, `roadmap_id` e hash da revisão;
6. registra o receipt de manutenção;
7. recarrega/reinicia os dois perfis quando a mudança afetar runtime ou skill;
8. retoma o mesmo `application_id`/`run_id`, sem criar candidatura nova.

Se a aplicação ou validação pós-commit falhar, o commit não será publicado como
válido e a retomada não será executada. A recuperação usa o mecanismo
transacional do checkout, nunca edição manual de artefatos celulares.

## Segurança e isolamento

- O mount de código dos bots continua read-only.
- O worker de manutenção será executado no host ou em worker privilegiado
  isolado, com identidade própria e diretório temporário dedicado.
- O worker não recebe tokens externos por padrão.
- O supervisor verifica branch, dirty state inesperado e conflito de
  concorrência antes de aplicar.
- Alterações em skills seguem a precedência canônica; cópias locais de perfil
  não serão criadas.
- O sistema preserva a distinção entre manutenção de código e produção de
  artefato de candidatura.

## Observabilidade

Cada pedido deve deixar um receipt contendo perfil solicitante, sessão/run,
base commit, commit aplicado, hashes do diff/spec, caminhos permitidos e
alterados, tentativas, testes/gates, score e decisão do revisor, timestamps,
motivo de bloqueio e estado da recarga/retomada.

O status conversacional deve distinguir `requested`, `running`, `rejected`,
`blocked`, `applied`, `committed` e `resumed`.

## Validação e aceite

Antes de habilitar em produção, a implementação deve testar:

- pedido válido e malformado;
- rejeição de caminhos fora da allowlist;
- aceitação de alteração em uma skill canônica existente;
- rejeição de criação de nova skill ou alteração de estado/artefato gerado;
- worktree isolado e ausência de escrita no checkout durante a execução;
- revisor que aprova exatamente `99/100` e rejeita `98.99/100`;
- hard gate que rejeita mesmo com score alto;
- retry limitado e bloqueio após três tentativas;
- idempotência e conflito de base;
- commit e receipt completos;
- reload dos dois perfis e retomada do mesmo run;
- regressão dos comandos `maintenance:request` e `maintenance:apply`.

Critério operacional: um pedido originado por cada bot deve percorrer o fluxo
completo em ambiente de teste, produzir commit reproduzível para ambos e deixar
os dois perfis capazes de resolver a mesma skill/código canônico após reload.

## Decisão registrada

Esta proposta assume que alterações allowlisted em código e skills serão
aplicadas e commitadas automaticamente após os gates. Operações externas e
artefatos selados continuam fora dessa autorização.
