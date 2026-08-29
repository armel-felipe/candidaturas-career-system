# Correções críticas do roadmap — TEST-001 e RUNTIME-005

Data: 2026-08-25

## Escopo

- `TEST-001`: corrigir o teste de duas pipelines celulares concorrentes sem
  relaxar isolamento, proveniência, hashes ou revisão.
- `RUNTIME-005`: manter o runtime principal nos modelos grandes do
  `ollama-cloud`, sem cair silenciosamente para um modelo local.

## Execução e evidências

- `TEST-001`: a reprodução mostrou um gap ATS não declarado na fixture inglesa,
  seguido por expectativas antigas de períodos e idiomas. A fixture passou a
  declarar `growth` como gap legítimo e o teste foi alinhado ao contrato atual
  (`a`/`to` e `:`). O teste concorrente passou.
- `RUNTIME-005`: os perfis de configuração e runtime dos dois bots usam
  `provider: ollama-cloud` com `deepseek-v4-flash:0731`; a configuração foi
  conferida no host e dentro do container, sem expor credenciais.
- Validações: `2 passed` no conjunto focado; `npm run validate:structure`;
  `npm run runtime:verify -- --strict`; `git diff --check`.
- Suíte canônica: `519 passed, 3 failed`; as três falhas restantes são
  `TEST-005`, `TEST-007` e `TEST-008`.

## Limite conhecido

O smoke `hermes -z` completo excedeu 60 segundos mesmo em `safe-mode`; o
processo diagnóstico foi encerrado. Isso não reabre `RUNTIME-005`, cujo
critério é atendido pela configuração Cloud explícita, mas mantém uma
pendência de latência/integração CLI para observação.
