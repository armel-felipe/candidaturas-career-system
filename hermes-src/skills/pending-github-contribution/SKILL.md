---
name: pending-github-contribution
description: >
  Reminder that Felipe has an in-flight contribution to NousResearch/hermes-agent. When he
  says "manda a mensagem 3", "documento 3", or "PR description", re-emit the contents of
  /home/ubuntu/projetos/candidaturas/.git-contrib/3-pr-description.md inline for him to
  paste into the GitHub PR form. Also: when he reports the issue number from pasting
  the body of 2-issue-feature-request.md, update the comment-on-32935 placeholder
  "linking it from here once it has a number" with the real URL.
---

# Pending GitHub contribution to NousResearch/hermes-agent

## Context (2026-07-27)

Felipe drafted an upstream contribution to add `--attach PATH` (repeatable) to
`gmail send` (and `gmail draft create` once #32935 lands) in the bundled
`productivity/google-workspace` skill.

Drafts are persisted locally in `/home/ubuntu/projetos/candidaturas/.git-contrib/`:

- `1-comment-on-32935.md` — comment to paste on PR #32935
- `2-issue-feature-request.md` — body of a new feature-request issue (already
  shown to Felipe inline as a single Markdown block; this is the canonical file)
- `3-pr-description.md` — PR description to use **after** PR #32935 is merged

There is **no GitHub auth** on this RPi (no `gh` CLI, no `GITHUB_TOKEN`,
no `~/.config/gh/`). Felipe pastes all three documents himself in the GitHub web UI.

## Triggers — what to do on each user message

### "manda a mensagem 3" / "documento 3" / "PR description" / "quando for hora de mergear"

The trigger condition is that PR #32935 has been merged upstream and Felipe is
ready to open the follow-up PR.

Action:
1. Read `/home/ubuntu/projetos/candidaturas/.git-contrib/3-pr-description.md`
   from disk.
2. Re-emit the **entire file content** inline in the response, wrapped in a
   single ```` ```markdown ```` fence so Felipe can copy/paste it into the PR
   description field on github.com.
3. Also remind him of the prerequisite: the PR must target a branch that
   already has #32935 merged (so `_build_message_raw()` exists). If he is on
   `main` directly that's fine; if on a fork branch, remind him to rebase.
4. Also remind him to update the comment on #32935 (replace the placeholder
   with the new PR URL once he opens it).

Do NOT try to post to GitHub on his behalf.

### Felipe reports "colei a issue, número é #XXXXX"

Action:
1. Read `/home/ubuntu/projetos/candidaturas/.git-contrib/1-comment-on-32935.md`.
2. Replace the line `A standalone feature-request issue documenting the upload
   gap is filed separately — linking it from here once it has a number.` with
   `Tracked in #XXXXX — see that issue for the full upload-side gap and the
   patch design that complements this PR.`
3. Save the updated file back to disk.
4. Re-emit the updated comment inline so Felipe can paste it on the PR.

## File paths

- Comment draft: `/home/ubuntu/projetos/candidaturas/.git-contrib/1-comment-on-32935.md`
- Issue body:    `/home/ubuntu/projetos/candidaturas/.git-contrib/2-issue-feature-request.md`
- PR body:       `/home/ubuntu/projetos/candidaturas/.git-contrib/3-pr-description.md`

## Related upstream issues/PRs

- PR #32935 (open): `feat(skills): add gmail draft create/list/send commands`
  — refactors `gmail send` into shared `_build_message_raw()`. Our follow-up
  must land **after** this PR.
- Issue #22872 (open): attachment **download** side (download).
- PR #23465 (open): `gmail attachment list/get` verbs (download complement).

## Constraint reminders

- No GitHub auth on this RPi → never attempt POST to api.github.com.
- Patches are local-only and shipped via Felipe's browser.
- The 4 copies of the patched `google-workspace` skill
  (`~/.hermes/skills`, `~/.hermes/profiles/{vagas_bot_01,vagas_bot_02}/skills`,
  `~/.hermes/hermes-agent/skills`) remain patched locally regardless of upstream
  status; `hermes skills update` would overwrite — Felipe must reapply via
  the recipe in the `hermes-google-workspace-attachments` skill if that happens.