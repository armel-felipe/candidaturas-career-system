# cellular-runtime

## Mandatory rules

- Toda execução celular exige `CAREER_CONTROL_DB_ID`, `application_id`, `run_id` e manifesto válido.
- Células só leem e escrevem dentro das allowlists da candidatura; não há fallback ao estado global.
- `notion-write` e outros recursos externos declarados são serializados por lock SQLite, sem bloquear o trabalho interno de outras candidaturas.
- Reparos usam `applications:repair` e preservam manifests e artefatos anteriores.
