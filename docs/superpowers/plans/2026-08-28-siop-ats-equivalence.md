# Plano de correção — equivalência ATS de SIOP

Plano: `2026-08-28-siop-ats-equivalence` — concluído em 2026-08-28.

## Diagnóstico confirmado

- A candidatura Jobgether está bloqueada em `review_cv`.
- A terceira revisão atingiu ATS top8 `7,0/8`, com único
  `missing_unexplained`: `SIOP`.
- O CV já contém `S&OP` em experiências com evidência de planejamento,
  inventário, safety stock, MRP e manufatura.
- O registry canônico não possuía entrada para `SIOP`; por isso o reviewer não
  podia classificar `S&OP` como cobertura similar.
- A run existente já consumiu as três tentativas de `compose_cv`; ela não pode
  ser corrigida apenas repetindo `review_cv`.

## Item do roadmap

- `CV-013`: equivalência curada de `SIOP` e `S&OP` em CV inglês.

## Implementação

1. Adicionar teste regressivo que falha quando `SIOP` não reconhece `S&OP`.
2. Adicionar entrada `siop` ao registry com `en_cv_preferred: S&OP`, variantes
   aceitas e condição explícita de evidência.
3. Manter a regra de não injetar `SIOP` no texto quando a nomenclatura não for
   factual; a equivalência é usada somente para o gate ATS.
4. Criar uma nova run celular da mesma candidatura, sem novo intake, depois da
   validação da correção. A execução foi concluída na run
   `run_b625368e9837418eb3ced11c82c56491`; durante a retomada, `supply chain`
   também foi materializado pela correção registrada em `CV-014`.

## Evidência de execução

- O teste novo falhou antes da alteração com `variants=[]`.
- Depois da alteração, o teste de equivalência e o teste de planejamento
  passaram (`2 passed`).
- O registry passou por `json.tool`.
- A candidatura Jobgether foi regenerada, aprovada e reconciliada; o
  esgotamento da run anterior não impediu a conclusão do caso.

## Critério de saída

O reviewer deve classificar `SIOP` como `covered_similar`, com score `0,8`,
quando o CV contém `S&OP` e a candidatura possui evidência canônica compatível;
um caso sem essa evidência continua sendo gap ou ausência não explicada.
