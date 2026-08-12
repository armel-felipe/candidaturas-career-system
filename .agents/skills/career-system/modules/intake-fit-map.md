# intake-fit-map

## Mandatory rules

- Toda vaga entra por `intake:notion-record`, `intake:paste`, `intake:linkedin-job`, `intake:linkedin-post` ou `intake:url`.
- Persistir a descrição, criar o draft, validar com `validate:fit-map:draft`, finalizar e validar qualidade antes de declarar FIT_MAP concluído.
- Para LinkedIn, usar exclusivamente os extratores autenticados do projeto; não analisar a URL diretamente.
- Retomar pelo `application_id` e pelo próximo passo persistido; reset real exige confirmação explícita.
- `references/catalogo_resultados_chave.json` orienta posicionamento e seleção de histórias; não é fonte de alegação publicável.
