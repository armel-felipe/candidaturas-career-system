# `app/` — compatibilidade histórica

Este diretório não é um runtime de produção e não deve ser montado como a
árvore ativa dos bots. Ele permanece preservado para auditoria e rollback.

O Compose monta a raiz do projeto em `/workspace/candidaturas`; portanto, os
serviços usam `src/`, `scripts/`, `.agents/` e `AGENTS.md` da raiz. O banco
compartilhado é `control-plane/career.db`. Estado, inbox e outputs continuam
isolados por bot através dos mounts específicos.

Não adicione novos arquivos executáveis aqui. Correções devem ser feitas na
árvore canônica e verificadas antes de qualquer rollout.
