# Bot02 Profile Context Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both `vagas_bot_01` and `vagas_bot_02` load the canonical project instructions and avoid runtime loops caused by truncated context, oversized stale skills, and an incompatible scanner binary.

**Architecture:** Keep maintenance in `.agents/skills/`, expose that tree as the profile's external read-only skill source, and remove the profile-local duplicate of `processe-a-vaga` so local precedence cannot select the 100KB legacy copy. Use the same `max_turns: 150` and `context_file_max_chars: 80000` in both profiles. The operator explicitly chose definitive deletion of the obsolete profile copy; no archive is retained. Disable the incompatible scanner explicitly because no verified x86_64 replacement exists.

**Tech Stack:** YAML profile config, Hermes skill discovery, Docker Compose, shell/file architecture checks, pytest runtime checks.

**Spec:** `docs/roadmap.md` item `RUNTIME-013` and the canonical skill governance in `AGENTS.md`.

## Global Constraints

- Do not put new source-of-truth skills outside `.agents/skills/`.
- The obsolete `vagas_bot_02` profile copy of `processe-a-vaga` is explicitly authorized for deletion; do not delete the canonical `.agents/skills/processe-a-vaga`.
- Do not expose or copy API keys; this plan changes routing and context only.
- A scanner with the wrong architecture must not be invoked repeatedly; use a known compatible binary or an explicit fail-open disablement.

### Task 1: Add a profile-context regression

**Files:**
- Create: `tests/test_bot02_profile_context.py`
- Read: `hermes/vagas_bot_01/config.yaml`, `hermes/vagas_bot_02/config.yaml`, `AGENTS.md`, `.agents/skills/processe-a-vaga/SKILL.md`

**Interfaces:**
- Consumes: profile configuration and canonical skill paths.
- Produces: checks that the configured context cap contains `AGENTS.md`, the canonical skill is below the Hermes skill limit, and the runtime profile path is explicit.

- [x] **Step 1: Write the failing test**

```python
from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


def test_bot02_context_and_canonical_skill_fit_runtime_limits() -> None:
    config = (ROOT / "hermes/vagas_bot_02/config.yaml").read_text(encoding="utf-8")
    match = re.search(r"^context_file_max_chars:\s*(\d+)\s*$", config, re.MULTILINE)
    assert match is not None
    assert int(match.group(1)) >= (ROOT / "AGENTS.md").stat().st_size
    assert (ROOT / ".agents/skills/processe-a-vaga/SKILL.md").stat().st_size < 100_000
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_bot02_profile_context.py`

Expected: FAIL because the active cap is 70,000 while `AGENTS.md` is larger.

### Task 2: Align both profiles to canonical instructions

**Files:**
- Modify: `hermes/vagas_bot_01/config.yaml`
- Modify: `hermes/vagas_bot_02/config.yaml`
- Delete: `hermes/vagas_bot_02/skills/software-development/processe-a-vaga/`

- [x] **Step 1: Raise the profile context cap**

Change `context_file_max_chars: 70000` to `context_file_max_chars: 80000`, which contains the current 71,227-byte `AGENTS.md` without changing the project-wide file.

- [x] **Step 2: Delete the stale local skill**

Delete the exact directory `hermes/vagas_bot_02/skills/software-development/processe-a-vaga/`. The canonical `.agents/skills/processe-a-vaga/SKILL.md` remains intact and is the only discovered copy. No archive is retained, per the operator's explicit decision.

- [x] **Step 3: Configure canonical external skills**

Add this profile configuration:

```yaml
skills:
  external_dirs:
    - /workspace/candidaturas/.agents/skills
```

The local duplicate is removed first, so the canonical `processe-a-vaga` is discovered through the external tree rather than shadowed by the legacy copy.

### Task 3: Resolve the `tirith` architecture mismatch safely in both profiles

- [x] **Step 1: Inspect the binary architecture**

Run: `file hermes/vagas_bot_01/bin/tirith hermes/vagas_bot_02/bin/tirith` and `docker compose exec -T vagas_bot_01 uname -m`, `docker compose exec -T vagas_bot_02 uname -m`.

Expected: the profile binary is `ARM aarch64` while the container is `x86_64`.

- [x] **Step 2: Use a compatible binary or disable only this scanner**

If an x86_64 `tirith` already exists in the image or repository, configure its absolute runtime path in both profiles. If none exists, set `security.tirith_enabled: false` in both profiles with a comment documenting the architecture mismatch and preserving the existing fail-open behavior. Do not download an unverified binary.

### Task 4: Restart and verify both profiles

- [x] **Step 1: Restart the two bot services**

Run: `docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02`.

- [x] **Step 2: Verify startup logs**

Run: `docker compose logs --tail=120 vagas_bot_01 vagas_bot_02`.

Expected: no new `AGENTS.md TRUNCATED`, no repeated `Exec format error`, and no skill content over-limit warning for `processe-a-vaga`.

- [x] **Step 3: Run tests and update roadmap**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_bot02_profile_context.py tests/test_runtime_provider_config.py tests/test_harness_dispatch.py` and `git diff --check`. Mark `RUNTIME-013` `DONE` only when the profile smoke and all checks pass; otherwise record the remaining external dependency as `BLOCKED`.

**Execution evidence (2026-08-28):** both profiles use `max_turns: 150`,
`context_file_max_chars: 80000`, and the canonical external skill directory;
the obsolete bot02 `processe-a-vaga` directory was deleted. Both containers
were recreated, run as UID 10000 for Hermes, and the runtime discovery found
only `/workspace/candidaturas/.agents/skills/processe-a-vaga/SKILL.md` (6,233
bytes). No new truncation, skill-size, or Tirith architecture errors appeared
in the startup/runtime log window. The profile and dispatch tests passed 10/10.
