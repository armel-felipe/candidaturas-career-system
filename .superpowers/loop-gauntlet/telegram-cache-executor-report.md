# Telegram Cache Executor Report

Date: 2026-09-01
Base commit: `8948126183b8cdd0077b41878907dfb83c0b0ced`

## Files Changed

- `src/career/services/harness_runs.py`
- `tests/test_cell_workspace_safety.py`
- `.superpowers/loop-gauntlet/telegram-cache-executor-report.md`

## RED

- Added test:
  - `test_cellular_harness_blocks_symlink_outside_message_cache_even_when_target_is_inside`
- Command:
  - `PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py -k 'symlink_outside_message_cache_even_when_target_is_inside'`
- Result:
  - `1 failed, 58 deselected`
- Failure mode:
  - `run.inspect()` returned `status == "ok"` even after creating `.career-state/telegram/delivery-state.json` as a symlink to `.career-state/telegram/messages/cached.json`.
  - This reproduced the reviewer blocker: the snapshot ignored a protected lexical path outside `messages/` because it resolved into the cache.

## GREEN

- Minimal production change:
  - `_protected_workspace_snapshot()` now decides the Telegram cache exclusion from the lexical `path`, not from `path.resolve()`.
  - Snapshot keys also stay lexical, so a symlink at `.career-state/telegram/delivery-state.json` is recorded and blocked even when its target lives under `.career-state/telegram/messages/`.

- `PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py -k 'symlink_outside_message_cache_even_when_target_is_inside'`
- Result: `1 passed, 58 deselected`

- `PYTHONPATH=src .venv/bin/pytest -q tests/test_cell_workspace_safety.py`
- Result: `59 passed in 8.57s`

- `git diff --check`
- Result: clean

## Scope Decision

The fix stayed limited to `_protected_workspace_snapshot()` plus one regression test for the symlink bypass. The lexical cache directory `.career-state/telegram/messages/` remains ignored, while any lexical sibling under `.career-state/telegram/` remains protected even if it points into the cache via symlink. No candidatura artifacts, FIT_MAP data, provenance, SQLite contents, outputs, configs, or cron paths were changed.
