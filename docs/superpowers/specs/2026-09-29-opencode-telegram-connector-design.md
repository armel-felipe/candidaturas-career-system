# OpenCode Telegram connector for candidaturas

## Purpose

Connect the existing Telegram bot `vagas_bot_02` to OpenCode so messages from
Telegram can control the canonical project at
`/opt/agent-projects/candidaturas`. Keep `vagas_bot_01` available for Hermes,
with one selected agent runtime at a time. OpenCode sessions must also be
reachable from the VS Code SSH terminal.

The concern motivating this change is Hermes leaving the project's canonical
workflow, including by creating parallel skills. The user has not observed that
behavior with OpenCode. This design keeps OpenCode pointed at the project's
existing `opencode.json` and `AGENTS.md`; it does not add new permission rules
based on the earlier ownership hypothesis.

## Selected integration

Use the community project
[`Tah10n/opencode-telegram-connector`](https://github.com/Tah10n/opencode-telegram-connector),
pinned to commit `d54a14683960e0848dc5cc8d3c0d5dd142ed006d` after source review.
It is a Telegram connector that uses OpenCode's server API, not an official
OpenCode plugin. Its source uses Node built-ins and internal modules; the
lockfile has no runtime package dependencies. It supports configured project
aliases, an authorized Telegram user ID, directory-aware event routing, and
attaching a terminal to the same OpenCode session.

The alternative `agentjoey/opencode-remote-control` is a true in-process plugin,
but its installer adds a global plugin and writes bot credentials to the source
repository's `.env`. Its workspace controls enumerate and switch across
workspaces. Those defaults do not meet the requirement to confine this Telegram
bot to one project without adapting upstream code. The selected connector has a
more suitable project binding model, though its upstream package is new and
requires a pinned source install and review.

## Runtime shape

- The connector is configured with exactly one project alias whose absolute
  directory is `/opt/agent-projects/candidaturas`.
- The connector starts or monitors one `opencode serve` instance for that
  directory on loopback only. No OpenCode API port is exposed publicly.
- Telegram authorization is restricted to the existing owner ID for
  `vagas_bot_02`. Connector permission-profile editing is disabled so Telegram
  cannot rewrite the project's `opencode.json` through `/permissions`.
- Run the connector under a dedicated systemd unit as root, preserving the
  existing OpenCode binary and provider auth context in `/root`. Keep its
  source/config and persistent Telegram/session state outside the project tree;
  keep the user ID in a root-only environment file and the bot token in a
  root-only systemd credential file, never in Git, child process environments,
  or service output.
- The host's system Node.js is 18.19.1, while this connector requires Node.js 20
  or newer. Use the isolated Node.js 24.19.0 runtime; do not replace system Node.
- In OpenCode mode, stop the `vagas_bot_01` Hermes gateway before starting
  `vagas_bot_02` with the connector. In Hermes mode, stop the connector and its
  managed OpenCode server before starting `vagas_bot_01`. The selector must
  refuse a switch while a run is active and must not leave both Telegram
  gateways enabled after a failed transition.
- In OpenCode mode, the VS Code SSH terminal uses `opencode attach` to connect
  to the same server/session. The operating instructions will treat this as the
  same selected runtime, not a second worker. When Hermes is selected, users
  must stop the OpenCode connector/server before starting an independent
  OpenCode session in this project.

## Project behavior and boundaries

- OpenCode starts with the canonical project directory so its existing
  `opencode.json` loads `AGENTS.md` and the project's established instructions.
- The connector config exposes only the `candidaturas` alias. It does not
  provide a Telegram route to add arbitrary project paths.
- Use OpenCode server port `4196` on `127.0.0.1`; the selector checks
  `/session/status?directory=...` before switching away from OpenCode. No public
  reverse proxy or tunnel is configured.
- Preserve the project's current OpenCode permissions and skill governance.
  Disable only the connector's command for editing permission profiles.
- Reuse the existing `vagas_bot_02` token and authorized Telegram user ID
  without printing either value. Do not change `vagas_bot_01` credentials.
- Runtime state and logs stay outside the project and have restrictive file
  permissions. Installation must not rewrite `.env`, candidate data, or existing
  skill files.

## Operational interface

Provide a documented, explicit runtime selector with two modes:

- `hermes`: only the `vagas_bot_01` Hermes gateway is active.
- `opencode`: only the `vagas_bot_02` Telegram connector is active, with its
  OpenCode server available for Telegram and `opencode attach`.

The selector reports the current mode, refuses switching during active work,
stops the current mode before starting the other, and reports a recoverable
failure if the new mode cannot start. The project runbook documents manual
status, start/stop, and log commands. Existing runner-selection code may be
reused where it applies, but it does not replace the service-level exclusivity
required here.

## Failure handling

- Invalid or missing Telegram credentials and an empty allowed-user setting
  fail closed; do not start polling without an authorized user.
- OpenCode health or SSE failures remain visible in systemd logs and the bot's
  status response. The connector's project-scoped routing stays fail-closed if
  OpenCode omits directory metadata.
- A failed runtime transition leaves at most one Telegram gateway active. The
  status command reports the observed services instead of inferring success
  from saved configuration.
- Stop/restart actions use the connector's confirmation workflow. No
  destructive clearing of connector state or project/session data is automatic.

## Acceptance criteria

1. `vagas_bot_02` responds to the authorized Telegram user and sends prompts
   only to an OpenCode session rooted at `/opt/agent-projects/candidaturas`.
2. The same session can be attached from the SSH terminal with OpenCode CLI.
3. Only one configured project is visible/bindable to Telegram, and unrelated
   OpenCode project events are not mirrored to this bot.
4. Selecting OpenCode stops the Hermes Telegram gateway; selecting Hermes
   stops the connector and its OpenCode server. An active run prevents switching.
5. The service starts after reboot, credentials remain outside Git and logs,
   and the installation does not modify candidate data or canonical skills.
6. `vagas_bot_01` continues to run its existing Hermes workflow when selected.

## Implementation notes

The repository currently has a large unrelated dirty worktree. Implementation
must preserve those edits and isolate its changes. The current project operating
instructions and roadmap also describe a bot01-only deployment, so the approved
implementation must update the active-mode documentation and supersede that
deployment decision without erasing historical runtime state.

## Deployment record — 2026-09-30

The pinned source was reviewed and installed outside the project at
`/opt/agent-services/opencode-telegram-connector`. OpenCode 1.18.33's local SDK
provides `/session/status?directory=...`; the connector setup check confirmed
the existing `vagas_bot_02` token and its single authorized user, with one
expected warning because OpenCode was not yet running. Node.js 24.19.0 was
installed from the official checksum-verified binary archive. The selector
service was activated in `opencode` mode after stale database statuses were
correlated with the bot01 container restart time; those records were not
rewritten. The remaining end-to-end handoff is the user's first Telegram turn
and SSH attach to that same session.
