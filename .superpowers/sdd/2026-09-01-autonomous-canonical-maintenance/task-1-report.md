# Task 1 — Relatório de implementação

## Escopo

Implementado o contrato versionado de pedidos de manutenção canônica (`MAINT-002`) em `src/career/services/maintenance.py`, com testes em `tests/test_canonical_maintenance.py`.

## TDD

- RED: os testes foram escritos antes da implementação.
- A primeira execução do comando literal do brief foi bloqueada porque `.venv/bin/pytest` não existe neste worktree.
- Com o interpretador disponível no checkout compartilhado (`/opt/agent-projects/candidaturas/.venv/bin/pytest`), os testes falharam pelas causas esperadas: ausência dos argumentos versionados e dos validadores.
- GREEN: implementação mínima adicionada e suíte focada aprovada.

## Implementação

- `schema_version = 2` no payload.
- Campos de especificação, evidência, perfil solicitante, candidatura/run, roadmap e commit-base.
- Fingerprint SHA-256 de JSON canônico com chaves ordenadas e separadores compactos.
- Validação de schema, requisitos, evidência, fingerprint e paridade `application_id`/`run_id`.
- Validação de paths contra Git/base checkout, allowlist canônica, exclusões de estado/artefatos, escapes por symlink, novos arquivos e novas skills.
- Compatibilidade preservada para callers legados de `create_maintenance_request` e `apply_maintenance_patch`.

## Validação executada

```text
PYTHONPATH=src /opt/agent-projects/candidaturas/.venv/bin/pytest -q tests/test_canonical_maintenance.py
7 passed

python3 -m compileall -q src/career/services/maintenance.py tests/test_canonical_maintenance.py
pass

git diff --check
pass
```

## Self-review e preocupações

Não foram encontrados blockers no diff. Apenas os dois arquivos de código/teste da tarefa foram alterados antes deste relatório. A suíte foi executada com o `.venv` do checkout principal porque o worktree isolado não contém uma cópia local do ambiente virtual; nenhum arquivo do checkout principal foi modificado.
