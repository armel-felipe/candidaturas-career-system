# Task 2 Report — Fase D canary hook staging

Date: 2026-08-13
Status: implemented
Commit: `feat: add phase D canary hook staging` (final HEAD recorded in handoff response)

## Scope delivered

- Added `stage_hook(target, apply)` in `app/src/career/services/canary_control.py`
- Added `route_smoke(root, messages, execute=False)` in `app/src/career/services/canary_control.py`
- Added `rollback_dry_run(target)` in `app/src/career/services/canary_control.py`
- Extended `app/scripts/phase_d_canary.py` with `route-smoke` and `rollback-dry-run`
- Updated `app/TELEGRAM_HARNESS_RUNBOOK.md` with dry-run, backup and manual restart guidance
- Added regression coverage in `app/tests/test_phase_d_canary.py`

## TDD evidence

### RED

Command:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'hook or route or rollback' --tb=short
```

Output:

```text
FFFFF                                                                    [100%]
5 failed, 10 deselected in 0.23s
```

Key failures:

- `ImportError: cannot import name 'stage_hook'`
- `ImportError: cannot import name 'rollback_dry_run'`
- `ImportError: cannot import name 'route_smoke'`
- CLI rejected `route-smoke` because the subcommand did not exist yet

### GREEN

Command:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'hook or route or rollback' --tb=short
```

Output:

```text
.....                                                                    [100%]
5 passed, 10 deselected in 0.20s
```

## Final verification

Command:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py --tb=short
```

Output:

```text
...............                                                          [100%]
15 passed in 0.56s
```

Command:

```bash
smoke_root=$(mktemp -d /tmp/phase-d-fixture-XXXXXX) && ./scripts/python.sh scripts/phase_d_canary.py route-smoke --root "$smoke_root" --message-id d1-1 --message 'status das candidaturas' --route-only
```

Observed output on a fresh temp root:

```json
[
  {
    "deduplicated": false,
    "message": "status das candidaturas",
    "message_id": "d1-1"
  },
  {
    "deduplicated": true,
    "message": "status das candidaturas",
    "message_id": "d1-1"
  }
]
```

Interpretation:

- The CLI exercised `telegram_harness_adapter` successfully.
- Using a fresh temp root produced the expected deterministic `false -> true` deduplication sequence for the same `message_id`.

## Commands executed

```bash
sed -n '1,260p' /opt/agent-projects/candidaturas/.superpowers/sdd/2026-08-13-phase-d-vagas-bot-01-canary/task-2-brief.md
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git status --short
rg -n "CanaryTarget|preflight|stage_hook|route_smoke|rollback_dry_run|vagas_bot_01|vagas_bot_02|install_hermes_harness_hook|telegram_harness_adapter" app/src app/scripts app/tests app/TELEGRAM_HARNESS_RUNBOOK.md
git show --stat --oneline 6610400
sed -n '1,260p' app/src/career/services/canary_control.py
sed -n '1,260p' app/scripts/phase_d_canary.py
sed -n '1,320p' app/tests/test_phase_d_canary.py
sed -n '1,220p' app/TELEGRAM_HARNESS_RUNBOOK.md
sed -n '1,260p' app/scripts/install_hermes_harness_hook.py
sed -n '1,260p' app/scripts/telegram_harness_adapter.py
sed -n '1280,1385p' app/scripts/selftest_phases.py
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'hook or route or rollback' --tb=short
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py --tb=short
./scripts/python.sh scripts/phase_d_canary.py route-smoke --root /tmp/phase-d-fixture --message-id d1-1 --message 'status das candidaturas' --route-only
smoke_root=$(mktemp -d /tmp/phase-d-fixture-XXXXXX) && ./scripts/python.sh scripts/phase_d_canary.py route-smoke --root "$smoke_root" --message-id d1-1 --message 'status das candidaturas' --route-only
git diff -- app/src/career/services/canary_control.py app/scripts/phase_d_canary.py app/tests/test_phase_d_canary.py app/TELEGRAM_HARNESS_RUNBOOK.md
```

## Concerns

1. The brief’s pytest path uses `../.venvs/hermes-dev/bin/python` from `app/`, but the actual environment here resolved to `/opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python`; I used the real path and kept the rest of the command unchanged.
2. `route-smoke` is intentionally deterministic and cache-backed. Reusing the same `--root` and `--message-id` across runs will make later smoke executions start already deduplicated. For a clean first-pass smoke, use a fresh temp root.
3. Formal subagent code review was not executed because this harness did not expose the multi-agent reviewer flow described by the superpowers skill set.

## Fix round 1

Status: implemented

Commit: `fix: tighten phase D canary hook contract`

### Tests

RED:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'backup or compose_resolves or ephemeral_root or route_smoke_cli_creates or stage_hook_apply' --tb=short
```

```text
FFF                                                                      [100%]
3 failed, 14 deselected in 0.22s
```

GREEN focused:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py -k 'backup or compose_resolves or ephemeral_root or route_smoke_cli_creates or stage_hook_apply' --tb=short
```

```text
...                                                                      [100%]
3 passed, 14 deselected in 0.20s
```

Task 2 suite:

```bash
PYTHONPATH=src:scripts /opt/agent-projects/candidaturas/.venvs/hermes-dev/bin/python -m pytest -q tests/test_phase_d_canary.py --tb=short
```

```text
.................                                                        [100%]
17 passed in 0.73s
```

Smoke:

```bash
./scripts/python.sh scripts/phase_d_canary.py route-smoke --message-id d1-fix1 --message 'status das candidaturas' --route-only
```

Observed:

```json
[
  {
    "deduplicated": false,
    "message_id": "d1-fix1"
  },
  {
    "deduplicated": true,
    "message_id": "d1-fix1"
  }
]
```

### Concerns

1. The canary contract is now explicitly split from the legacy generic installer: the generic script still defaults to `config.yaml`, while the Phase D canary wrapper only accepts the compose-resolved host path for `vagas_bot_01/hermes.config.json` and reports `hermes.config.json.bak.harness`.
2. `route-smoke` without `--root` now creates a fresh ephemeral temp root per execution. Reusing an explicit root remains intentionally stateful because deduplication is file-backed.
3. Formal subagent code review still was not executed because this harness does not expose the multi-agent reviewer flow described by the superpowers skills.
