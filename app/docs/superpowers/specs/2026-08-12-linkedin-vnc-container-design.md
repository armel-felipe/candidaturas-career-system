# LinkedIn VNC Container Design

**Goal:** Make manual LinkedIn authentication work for `vagas_bot_01` on the current Docker deployment at `/opt/agent-projects/candidaturas`.

## Context

The active deployment uses `compose.yaml` at the workspace root. The service
`hermes-vagas-bot-01` runs the Hermes gateway as UID `10000` in a container,
with the project mounted at `/workspace/candidaturas` and the agent state
mounted at `/workspace/candidaturas/.career-state`. The image already contains
`Xvfb`, but not `x11vnc`, `fluxbox`, `novnc`, or `websockify`.

Installing packages on the host does not fix the container. The system GUI
dependencies therefore belong in `hermes-src/Dockerfile`. The host must expose
the container's localhost-only noVNC listener through an equally localhost-only
Docker port mapping so the operator can use an SSH tunnel.

## Design

1. Add the four missing Debian packages to the production Hermes image.
2. Make the canonical scripts in `app/scripts/*linkedin_browser_gateway*.sh`
   implement the Linux/container flow, while retaining macOS local behavior.
3. Keep the gateway state under `.career-state/browser-gateway` and LinkedIn
   browser data under `.career-state/browser/linkedin`, which resolves to the
   existing per-agent state mount.
4. Publish noVNC only on host loopback: `6081 -> 6080` for `vagas_bot_01` and
   `6082 -> 6080` for `vagas_bot_02`.
5. Update the runbook and deployment README to use the current host layout and
   `docker compose`, without referring to the obsolete `/opt/candidaturas`
   layout, RPi5, or duplicate scripts whose filenames contain ` 2`.

## Operational Flow

On the server, rebuild and recreate the target service. Start the gateway
inside `vagas_bot_01`, keep its x11vnc listener bound to container loopback and
let websockify listen on the container interface for Docker forwarding,
and create an SSH tunnel from the operator machine to host port `6081`. The
operator opens the tunneled noVNC URL and completes LinkedIn authentication.
The Playwright process runs in the same container and therefore reuses the
same mounted browser profile.

## Failure Handling

- Missing GUI binaries produce a concrete dependency error with the image
  rebuild command.
- A stale or dead PID is treated as stopped and can be restarted safely.
- The noVNC listener is never bound to a public interface.
- Authentication remains manual; passwords, CAPTCHA, and 2FA are not
  automated or stored by the scripts.

## Verification

- `docker compose config` succeeds.
- Shell scripts pass `bash -n`.
- The rebuilt container contains all five required commands/files.
- The gateway starts, reports all four processes as running, and writes the
  expected `DISPLAY`/noVNC environment file.
- The service remains reachable only through the localhost port mapping.
