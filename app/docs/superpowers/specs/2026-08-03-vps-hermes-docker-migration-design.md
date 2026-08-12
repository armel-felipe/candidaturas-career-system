# Migração do sistema de candidaturas para VPS — Design

## Objetivo

Migrar o workspace de candidaturas e os profiles Hermes `vagas_bot_01` e
`vagas_bot_02` para a VPS Ubuntu da Hostinger, com execução isolada por
Docker Compose e dados persistentes fora dos containers.

## Contexto confirmado

- VPS: Ubuntu 24.04 LTS, Docker 29.7.1 e Docker Compose v5.4.0.
- Acesso SSH por chave Ed25519 validado para `root`.
- O projeto ainda não possui Dockerfile ou Compose próprios.
- Os dois profiles existem em `~/.hermes/profiles/` e incluem estado de
  sessão, pairing e credenciais. O estado do projeto inclui a SQLite e os
  artefatos de candidatura.

## Arquitetura

```text
/opt/candidaturas/
  app/                         # código do workspace
  data/                        # .career-state e outputs persistentes
  hermes/
    vagas_bot_01/              # HERMES_HOME do profile 01
    vagas_bot_02/              # HERMES_HOME do profile 02
  compose.yaml
  .env                         # credenciais de runtime; permissão 0600
```

O Compose terá dois serviços Hermes independentes. Cada serviço monta o
workspace em modo de escrita e somente seu diretório de profile como
`HERMES_HOME`; os profiles não montam um o diretório do outro. Ambos usam a
mesma versão de imagem Hermes e a mesma rede interna privada.

Não haverá portas publicadas inicialmente. Uma porta de gateway só será
publicada se a configuração migrada demonstrar que ela é necessária; nesse
caso, será liberada no firewall apenas para os endereços autorizados.

## Migração de dados

1. Criar um snapshot local compacto, excluindo caches recriáveis e arquivos de
   lock, sem alterar a origem.
2. Transferir código, estado e os dois profiles por SSH com verificação de
   integridade.
3. Preservar permissões estritas para `.env`, tokens, SQLite e diretórios
   Hermes.
4. Manter o snapshot local até a validação final na VPS.

Tokens, pairing e sessões são migrados como dados confidenciais e nunca são
impressos nos logs, incluídos em Git ou expostos em portas HTTP.

## Operação e recuperação

- `docker compose up -d` inicia os profiles e `docker compose logs` permite
  diagnóstico sem acesso direto a arquivos sensíveis.
- `restart: unless-stopped` garante reinício após reboot da VPS.
- Cada profile preserva seu próprio `HERMES_HOME`, portanto a identidade e o
  binding `profile → candidatura` continuam separados.
- Em falha de migração, os containers são parados e o snapshot da VPS é
  removido ou substituído somente após confirmação; a instalação local segue
  sendo a fonte de recuperação.

## Validação de aceite

1. Ambos os containers ficam saudáveis e reiniciam após reinício simulado.
2. `npm run validate:structure` passa dentro do runtime.
3. Cada profile reporta seu próprio `HERMES_HOME` e status de binding, sem
   acessar o diretório do outro profile.
4. Nenhuma porta fica exposta sem necessidade documentada.
5. A origem local permanece inalterada e o snapshot é verificável.
