# Cellular Recovery Hardening — Design Specification

**Date:** 2026-09-01
**Roadmap:** `CELLULAR-016`, `CELLULAR-017`, `HARNESS-015`, `RUNTIME-021`

## Problem

The autonomous-maintenance deployment is healthy, but two production cellular
runs exposed a second-order reliability gap:

- `run_9a62f3c91c5b467c8f63b08efacf1b7f` for Rappi remains active at
  `analyze_fit`, with previous attempts failing with
  `draft_binding_invalid:attempt_mismatch,manifest_path_mismatch`. The bot
  consumed 150 model iterations while inspecting missing/stale artifacts.
- `run_d2ff78cd9c5644a4bf98476d223ec12b` for Empresa Confidencial is blocked at
  `review_cv` after three attempts. The same `cv_content`/review blockers were
  repeated: `liderança de equipes multidisciplinares` and `NPS` remained
  `missing_unexplained`.
- The Hermes `pre_llm_call` hook executes the supervisor synchronously. A live
  turn exceeded its 300-second hook timeout. One session also reached roughly
  651,533 tokens, and the background skill reviewer attempted writes to
  externally owned skills during ordinary work.

The system therefore needs bounded recovery semantics, not a larger retry
limit or a second blind deployment.

## Goals

1. Reuse one active serial run per application and never create a duplicate
   plan during a continuation race.
2. Reconcile stale `analyze_fit` bindings into a fresh, explicitly scoped
   attempt without consuming an attempt before the external agent is ready.
3. Detect unchanged CV repair candidates and stop with an actionable blocker
   instead of repeating the same review indefinitely.
4. Keep the pre-LLM supervisor hook bounded and supervised by dispatching long
   work to a durable worker rather than waiting for the entire pipeline.
5. Bound Telegram session context and make automatic skill review opt-in for
   production profiles.
6. Preserve canonical provenance, application/run identity, allowlists and
   all existing delivery gates.

## Non-goals

- Injecting provenance, keywords or metrics into a FIT_MAP/CV by hand.
- Editing SQLite, sealed artifacts, DOCX files or Notion records to bypass a
  gate.
- Increasing model temperature or retry budgets as a substitute for recovery.
- Creating new skills or allowing Hermes to modify canonical skills directly.
- Changing the external Notion, OneDrive or Gmail approval contracts.

## Required behavior

### Active-run arbitration

For a scoped `application_id`, the supervisor must query the newest serial run
under the canonical control database. If the run is `planned`, `running`,
`awaiting_agent`, `awaiting_approval` or `blocked`, the continuation must return
that same `run_id` and state. It may not call `applications:plan` again.

If a plan creation command races with another process, the supervisor must
re-query the database after the command fails and adopt the newly persisted
serial run when its identity and graph are valid. Otherwise it returns a
structured `serial_plan_creation_failed` containing captured stdout and
stderr.

### Fresh binding recovery

An `analyze_fit` binding is valid only when its application, run, node, attempt,
job fingerprint, draft hash and manifest path all match the reserved attempt.
When the binding is stale, the old draft/binding is quarantined, the attempt
is returned to `planned` or `cancelled`, and a new request is generated with a
new expected manifest path. A run cannot remain `reserved` without an active
worker lease.

### No-progress CV repair

Each review attempt records a deterministic fingerprint of the blocker IDs,
missing top-8 keywords and the rendered `cv_content` hash. Before another repair
is dispatched:

- a changed candidate is accepted only after metadata/provenance validation;
- an unchanged candidate with the same blocker fingerprint becomes
  `cv_repair_no_progress` and stops the loop;
- a candidate that changes but produces the same blocker fingerprint may be
  retried only within the configured bound, then stops with the exact missing
  keywords and the canonical source that must be corrected.

No attempt may mark the run complete while `approved_for_delivery` is false.

### Bounded hook dispatch

The pre-LLM hook must finish classification and dispatch within a bounded local
budget (target: 5 seconds). It must persist a request envelope containing
`message_id`, `session_id`, `turn_id`, decision, application/run scope and
status. A single worker may own a request at a time; duplicate hook invocations
return the existing `awaiting_agent`/`running` result.

The worker executes with `CAREER_HARNESS_SUBAGENT=1`, writes the final result to
the request envelope and never re-enters the pre-LLM hook. A hook timeout remains
a structured `blocked` result; it can never release Hermes into an
unconstrained workflow.

### Session and curator bounds

Before building the model request, a session whose serialized history exceeds
the configured maximum is compacted to the current task plus the most recent
bounded turns. The compaction emits a structured event and does not include
the entire historical transcript in the next prompt.

Automatic skill-library review is disabled unless a production profile
explicitly opts in. Ordinary career tasks must not call `skill_manage`; any
requested canonical skill change goes through the maintenance supervisor.

## Acceptance evidence

- A deterministic test proves two concurrent continuations produce one serial
  run and preserve its `run_id`.
- A deterministic test proves stale binding recovery creates a fresh request,
  resets the state and never executes the previous draft.
- A deterministic test proves identical CV repair candidates stop with
  `cv_repair_no_progress` and do not consume the remaining repair budget.
- A hook test proves a slow workflow returns `awaiting_agent` within the local
  budget and the worker later persists the result without recursion.
- Hermes tests prove session compaction and opt-in skill review.
- Full project tests, `npm run validate:structure`, `npm run runtime:verify --
  --strict`, `git diff --check` and one disposable canary for each bot pass.
- The two live incident runs are recovered only through their canonical
  `application_id`/`run_id`; no manual JSON/SQLite/Notion workaround is used.
