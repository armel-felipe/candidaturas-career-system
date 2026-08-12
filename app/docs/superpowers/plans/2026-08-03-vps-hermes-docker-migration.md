# VPS Hermes Docker Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the career-system workspace and the `vagas_bot_01` and `vagas_bot_02` Hermes profiles on the Hostinger VPS in isolated, persistent Docker Compose services.

**Architecture:** The project code and shared application state live in persistent directories under `/opt/candidaturas`. Each Hermes container mounts the shared workspace and only its own profile directory as `HERMES_HOME`; all service communication uses an internal Docker network without public ports.

**Tech Stack:** Ubuntu 24.04, Docker Engine 29.7.1, Docker Compose v5.4.0, Hermes Agent v0.18.2, Python 3.12, Node 22 in the Hermes image, rsync over SSH.

## Global Constraints

- Target host: `root@187.77.230.101`; use only the configured Ed25519 key.
- Target root: `/opt/candidaturas`; deployment secrets and profiles are never added to Git.
- Profiles are `vagas_bot_01` and `vagas_bot_02`, each with a distinct `HERMES_HOME`.
- Preserve `.career-state`, `outputs`, the project `.env`, and each profile's `.env`, `auth.json`, pairing data and SQLite files.
- Stop both local gateways before the final profile transfer; do not copy an actively written SQLite database.
- No `ports:` field is permitted initially; any later dashboard access is through SSH tunnelling.
- Retain the local source and verified snapshots until the user authorizes deletion.

---

### Task 1: Create the deployment layout and non-secret configuration

**Files:**
- Create: `deploy/hermes/.gitignore`
- Create: `deploy/hermes/README.md`
- Create: `deploy/hermes/compose.yaml`
- Create: `deploy/hermes/.env.example`
- Create on VPS: `/opt/candidaturas/{app,data,hermes,hermes-src,backups}`

**Interfaces:**
- Consumes: workspace `/home/ubuntu/projetos/candidaturas` and local Hermes profile homes.
- Produces: a root-owned VPS layout and a validated two-service Compose configuration.

- [ ] **Step 1: Create ignored local deployment conventions**

Create `deploy/hermes/.gitignore`:

```gitignore
.env
profiles/
data/
backups/
*.tar.zst
```

Create `deploy/hermes/.env.example`:

```dotenv
COMPOSE_PROJECT_NAME=candidaturas
```

Create `deploy/hermes/README.md` declaring that profiles, tokens, project `.env`, and copied data only exist outside Git at `/opt/candidaturas`.

- [ ] **Step 2: Create the target directories with strict permissions**

Run:

```bash
ssh root@187.77.230.101 'install -d -m 0700 /opt/candidaturas /opt/candidaturas/data /opt/candidaturas/hermes /opt/candidaturas/hermes-src /opt/candidaturas/backups'
```

Expected: each path exists and has mode `700`.

- [ ] **Step 3: Write the Compose configuration**

Create `deploy/hermes/compose.yaml`:

```yaml
services:
  vagas_bot_01:
    build:
      context: /opt/candidaturas/hermes-src
    image: candidaturas/hermes-agent:0.18.2
    container_name: hermes-vagas-bot-01
    restart: unless-stopped
    environment:
      HERMES_HOME: /opt/data
      HERMES_UID: "10000"
      HERMES_GID: "10000"
    volumes:
      - /opt/candidaturas/hermes/vagas_bot_01:/opt/data
      - /opt/candidaturas/app:/workspace:rw
      - /opt/candidaturas/data:/workspace/.career-state:rw
    working_dir: /workspace
    command: ["gateway", "run"]
    networks: [internal]

  vagas_bot_02:
    build:
      context: /opt/candidaturas/hermes-src
    image: candidaturas/hermes-agent:0.18.2
    container_name: hermes-vagas-bot-02
    restart: unless-stopped
    environment:
      HERMES_HOME: /opt/data
      HERMES_UID: "10000"
      HERMES_GID: "10000"
    volumes:
      - /opt/candidaturas/hermes/vagas_bot_02:/opt/data
      - /opt/candidaturas/app:/workspace:rw
      - /opt/candidaturas/data:/workspace/.career-state:rw
    working_dir: /workspace
    command: ["gateway", "run"]
    networks: [internal]

networks:
  internal:
    internal: true
```

