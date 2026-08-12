---
name: career-system
description: Roteador compacto do sistema de candidaturas.
---

# Career System

## Contrato de composição

Antes de executar uma skill de candidatura, leia seus `instruction_modules` no front matter. Carregue sempre `modules/runtime-core.md`, depois os módulos declarados e por fim a skill alvo. Um módulo ausente bloqueia a execução; não use instruções globais antigas como fallback.

## Módulos válidos

- `runtime-core`: binding Hermes, isolamento e contexto.
- `intake-fit-map`: intake e FIT_MAP.
- `cv-delivery`: CV, revisão e OneDrive.
- `notion-email`: Notion, Gmail e aprovações.
- `cellular-runtime`: células, locks e autoridade.

O roteamento canônico está em `references/routing-table.md`. Referências extensas ficam em `references/` e são carregadas apenas quando o módulo ou a skill as exigir.
