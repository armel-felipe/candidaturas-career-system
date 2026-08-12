# Hermes workspace write roots — design

## Goal

Allow both active vacancy bots to persist their per-bot application state, inbox files, and outputs under `/workspace/candidaturas` without expanding write access to the application code or mounted environment file.

## Chosen approach

Override `HERMES_WRITE_SAFE_ROOT` in the active Compose file for both services with a colon-separated allowlist:

```text
/opt/data:/workspace/candidaturas
```

`/opt/data` retains the Hermes runtime location already allowed by the image. Docker continues to enforce the finer boundaries: `app` and `.env` are read-only mounts; `.career-state`, `inbox`, and `outputs` are the only writable mounts below `/workspace/candidaturas`.

## Alternatives considered

1. Allow only the three writable subdirectories. This is marginally narrower but ties the safety setting to the current directory layout and can break legitimate pipeline paths added under the existing workspace boundary.
2. Allow `/tmp` as well. Rejected: the failed temporary write is not a persistent pipeline artifact, and widening the temporary filesystem is unnecessary.

## Validation

Recreate both services through Docker Compose, verify the effective container environment, then perform non-destructive write probes in `.career-state`, `inbox`, and `outputs`. Confirm that writes to the read-only app mount and `.env` remain rejected by the filesystem.
