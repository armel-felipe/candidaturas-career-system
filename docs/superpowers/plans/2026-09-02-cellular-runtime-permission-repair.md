# Cellular Runtime Permission Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore `vagas_bot_01` so a scoped cellular run can safely progress from FIT_MAP through CV and Notion without permission leakage or direct Hermes bypass.

**Architecture:** Repair the bot-specific runtime state first, then rebuild both Hermes containers from the current canonical source. Harden the protected workspace snapshot so archival/ephemeral transport files do not block unrelated scoped runs, while historical application trees remain subject to ownership validation. Resume the existing application only through explicit `application_id`/`run_id` commands and verify the full CV/Notion gates.

**Tech Stack:** Python 3, pytest, SQLite control plane, Docker Compose, Hermes shell hooks, filesystem ownership, cellular HarnessSupervisor.

**Spec:** `docs/superpowers/specs/2026-09-02-cellular-runtime-permission-repair-design.md`

## Global Constraints

- Preserve all current uncommitted files; never use `git reset --hard` or discard/stash without explicit approval.
- Do not manually edit SQLite, FIT_MAP, FIT_MAP provenance, CV content, DOCX, Notion, receipts, or cellular manifests.
- Use only `workspaces/vagas_bot_01/{state,inbox,outputs,env}` for bot01 ownership repair; never change ownership of the canonical source tree.
- Run cellular commands with explicit `--application-id` and, when resuming a planned run, explicit `--run-id`.
- Keep the canonical root mount read-only; only the declared overlays remain writable.
- A maintenance patch may run only after the clean-checkout gate is satisfied by preserving the current harness diff through an approved commit or stash decision.
- No delivery claim is valid without the existing CV approval and delivery receipts.

## Roadmap coverage

- `RUNTIME-023`: stale Hermes image and unenforced `pre_llm_call` block.
- `RUNTIME-024`: root-owned bot state breaks global preflight.
- `HARNESS-018`: stale compatibility pointer and missing explicit scope on continuation.
- Existing `CELLULAR-016`: observe only; do not declare complete until the canonical Rappi run is inspectable and resumable.

## File map

- Modify: `src/career/services/harness_runs.py` — protected snapshot exclusions for archival and ephemeral transport roots, with tests.
- Test: `tests/test_cell_workspace_safety.py` — permission failure and ignored-root regressions.
- Test: `hermes-src/tests/agent/test_shell_hooks.py`, `hermes-src/tests/agent/test_turn_context.py` — source-level block contract.
- Operate: `app/deploy/hermes/compose.yaml`, root `compose.yaml` — build/recreate only; keep both compose files aligned.
- Operate: `workspaces/vagas_bot_01/state` — ownership repair after hash inventory.
- Operate: `control-plane/career.db` — read-only inspection through official commands.
- Review: `docs/roadmap.md` — update statuses only with fresh evidence.

## Task 1: Freeze the current state and preserve the dirty checkout

**Roadmap:** all three IDs; prerequisite for every later task.

- [ ] **Step 1: Record the current worktree and runtime baseline.**

  Run:

  ```bash
  git status --short
  git diff --check
  docker compose ps
  docker image inspect candidaturas/hermes-agent:0.18.2 --format 'id={{.Id}} created={{.Created}}'
  npm run bot:runtime -- --bot vagas_bot_01 --status
  ```

  Expected: the existing harness changes remain visible; both bot containers
  are identified; bot01 remains in Hermes mode.

- [ ] **Step 2: Save an external, read-only patch reference for the current diff.**

  Use a path outside the repository, for example:

  ```bash
  git diff --binary -- docs/roadmap.md package.json scripts/hermes_harness_context_hook.py \
    scripts/hermes_harness_dispatch_worker.py scripts/telegram_harness_adapter.py \
    tests/test_harness_async_dispatch.py > /tmp/vagas_bot_01_harness_before_repair.patch
  ```

  Do not use this patch to revert anything; it is a recovery reference only.

- [ ] **Step 3: Capture the exact permission baseline without changing files.**

  ```bash
  find workspaces/vagas_bot_01/state -user root -printf '%M %u:%g %p\n' > /tmp/vagas_bot_01_root_owned_before.txt
  find workspaces/vagas_bot_01/state -user root | wc -l
  docker exec --user 10000:10000 hermes-vagas-bot-01 sh -lc \
    'cd /workspace/candidaturas && PYTHONPATH=/workspace/candidaturas/src:/workspace/candidaturas/scripts /opt/hermes/.venv/bin/python - <<"PY"
  from pathlib import Path
  from career.services.harness_runs import _protected_workspace_snapshot
  root = Path("/workspace/candidaturas")
  app = root / ".career-state/applications_v2/local_20260831T231643_522497_rappi_6d861996"
  print(_protected_workspace_snapshot(root, app))
  PY'
  ```

  Expected before repair: the command reproduces a `ValidationFailure` naming
  a `root:root mode=600` file, without mutating the application.

