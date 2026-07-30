Heads-up — related work that should sequence with this PR.

I have a local patch on `gmail send` that adds `--attach PATH` (repeatable) using `MIMEMultipart` + `MIMEBase` + `encoders.encode_base64`, with auto-detected MIME type via `mimetypes.guess_type` and `Content-Disposition: attachment; filename="..."`. Tested end-to-end against my account: sends the email with the attachment, message lands in the SENT label, and `gmail get` confirms delivery to the recipient.

The fix is small (~25 lines in `gmail_send`) but it conflicts with this PR in two places:

1. The duplicated MIME construction inside `gmail send` that this PR is refactoring into `_build_message_raw()`.
2. The `gmail send` parser block where I added `p.add_argument("--attach", action="append", default=[], ...)`.

## Suggested sequencing to avoid merge friction

1. Land this PR first (`_build_message_raw()` + drafts verbs). Drafts are a clearer safety story and unblock the helper.
2. Then a follow-up PR that adds an `attachments` kwarg to `_build_message_raw()` (default `[]`, preserves the `MIMEText` path when empty) and wires `--attach` into both `gmail send` and `gmail draft create`. Drafts especially benefit from attachments — staging a cover letter + CV for human review is the common job-application flow.

## The attachment branch (drop-in addition to `_build_message_raw`)

```python
if attachments:
    message = MIMEMultipart()
    message.attach(MIMEText(body, "html" if html else "plain"))
else:
    message = MIMEText(body, "html" if html else "plain")

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

## Existing related issues/PRs (cross-checked)

- #22872 — `productivity/google-workspace: CLI wrapper missing attachment download` (open) — covers the **download** path; this patch covers the **upload/send** path. Together they round-trip attachments end-to-end.
- #23465 — `feat(google-workspace): add gmail attachment list/get CLI verbs` (open) — download side; pairs with this for full attachment workflow.
- #32935 — this PR — drafts verbs + `_build_message_raw()` refactor; our patch should land after.

A standalone feature-request issue documenting the upload gap is filed separately — linking it from here once it has a number.

Happy to hold my follow-up PR until this lands, or open it now as a draft if you prefer to see the design in parallel.

— Felipe