- [ ] **Step 4: Validate configuration before transfer**

Run:

```bash
docker compose -f deploy/hermes/compose.yaml config
! rg -n '^\s*ports:' deploy/hermes/compose.yaml
```

Expected: both services render and no public port declaration exists.

- [ ] **Step 5: Commit the non-secret deployment files**

Run:

```bash
git add deploy/hermes
git commit -m 'feat: add isolated Hermes Compose deployment'
```

### Task 2: Snapshot and transfer data safely

**Files:**
- Create: `deploy/hermes/migrate-to-vps.sh`
- Create on VPS: `/opt/candidaturas/compose.yaml`
- Create on VPS: `/opt/candidaturas/backups/source-manifest-before-migration.txt`

**Interfaces:**
- Consumes: the Compose configuration from Task 1, local project state, profiles, and local Hermes source.
- Produces: verified VPS copies without applying `--delete` to any destination.

- [ ] **Step 1: Implement the guarded transfer script**

Create `deploy/hermes/migrate-to-vps.sh`. It must run distinct `rsync -aHAX --numeric-ids --info=progress2` transfers and reject a target other than `root@187.77.230.101:/opt/candidaturas/`.

Transfers:

```text
project source excluding .git/, node_modules/, .career-state/, outputs/, .env -> /opt/candidaturas/app/
.career-state                                                      -> /opt/candidaturas/data/
outputs                                                            -> /opt/candidaturas/app/outputs/
project .env                                                       -> /opt/candidaturas/.env
vagas_bot_01 profile                                               -> /opt/candidaturas/hermes/vagas_bot_01/
vagas_bot_02 profile                                               -> /opt/candidaturas/hermes/vagas_bot_02/
~/.hermes/hermes-agent excluding .git/ and .env                    -> /opt/candidaturas/hermes-src/
```

Never use `--delete`; do not echo secret file contents.

- [ ] **Step 2: Stop gateways and produce consistent archives**

Run:

```bash
systemctl --user stop hermes-gateway-vagas_bot_01.service hermes-gateway-vagas_bot_02.service
tar --zstd -cf /tmp/vagas_bot_01.tar.zst -C /home/ubuntu/.hermes/profiles vagas_bot_01
tar --zstd -cf /tmp/vagas_bot_02.tar.zst -C /home/ubuntu/.hermes/profiles vagas_bot_02
tar --test -f /tmp/vagas_bot_01.tar.zst
tar --test -f /tmp/vagas_bot_02.tar.zst
```

Expected: both services are stopped and both archive integrity checks pass.

- [ ] **Step 3: Transfer and checksum the persistent state**

Run the script. On source and VPS calculate SHA-256 sums for `career.db`, both profile `state.db` files, and both `auth.json` files. Compare values without reading or printing their contents. Save paths, byte counts, and checksum results in the VPS manifest.

- [ ] **Step 4: Install runtime files and permissions**

Copy `compose.yaml` to `/opt/candidaturas/compose.yaml`, then run:

```bash
ssh root@187.77.230.101 'chmod 600 /opt/candidaturas/.env /opt/candidaturas/hermes/vagas_bot_01/.env /opt/candidaturas/hermes/vagas_bot_02/.env && chmod 700 /opt/candidaturas/hermes/vagas_bot_01 /opt/candidaturas/hermes/vagas_bot_02'
```

Then normalize only the writable mounted directories for the Hermes runtime:

```bash
ssh root@187.77.230.101 'chown -R 10000:10000 /opt/candidaturas/data /opt/candidaturas/hermes/vagas_bot_01 /opt/candidaturas/hermes/vagas_bot_02 /opt/candidaturas/app/outputs'
```

- [ ] **Step 5: Resume local gateways after transfer verification**

Run:

```bash
systemctl --user start hermes-gateway-vagas_bot_01.service hermes-gateway-vagas_bot_02.service
systemctl --user --no-pager status hermes-gateway-vagas_bot_01.service hermes-gateway-vagas_bot_02.service
```

Expected: local services resume; local snapshot archives remain retained.

### Task 3: Build, start, and persist the VPS runtime

**Files:**
- Create on VPS: `/etc/systemd/system/candidaturas-compose.service`

