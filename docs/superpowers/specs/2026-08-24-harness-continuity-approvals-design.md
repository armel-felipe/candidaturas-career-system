# Harness Continuity and Approval Boundaries

## Goal

Make the career harness continue an explicit multi-step application request
without asking the user to re-confirm ordinary pipeline steps, while keeping
workspace-authority changes behind one structured approval.

## Scope

This change covers the canonical Python runtime used by the harness and the
roadmap evidence for the current bot observations. It does not change the
meaning of FIT_MAP gates, CV review gates, Notion payload contents, or the
physical storage safety rules.

## Design

The `HarnessSupervisor` remains the deterministic conductor. A session-bound
`application_id` is the only execution selector; global JSON pointers remain
discovery metadata. When an intake binds a session, the supervisor persists a
compact pipeline intent containing the requested deliverables. Follow-up
messages such as “sim, gere o CV e envie” resolve that same session intent and
continue with the scoped specialist instead of creating an unscoped CV request.

Specialist agents decide analysis and document content. They return structured
success, blocked, or approval-required results; they do not negotiate normal
pipeline steps with the user.

Ordinary explicit requests authorize the requested Notion write, CV
generation, and OneDrive delivery according to the existing delivery profile.
Only an authority mutation, an unresolved application ambiguity, or an
unrequested external side effect reaches the user. A storage handoff becomes a
single idempotent approval record keyed by control database, physical storage
identity, and owner. Approval execution calls the official handoff command and
records a resumable continuation state.

## Related roadmap work

- `HARNESS-001`: preserve scoped application context and compound intent across
  conversation turns.
- `HARNESS-002`: centralize approval boundaries and resume after approved
  authority handoff.
- `RUNTIME-006`: add a regression boundary for session continuation in addition
  to the existing intake-envelope propagation coverage.
- `TEST-003`: make the pre-ledger fixture migrate before provisioning and add
  handoff schema coverage.
- `RUNTIME-OBS-001`: close the current observation window with an explicit
  preservation decision for compatibility JSON and evidence from both bots.

## Safety invariants

1. No global pointer selects an execution.
2. No agent bypasses authority, provenance, or delivery gates.
3. A duplicate user reply cannot create duplicate approval or handoff records.
4. An approved handoff resumes the same application and does not restart intake.
5. Existing pending approvals are not deleted by this change.

## Verification

The regression suite must prove session continuation, intent persistence,
approval idempotency, pre-ledger schema migration, and preservation of the
authority fail-closed behavior. Existing unrelated `TEST-004` remains outside
this change and must be reported separately if the focused suite includes it.
