# Design: alinhamento de runtime do canário da Fase D

## Objetivo

Permitir que o canário `vagas_bot_01` valide o compose real com o control plane
SQLite compartilhado, mantendo D0 estritamente read-only e tornando explícito o
momento em que a evidência de D0 é persistida.

## Decisões

1. `CanaryTarget` terá um `state_root` separado do `workspace_root`. O workspace
   continua apontando para os scripts e o perfil Hermes; evidências, manifests,
   requests e aplicações usam o state root resolvido pelo mount
   `/workspace/candidaturas/.career-state`.
2. Paths absolutos declarados no ambiente do serviço serão traduzidos do path
   interno do container para o source host do volume correspondente. Paths host
   já resolvidos continuam válidos.
3. O comando `preflight` somente calcula e imprime o relatório. O novo comando
   `record-preflight` executa o mesmo preflight e, somente se o resultado for
   `ready`, grava D0 através do mecanismo existente de evidências.
4. O compose Hermes canônico declara, para os dois serviços, o mesmo control
   plane, ledger e `CAREER_CONTROL_DB_ID`. A execução operacional desta fase
   continua limitada ao `vagas_bot_01`; isso não inicia nem altera o perfil do
   `vagas_bot_02`.

## Fluxo

```text
compose real
  -> resolve workspace/state/control-plane host paths
  -> preflight read-only
  -> record-preflight explícito (somente se ready)
  -> stage-hook dry-run/apply
  -> controlled-run
  -> D3 runner gate
```

## Segurança e falhas

- O target continua rejeitando qualquer bot diferente de `vagas_bot_01`.
- D0 bloqueado não cria evidência, manifesto ou diretório auxiliar.
- O registro D0 usa o state root canônico e não grava prompt, histórico ou
  stdout ilimitado.
- A ausência do runner Hermes continua fail-closed; não haverá fallback.
- O compose será validado por testes contra paths internos e sources host,
  incluindo o isolamento do state root e a preservação do bot02.

## Fora do escopo

- iniciar ou reiniciar containers;
- instalar o executável Hermes;
- alterar configurações do perfil Hermes;
- promover `CHG-0006` ou `ARCH-06` para verificado.