**Interfaces:**
- Consumes: transferred Hermes source and the two mounted profile directories.
- Produces: running `hermes-vagas-bot-01` and `hermes-vagas-bot-02` containers enabled to start after reboot.

- [ ] **Step 1: Build the pinned image**

Run:

```bash
ssh root@187.77.230.101 'docker compose -f /opt/candidaturas/compose.yaml build --pull'
```

Expected: image `candidaturas/hermes-agent:0.18.2` is built successfully.

- [ ] **Step 2: Install project Node dependencies inside the image runtime**

Run:

```bash
ssh root@187.77.230.101 'docker compose -f /opt/candidaturas/compose.yaml run --rm vagas_bot_01 npm ci'
```

Expected: project dependencies are installed in `/workspace/node_modules`; the VPS host does not need a separate Node installation.

- [ ] **Step 3: Start and inspect the first profile**

Run:

```bash
ssh root@187.77.230.101 'docker compose -f /opt/candidaturas/compose.yaml up -d vagas_bot_01 && docker compose -f /opt/candidaturas/compose.yaml logs --tail=100 vagas_bot_01'
```

Expected: no missing-runtime, permissions, or migration errors. Do not start the second service until this is true.

- [ ] **Step 4: Start the second profile**

Run:

```bash
ssh root@187.77.230.101 'docker compose -f /opt/candidaturas/compose.yaml up -d vagas_bot_02 && docker compose -f /opt/candidaturas/compose.yaml ps'
```

Expected: both services are running and no ports are published.

- [ ] **Step 5: Add reboot reconciliation**

Create `/etc/systemd/system/candidaturas-compose.service`:

```ini
[Unit]
Description=Candidaturas Hermes Compose services
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/candidaturas
ExecStart=/usr/bin/docker compose -f /opt/candidaturas/compose.yaml up -d
ExecStop=/usr/bin/docker compose -f /opt/candidaturas/compose.yaml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Enable and prove the unit**

Run:

```bash
ssh root@187.77.230.101 'systemctl daemon-reload && systemctl enable --now candidaturas-compose.service && systemctl is-enabled candidaturas-compose.service && systemctl is-active candidaturas-compose.service'
```

Expected: output includes `enabled` and `active`.

### Task 4: Validate isolation, bindings, and recovery

**Files:**
- Modify: `deploy/hermes/README.md`
- Create on VPS: `/opt/candidaturas/backups/validation-report.txt`

**Interfaces:**
- Consumes: running services from Task 3.
- Produces: a redacted acceptance report and a documented recovery runbook.

- [ ] **Step 1: Validate project structure in the runtime**

Run:

```bash
ssh root@187.77.230.101 'docker compose -f /opt/candidaturas/compose.yaml exec -T vagas_bot_01 sh -lc \"npm run validate:structure\"'
```

Expected: zero exit status.

- [ ] **Step 2: Validate profile-specific mounts**

For each service, run:

```bash
test "$HERMES_HOME" = /opt/data
test -f "$HERMES_HOME/config.yaml"
test -f /workspace/.career-state/career.db
```

Then inspect `docker inspect` mount sources. The first service must mount only `/opt/candidaturas/hermes/vagas_bot_01` at `/opt/data`; the second must mount only the `vagas_bot_02` directory.

- [ ] **Step 3: Validate binding state from each service**

Run inside each container:

```bash
./scripts/python.sh scripts/career_cli.py applications profile-status
```

Record the command result in the acceptance report without inventing whether the profile is bound. If a binding exists, confirm that its profile identifier matches the service name.

- [ ] **Step 4: Validate exposure and restart**

Run:

```bash
ssh root@187.77.230.101 'docker ps --format \"{{.Names}} {{.Ports}}\"; docker compose -f /opt/candidaturas/compose.yaml restart vagas_bot_01; sleep 5; docker compose -f /opt/candidaturas/compose.yaml ps'
```

Expected: empty published-port columns and a running restarted profile.

- [ ] **Step 5: Publish operational recovery instructions**

Update `deploy/hermes/README.md` with exact commands for logs, status, restart, stop, and dashboard tunnelling only if a dashboard is explicitly enabled:

```bash
ssh -L 9119:127.0.0.1:9119 root@187.77.230.101
```

Commit the documentation. Keep source archives and manifests until the user explicitly authorizes removal.

