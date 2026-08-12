# Hermes Workspace Write Roots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore pipeline writes to the active bots' mounted workspace without granting application-code write access.

**Architecture:** Docker Compose injects an allowlist into each bot container. Docker bind mounts remain the enforcement layer for individual workspace subdirectories: application code and `.env` stay read-only, while state, inbox, and outputs remain per-bot writable.

**Tech Stack:** Docker Compose, Hermes `HERMES_WRITE_SAFE_ROOT`, shell write probes.

## Global Constraints

- Modify only `/opt/agent-projects/candidaturas/compose.yaml`, the Compose file that created both running containers.
- Preserve the existing `/opt/data` safe root.
- Do not permit `/tmp`.
- Recreate both bot containers so the environment override takes effect.

---

### Task 1: Configure and verify workspace writes

**Files:**
- Modify: `compose.yaml` for both `vagas_bot_01` and `vagas_bot_02`
- Test: Docker Compose effective configuration and container write probes

**Interfaces:**
- Consumes: `HERMES_WRITE_SAFE_ROOT` as an OS-path-separated allowlist.
- Produces: Both containers receive `/opt/data:/workspace/candidaturas`.

- [x] **Step 1: Add the safe-root environment override**

Add this exact value to each service's `environment` mapping:

```yaml
HERMES_WRITE_SAFE_ROOT: /opt/data:/workspace/candidaturas
```

- [x] **Step 2: Validate the rendered Compose configuration**

Run:

```bash
docker compose config
```

Expected: both services contain `HERMES_WRITE_SAFE_ROOT: /opt/data:/workspace/candidaturas`.

- [x] **Step 3: Recreate the services**

Run:

```bash
docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02
```

Expected: both services are recreated and running.

- [x] **Step 4: Verify the runtime boundary**

Run controlled `docker exec` probes that create and remove unique files in each bot's `.career-state`, `inbox`, and `outputs` mounts. Attempt a write in `/workspace/candidaturas/src` and verify it fails because the application mount is read-only.

- [x] **Step 5: Record the configuration change**

Run `git status --short` if a repository is present. This deployment directory has no Git metadata, so record the exact changed file and the live verification results in the handoff instead of committing.