- [ ] **Step 4: Stop here if the user has not chosen how to preserve the dirty diff.**

  The HarnessSupervisor maintenance path cannot apply a canonical patch while
  these changes are uncommitted. The allowed choices are an explicit commit of
  the current harness work, an explicit stash with the external patch reference,
  or postponing maintenance until the user resolves the diff. Never force the
  maintenance orchestrator past `canonical_checkout_not_clean`.

## Task 2: Repair only bot01 runtime ownership

**Roadmap:** `RUNTIME-024`.

- [ ] **Step 1: Stop bot01 before changing its mounted state.**

  ```bash
  docker compose stop vagas_bot_01
  ```

- [ ] **Step 2: Hash every root-owned regular file before ownership repair.**

  ```bash
  find workspaces/vagas_bot_01/state -user root -type f -print \
    > /tmp/vagas_bot_01_root_owned_paths_before.txt
  while IFS= read -r path; do sha256sum "$path"; done \
    < /tmp/vagas_bot_01_root_owned_paths_before.txt \
    > /tmp/vagas_bot_01_root_owned_hashes_before.txt
  ```

- [ ] **Step 3: Align the bot state to the runtime UID/GID.**

  ```bash
  chown -R 10000:10000 workspaces/vagas_bot_01/state
  chown -R 10000:10000 workspaces/vagas_bot_01/inbox workspaces/vagas_bot_01/outputs workspaces/vagas_bot_01/env
  ```

  This changes ownership only under bot01's mounted overlays. It must not be
  run against `/opt/agent-projects/candidaturas`, `hermes-src`, `src`, or
  `control-plane`.

- [ ] **Step 4: Prove content preservation and runtime access.**

  ```bash
  find workspaces/vagas_bot_01/state -user root -print
  while IFS= read -r path; do sha256sum "$path"; done \
    < /tmp/vagas_bot_01_root_owned_paths_before.txt \
    > /tmp/vagas_bot_01_root_owned_hashes_after.txt
  diff -u /tmp/vagas_bot_01_root_owned_hashes_before.txt \
    /tmp/vagas_bot_01_root_owned_hashes_after.txt
  docker compose up -d vagas_bot_01
  docker exec --user 10000:10000 hermes-vagas-bot-01 sh -lc 'id; test -r /workspace/candidaturas/.career-state/applications_v2/local_20260831T231643_522497_rappi_6d861996/fit_map.json; test -w /workspace/candidaturas/outputs'
  ```

  Expected: no root-owned files remain under the bot state, the hashes of all
  files are unchanged, and UID10000 can read the application and write outputs.

## Task 3: Prevent unrelated transport/archive files from breaking preflight

**Roadmap:** `RUNTIME-024`.

- [ ] **Step 1: Write the failing regression tests.**

  Add tests in `tests/test_cell_workspace_safety.py` proving that
  `_protected_workspace_snapshot()` excludes `.career-state/harness/dispatches`
  and `.career-state/reset_backups`, while still hashing an unrelated active
  application file and the protected database.

  The test fixture must create a mode-`0600` file in each excluded root and a
  readable sentinel outside them. It must assert the excluded paths are absent
  and the sentinel is present.

- [ ] **Step 2: Run the focused test and confirm RED.**

  ```bash
  .venv/bin/python -m pytest -q tests/test_cell_workspace_safety.py -k 'protected_workspace_snapshot or ignored_root'
  ```

  Expected: the new ignored-root assertion fails against the current
  `ignored_roots` set.

- [ ] **Step 3: Implement the smallest snapshot boundary.**

  In `src/career/services/harness_runs.py`, extend `ignored_roots` with:

  ```python
  root / ".career-state" / "harness" / "dispatches",
  root / ".career-state" / "reset_backups",
  ```

  Keep application directories out of this exclusion list; they must remain
  ownership-checked and scoped. Preserve the existing Telegram-message
  exclusion.

- [ ] **Step 4: Run the regression and permission gates.**

  ```bash
  .venv/bin/python -m pytest -q tests/test_cell_workspace_safety.py
  npm run validate:structure
  git diff --check
  ```

  Expected: the snapshot no longer reads the known archival/transport files,
  while unreadable application files still produce the actionable UID10000
  failure.

## Task 4: Rebuild and verify Hermes before any new Telegram workflow

**Roadmap:** `RUNTIME-023`.

- [ ] **Step 1: Run the source-level contract tests.**

  ```bash
  PYTHONPATH=hermes-src .venv/bin/pytest -q \
    hermes-src/tests/agent/test_shell_hooks.py -k 'pre_llm_call and block' \
    hermes-src/tests/agent/test_turn_context.py -k 'pre_llm_supervisory_block'
  ```

  Expected: all source-level block tests pass before rebuilding.

