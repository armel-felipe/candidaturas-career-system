# Task 1 report — migration regression guard

## Delivered

- Added `tests/test_project_structure.py` exactly as specified in the task brief.
- Committed the red regression test as `f92b875adc3e8afd7f53570615622d895c85a77d` (`test: require agents skill root`).

## Focused test evidence

Required command:

```text
pytest tests/test_project_structure.py::test_agents_skill_root_is_canonical_and_valid -v
```

Result: failed during collection with `ModuleNotFoundError: No module named 'scripts'`. The existing `tests/conftest.py` adds only `src` to `sys.path`; `scripts` is not an importable package under the command's default environment.

To verify the intended red condition without changing the prescribed test, I also ran:

```text
PYTHONPATH=. pytest tests/test_project_structure.py::test_agents_skill_root_is_canonical_and_valid -v
```

Result: one collected test, failed at the expected first assertion because `.agents/skills/career-system/SKILL.md` does not yet exist.

## Self-review

- The test imports `scripts.validate_project_structure`, checks the canonical `.agents` skill path, rejects `.opencode`, requires `main() == 0`, and checks the success output.
- `git diff --check` and `git show --check --stat --oneline HEAD` reported no whitespace errors.
- Scope stayed limited to the requested test; no migration implementation or validator changes were made.

## Concern

The literal required pytest command currently cannot import `scripts`. A later task should make that import available in the standard pytest environment (for example through test path configuration or package setup); this task intentionally did not expand scope beyond the specified red test.

## Fix report — test infrastructure import path

### Root cause and smallest adjustment

`tests/conftest.py` inserted only `<repo>/src` into `sys.path`. The prescribed test imports `scripts.validate_project_structure`, which lives under `<repo>/scripts`; therefore pytest failed in collection before evaluating the intended migration assertion. The test body was left unchanged. The conftest bootstrap now defines `ROOT` once and inserts both `<repo>` and `<repo>/src`, making the repository-level `scripts` namespace importable in the standard test environment.

### Command output summary

Required command, after the fix:

```text
pytest tests/test_project_structure.py::test_agents_skill_root_is_canonical_and_valid -v
```

Result: collection succeeded (`collected 1 item`). The test failed at the expected red assertion on line 10 because `.agents/skills/career-system/SKILL.md` does not yet exist:

```text
AssertionError: assert False
```

This is the expected pre-migration failure; the previous `ModuleNotFoundError: No module named 'scripts'` collection failure is resolved.
