# Plano de correção — materialização ATS de supply chain

Plano: `2026-08-28-supply-chain-ats-materialization` — concluído em 2026-08-28.

## Diagnóstico

Na nova FIT_MAP celular da candidatura Jobgether, `supply chain` entrou no
top8. O CV tinha evidência canônica de planejamento, demanda, inventário,
materiais e manufatura, mas o gerador inglês não possuía cláusula controlada
para materializar essa expressão. O review bloqueou com ATS top8 `6,8/8` e
`supply chain` como `missing_unexplained`.

## Implementação

- Adicionado teste regressivo de materialização para a experiência Trifil.
- Adicionada cláusula inglesa controlada em
  `src/career/services/cv_content.py`, sem alegar experiência em Syteline/CSI.
- Regenerados `compose_cv`, `render_cv` e `review_cv` na mesma run celular.
- Entregue o CV aprovado e reconciliados FIT_MAP, artefato, delivery e Notion
  no SQLite canônico.

## Evidência

- Teste RED antes da cláusula: falha porque `supply chain` não era
  materializado.
- Teste GREEN após a cláusula: passou, junto da suíte focada de CV/review.
- Run `run_b625368e9837418eb3ced11c82c56491`: `completed`.
- Review final: `approved_for_delivery=true`, ATS top8 `7,8/8`, zero
  `missing_unexplained` e nenhum blocker.
- Reconciliação: `core_package_sealed`, página Notion
  `3c90003f-9481-817c-979d-e0f5a6018bbd` e delivery OneDrive confirmados.
