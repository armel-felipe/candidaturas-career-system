## Summary

The bundled `productivity/google-workspace` skill exposes `gmail send` for composing and sending email, but the verb has **no way to attach files**. This blocks a common job-application workflow: stage a cover letter + CV for human review via `gmail draft create` (or send directly with `gmail send`) and ship the CV as a real attachment, not a link.

## Reproduction

1. Set up the skill normally (`python scripts/setup.py`, complete OAuth).
2. From any gateway (Telegram/Slack/CLI), ask the agent to send an application email with the CV attached.
3. Agent builds the body fine, then has no skill-provided way to attach `outputs/cv.docx`. Workarounds: drop the attachment from the email entirely, fall back to ad-hoc Python outside the skill, or paste a OneDrive link into the body (recipient friction).

## Where the gap is

`skills/productivity/google-workspace/scripts/google_api.py::gmail_send` builds the message via `MIMEText` only:

```python
message = MIMEText(args.body, "html" if args.html else "plain")
```

…and ships the raw message to `users().messages().send()`. There is no MIME multipart handling, no file argument parser, no per-file MIME detection. The underlying `google-api-python-client` fully supports attachments — the gap is purely in the skill's CLI surface.

## Suggested fix

Add `--attach PATH` (repeatable, `action="append"`) to the `gmail send` parser, and a small attachment branch in the message-building path that switches to `MIMEMultipart` when any attachments are present:

```python
attachments = getattr(args, "attach", []) or []

if attachments:
    message = MIMEMultipart()
    message.attach(MIMEText(args.body, "html" if args.html else "plain"))
else:
    message = MIMEText(args.body, "html" if args.html else "plain")

for path_str in attachments:
    p = Path(path_str).expanduser()
    if not p.exists():
        raise SystemExit(f"attachment not found: {p}")
    ctype, _ = guess_type(str(p))
    if ctype is None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    with p.open("rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
    message.attach(part)
```

Required imports (add near the existing `from email.mime.text import MIMEText`):

```python
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
```

## How to test

1. OAuth-setup the skill against a real Gmail account.
2. From a clean checkout, run:

   ```bash
   GAPI="python ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
   $GAPI gmail send      --to "yourself@gmail.com"      --subject "[test] attach"      --body "see attached"      --attach /etc/hostname
   ```

3. Open the resulting message in Gmail web — attachment appears under the body, filename preserved, content matches the local file (`shasum` should match between local and downloaded).
4. Repeat with no `--attach` — verify the no-attachment path still emits a `MIMEText` (backward compatible).

## Why this matters

- **Job-application workflows** (cover letter + CV) are the highest-volume outbound-email use case for the agent today.
- **Drafts + attachments** (the natural pairing once #32935 lands) enable a safe human-review pattern: stage the message, human edits body / swaps CV, then sends.
- The `has:attachment` search syntax is already documented in the skill's `references/gmail-search-syntax.md`, so the read side is supported — round-tripping an attachment requires the write side too.

## Related

- #22872 — attachment **download** side (open) — pairs with this for full attachment round-trip.
- #23465 — `gmail attachment list/get` verbs (open) — download verbs; complement to this upload verb.
- #32935 — `gmail draft create/list/send` (open) — refactors `gmail send` into shared `_build_message_raw()` helper. Our patch should sequence **after** this PR merges so the `attachments` kwarg can land in the shared helper rather than re-introducing duplication. Comment left on that PR with sequencing notes.

## Implementation notes

- **No new OAuth scopes** required — `gmail.send` + `gmail.modify` already authorize arbitrary MIME bodies including attachments.
- **Cross-platform** — pure Python (`email.mime.*`, `mimetypes`, `pathlib`); no shell or platform-specific code.
- **Backward compatible** — `action="append"` with `default=[]` means existing invocations without `--attach` produce identical output (still `MIMEText`).
- **Test surface** — should add a unit test under `tests/skills/test_google_workspace_api.py` (the file already exists for #32935) covering: (a) `--attach` round-trips through MIME multipart, (b) multiple `--attach` flags produce multiple parts, (c) missing file path produces clear error before API call.
- **gws CLI caveat** — if `gws` binary is present, the current code routes through `_gws_binary()` and bypasses our attachment branch. Either disable that path when attachments are present, or document that attachments require the Python fallback (no `gws` installed).

## Environment

- Tested on: Ubuntu 24.04 (RPi 5), Python 3.11, `google-api-python-client` 2.x, `google-auth-oauthlib` 1.x.
- Hermes Agent version: latest `main` as of 2026-07-27.
- Sender account: Gmail personal (`@gmail.com`) with OAuth Desktop-app client (project: `hermes-agent`).
