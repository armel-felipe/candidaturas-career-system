# LinkedIn VNC Container Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable manual LinkedIn login through noVNC in the current `vagas_bot_01` Docker container and align related documentation and scripts with the current server layout.

**Architecture:** Bake GUI dependencies into the Hermes image, run the gateway in the same agent container as Playwright, and publish noVNC only on host loopback through a per-service port. Use the existing per-agent `.career-state` mount for gateway metadata and the LinkedIn profile.

**Tech Stack:** Docker Compose, Debian Dockerfile, Bash, Node.js/Playwright, Markdown.

## Global Constraints

- Current host project root: `/opt/agent-projects/candidaturas`.
- Current container project root: `/workspace/candidaturas`.
- Current target service: `vagas_bot_01` / `hermes-vagas-bot-01`.
- Runtime gateway user: UID/GID `10000`; do not require sudo inside the container.
- noVNC must remain reachable only through host loopback and SSH forwarding.
- Do not automate LinkedIn passwords, CAPTCHA, or 2FA.

### Task 1: Add GUI dependencies to the Hermes image

**Files:** Modify `hermes-src/Dockerfile` in the existing apt package list.

- [ ] Verify the current container lacks `x11vnc`, `fluxbox`, `websockify`, and `/usr/share/novnc`.
- [ ] Add `xvfb x11vnc fluxbox novnc websockify` to the image package list.
- [ ] Rebuild/recreate both services and verify all commands/files exist inside `hermes-vagas-bot-01`.

Verification:

```bash
docker compose build vagas_bot_01 vagas_bot_02
docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02
docker exec hermes-vagas-bot-01 sh -lc 'command -v Xvfb && command -v x11vnc && command -v fluxbox && command -v websockify && test -d /usr/share/novnc'
```

### Task 2: Canonicalize the gateway scripts

**Files:** Modify the four canonical scripts under `app/scripts/` and the
`linkedin:browser:*` entries in `app/package.json`.

- [ ] Verify the current canonical Linux command incorrectly reports local mode.
- [ ] Move the Linux behavior from the temporary scripts with ` 2` in their names into the canonical scripts, preserving macOS local mode.
- [ ] Make dependency installation a Docker-image preflight; it must not run `sudo apt-get` inside the agent container.
- [ ] Point npm scripts at the canonical filenames and remove operator-facing references to the temporary filenames.
- [ ] Run `bash -n` on all four scripts and start/status the gateway as UID `10000` inside the container.

Verification:

```bash
bash -n app/scripts/install_linkedin_browser_gateway_deps.sh
bash -n app/scripts/start_linkedin_browser_gateway.sh
bash -n app/scripts/status_linkedin_browser_gateway.sh
bash -n app/scripts/stop_linkedin_browser_gateway.sh
docker exec --user 10000 hermes-vagas-bot-01 sh -lc 'cd /workspace/candidaturas && npm run linkedin:browser:start && npm run linkedin:browser:status'
```

Expected: the four gateway processes report `running` and the environment
contains `DISPLAY=:99`.

### Task 3: Publish loopback-only noVNC ports

**Files:** Modify `compose.yaml` for services `vagas_bot_01` and `vagas_bot_02`.

- [ ] Add `127.0.0.1:6081:6080` to `vagas_bot_01`.
- [ ] Add `127.0.0.1:6082:6080` to `vagas_bot_02`.
- [ ] Validate the Compose model and inspect the recreated port mapping.

Verification:

```bash
docker compose config
docker compose up -d --force-recreate vagas_bot_01 vagas_bot_02
docker port hermes-vagas-bot-01 6080
```

Expected: port 6080 maps to host `127.0.0.1:6081` and is not published on a
public interface.

### Task 4: Align documentation and deployment references

**Files:** Modify `app/LINKEDIN_AUTH_RUNBOOK.md`,
`app/deploy/hermes/README.md`, `app/deploy/hermes/compose.yaml`, and
`app/deploy/hermes/migrate-to-vps.sh`.

- [ ] Replace `/opt/candidaturas`, RPi5, and temporary-script assumptions with the current host/container paths and service names.
- [ ] Document image rebuild, `docker compose exec`, the `6081` SSH tunnel, the noVNC URL, authentication, extraction, and shutdown.
- [ ] Align the secondary deployment compose/migration references with the current root compose or explicitly mark them as legacy so they cannot be mistaken for the active deployment.
- [ ] Confirm targeted search finds no stale operational references.

Verification:

```bash
rg -n --glob '!node_modules/**' --glob '!*.lock' '/opt/candidaturas|RPi5|linkedin_browser_gateway.* 2\\.sh| 2\\.sh' app/LINKEDIN_AUTH_RUNBOOK.md app/deploy/hermes app/package.json
```

Expected: no stale operational references remain in the targeted files.

### Task 5: Final verification and handoff

- [ ] Run `cd app && npm run validate:structure`.
- [ ] Confirm gateway status inside the target container.
- [ ] Confirm `curl -fsS http://127.0.0.1:6081/vnc.html` succeeds.
- [ ] Provide the operator commands for the SSH tunnel, noVNC URL, container auth command, authenticated extraction, and gateway shutdown.