- [ ] **Step 2: Build both bot images from the current source.**

  ```bash
  docker compose build vagas_bot_01 vagas_bot_02
  docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02
  docker compose ps
  ```

  Do not use `docker exec` as root for Hermes commands that write profile
  state; use `--user 10000:10000`.

- [ ] **Step 3: Prove the running image has the current hook behavior.**

  ```bash
  for container in hermes-vagas-bot-01 hermes-vagas-bot-02; do
    docker exec --user 10000:10000 "$container" sh -lc \
      'PYTHONPATH=/opt/hermes /opt/hermes/.venv/bin/python - <<"PY"
  from agent.shell_hooks import _parse_response
  result = _parse_response("pre_llm_call", "{\"action\":\"block\",\"message\":\"stop\"}")
  assert result == {"action": "block", "message": "stop"}, result
  print("pre_llm_block_ok")
  PY'
  done
  ```

  Expected: both containers print `pre_llm_block_ok`. If either returns
  `None`, the image was not rebuilt/recreated from the current source.

- [ ] **Step 4: Verify the live logs after a controlled blocked dispatch.**

  Send one explicitly unscoped test message only after the runtime probe is
  green. Confirm the worker returns `explicit_application_scope_required` and
  that no subsequent model/tool turn appears for that message. Do not use a
  free-form message to resume a real application.

## Task 5: Reconcile scope and resume the existing Rappi run

**Roadmap:** `HARNESS-018`; observe `CELLULAR-016`.

- [ ] **Step 1: Inspect the canonical run from inside bot01.**

  ```bash
  docker exec --user 10000:10000 -w /workspace/candidaturas hermes-vagas-bot-01 \
    npm run applications:inspect-run -- \
    --application-id local_20260831T231643_522497_rappi_6d861996 \
    --run-id run_da7b09393276420b82d782791ed29ae0
  ```

  Expected: the same application/run is found; any expired reservation is
  reported with an official recovery action. If the run is absent from the
  authoritative projection, stop and restore/confirm identity through the
  existing reconciliation flow; do not create a replacement run by guessing.

- [ ] **Step 2: Resume with explicit identity and agent execution.**

  ```bash
  docker exec --user 10000:10000 -w /workspace/candidaturas hermes-vagas-bot-01 \
    npm run applications:run -- --run-agent \
    --application-id local_20260831T231643_522497_rappi_6d861996 \
    --run-id run_da7b09393276420b82d782791ed29ae0
  ```

  Expected: stale `analyze_fit` reservation is reconciled by the official
  service, the same run is resumed, and no second plan is created.

- [ ] **Step 3: Validate the resulting artifacts before reporting success.**

  Run the project gates using the explicit application path:

  ```bash
  docker exec --user 10000:10000 -w /workspace/candidaturas hermes-vagas-bot-01 \
    npm run applications:inspect-run -- \
    --application-id local_20260831T231643_522497_rappi_6d861996 \
    --run-id run_da7b09393276420b82d782791ed29ae0
  ```

  Require a valid CV review/approval receipt, delivery receipt, and Notion
  receipt before calling the package complete. A blocked provider, missing
  credential, or missing canonical evidence remains a reported blocker.

## Task 6: Close maintenance and document evidence

**Roadmap:** `RUNTIME-023`, `RUNTIME-024`, `HARNESS-018`, and observed
`CELLULAR-016`.

- [ ] **Step 1: Re-run all focused tests and runtime checks.**

  ```bash
  .venv/bin/python -m pytest -q tests/test_cell_workspace_safety.py tests/test_harness_dispatch.py tests/test_harness_async_dispatch.py
  PYTHONPATH=hermes-src .venv/bin/pytest -q hermes-src/tests/agent/test_shell_hooks.py hermes-src/tests/agent/test_turn_context.py
  npm run validate:structure
  npm run runtime:verify -- --strict
  git diff --check
  ```

- [ ] **Step 2: Reconcile the maintenance request only after checkout policy is satisfied.**

  If the snapshot-boundary change is still required, issue a new maintenance
  request with allowlist limited to `src/career/services/harness_runs.py` and
  apply it only after the current harness diff is explicitly committed or
  stashed. Never ask the orchestrator to mix the repair with unreviewed user
  changes.

- [ ] **Step 3: Update `docs/roadmap.md` with fresh evidence.**

  Mark each roadmap item `DONE` only with the exact test commands, container
  probes, ownership counts, and successful scoped resume. Keep any unresolved
  provider, canonical-run identity, or credential blocker in `BLOCKED`; do not
  report the pipeline as complete from a partial run.

## Stop conditions

- Any root-owned file remains in a path the snapshot reads.
- Either running container returns `None` for the `pre_llm_call` block probe.
- The canonical application/run cannot be resolved by explicit IDs.
- The maintenance orchestrator reports `canonical_checkout_not_clean`.
- A CV/Notion gate lacks its required receipt or provenance.
