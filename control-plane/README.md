# Career control plane

This directory is the shared runtime location for the Career Job Application
System control database.

- Both `vagas_bot_01` and `vagas_bot_02` mount this directory at
  `/workspace/candidaturas/.career-control`.
- Both profiles resolve `CAREER_CONTROL_DB_PATH` to the same
  `/workspace/candidaturas/.career-control/career.db` path.
- SQLite files in this directory are runtime state and are ignored by Git.
- The existing per-profile databases under `workspaces/vagas_bot_01/state` and
  `workspaces/vagas_bot_02/state` remain legacy state during Phase A. Do not copy,
  merge, delete, or replace them automatically.

Provisioning and authority-ledger binding are explicit operations. A runtime
worker must not create a second control database because the shared path is
temporarily unavailable.
