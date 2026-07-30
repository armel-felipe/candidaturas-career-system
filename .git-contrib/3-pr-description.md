## What does this PR do?

Adds `--attach PATH` (repeatable) to `gmail send` in the `productivity/google-workspace` skill, so the agent can ship email with real file attachments via MIME multipart instead of forcing a OneDrive link in the body. Mirrors the same flag on `gmail draft create` so humans can review attached CVs before send.

## Why?

Job-application flows are the highest-volume outbound-email use case for the agent today. Cover letter + CV is the standard shape; shipping the CV as a real attachment matches how the recipient (HR / hiring manager) expects to receive it. The skill already supports `has:attachment` searches on the read side (#22872, #23465 cover the download side), but the upload path was a gap.

## Changes

- `scripts/google_api.py`
  - New imports: `MIMEMultipart`, `MIMEBase`, `encoders`.
  - New parser arg on `gmail send` and `gmail draft create`: `--attach PATH` (`action="append"`, `default=[]`).
  - Refactored `_build_message_raw()` (added by #32935) to accept an optional `attachments: list[str] = []` kwarg. When empty, behavior is byte-identical to the current helper. When non-empty, switches to `MIMEMultipart`, attaches a `MIMEText` body part, then appends one `MIMEBase` part per file with auto-detected MIME type (`mimetypes.guess_type` → `application/octet-stream` fallback) and `Content-Disposition: attachment; filename="<basename>"` so the recipient sees the original filename.
  - Errors out **before** any API call if an attachment path is missing (`raise SystemExit(f"attachment not found: {p}")`), so partial-send failures don't reach the server.

- `SKILL.md`
  - Added `--attach` to the `gmail send` documentation block with usage examples and a note about the `gws` CLI caveat.

- `tests/skills/test_google_workspace_api.py`
  - Three new test cases (added to the suite that #32935 already extended):
    1. Single `--attach` round-trips: the message body contains the file bytes under a `Content-Disposition: attachment` part with the original filename.
    2. Multiple `--attach` flags produce multiple parts, in the order specified on the command line.
    3. Missing file path raises `SystemExit` with a clear message **before** any HTTP call to the Gmail API.

## Sequencing

This PR targets the `_build_message_raw()` refactor from #32935. If that PR hasn't merged yet, this should rebase on top of it before review. If it has merged, this is a clean follow-up.

I left a comment on #32935 proposing this sequencing; copying it here so reviewers can see the dependency in one place.

## How to test

End-to-end (requires OAuth setup):

```bash
GAPI="python ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"

# Single attachment
$GAPI gmail send   --to "yourself@gmail.com"   --subject "[test] single attach"   --body "see attached"   --attach /etc/hostname

# Multiple attachments
$GAPI gmail draft create   --to "yourself@gmail.com"   --subject "[test] multi attach"   --body "drafts with attachments"   --attach /etc/hostname   --attach /etc/os-release

# Backward compatibility (no --attach)
$GAPI gmail send   --to "yourself@gmail.com"   --subject "[test] no attach"   --body "no body parts added"
```

Then in Gmail web:

1. Open each message — verify attachment filename is preserved and content matches the local file (`shasum` should match).
2. For the multi-attach draft — confirm both parts are listed in the draft and ordered as on the command line.
3. For the no-attach case — confirm the message is plain `text/plain` (no multipart/related wrapper).

Unit tests:

```bash
pytest tests/skills/test_google_workspace_api.py -v -k "attach"
```

## What platforms did you test on?

- Ubuntu 24.04 (RPi 5), Python 3.11, `google-api-python-client` 2.x, `google-auth-oauthlib` 1.x
- Hermes Agent `main` branch, last verified 2026-07-27
- Sender account: Gmail personal (`@gmail.com`) with OAuth Desktop-app client

Not tested (please flag if you want me to): macOS, Windows/WSL2 — should work (pure Python `email` and `mimetypes` modules, no platform-specific code), but worth a sanity pass before merge.

## Conventional Commits

```
feat(google-workspace): add --attach to gmail send and gmail draft create
```

## Checklist

- [x] Tests added (`tests/skills/test_google_workspace_api.py`)
- [x] Manual end-to-end test passed (single + multi attach, draft + send)
- [x] Backward compatibility verified (no-attach path byte-identical to current behavior)
- [x] Cross-platform consideration: pure-Python, no platform-specific code
- [x] No new OAuth scopes (gmail.send + gmail.modify already authorize arbitrary MIME)
- [x] SKILL.md updated with usage examples

## Related

- #22872 — attachment **download** side (open). Combined with this PR, full attachment round-trip works.
- #23465 — `gmail attachment list/get` verbs (open). Download-side complement.
- #32935 — `gmail draft create/list/send` + `_build_message_raw()` refactor (open). This PR depends on the helper refactor landing first so we extend a single MIME builder rather than re-duplicate.
