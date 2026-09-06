# HARNESS-036 — Conversational Autonomy with Execution Safety

## Status

Approved design for implementation.

Roadmap item: `HARNESS-036`  
Plan: `2026-09-06-harness-conversational-autonomy`

## Goal

Allow the two Telegram agents to understand natural conversation and continue
the canonical work without requiring exact command phrases, while preserving
deterministic candidate identity, scoped state, and authorization boundaries for
external side effects.

## Problem

The current HarnessSupervisor combines too many decisions in a keyword-oriented
router. It can correctly preserve a session and identify the next canonical
step, but equivalent natural messages can fall into `generic_assistant`. The
opposite failure is also unsafe: relaxing routing globally could let a model
choose an application, file, or external action without sufficient evidence.

The desired behavior is freedom in interpretation and conversation, with strict
control at identity resolution and execution.

## Non-goals

- Do not let the model select or invent an internal `application_id`.
- Do not use global JSON mirrors, stale FIT_MAPs, filenames, or profile memory
  as execution authority.
- Do not share conversation memory, credentials, pending actions, or workspace
  writes between `vagas_bot_01` and `vagas_bot_02`.
- Do not remove approval requirements for Notion, Gmail, OneDrive, or
  destructive/overwriting operations.
- Do not replace the canonical SQLite resolver or scoped specialist contracts
  with a model-generated plan that executes directly.

## Design principles

1. The model interprets language; deterministic services resolve identity and
   decide what is executable.
2. A user request can authorize the work explicitly described, but identity is
   never authorization by itself.
3. A unique canonical match may proceed; ambiguity, stale state, and conflicting
   bot ownership must be surfaced instead of guessed through similarity.
4. Internal, scoped, and reversible work may be autonomous when intent is clear.
5. External side effects require a persisted authorization or approval record.
6. Every execution records what the system understood and which canonical
   application it resolved.

## Architecture

The conversation trunk becomes a five-stage flow:

```text
message + bounded session history
        |
        v
contextual planner (structured proposal, no tools)
        |
        v
canonical resolver (SQLite, session binding, fingerprints)
        |
        v
state inspector + authorization policy
        |
        v
scoped executor -> verified result -> conversation/audit record
```

### 1. Contextual planner

The planner receives the current message, the bounded history for the same
runtime/profile/session, the last canonical result, and the current menu or
pending-input context when present. It returns a validated proposal with only
user-visible clues:

```json
{
  "intent": "chat|inspect|intake|analyze|resume|generate_cv|generate_cover_letter|update_notion|deliver_onedrive|email_draft|process_package",
  "target_hints": {
    "notion_id": "625",
    "company": "Keeta",
    "role": "Sales Operations Manager",
    "url": null,
    "menu_index": null
  },
  "requested_steps": ["cv", "onedrive"],
  "authorization": "none|user_request|confirmation|pending_approval",
  "confidence": "high|medium|low"
}
```

`target_hints` are clues, not authority. The planner must not emit an internal
`application_id`, filesystem path, artifact path, approval ID, or tool command.
Malformed, extra, or low-confidence planner output falls back to a safe
clarification response; it must never be executed directly.

The existing deterministic classifier remains a fast path for unambiguous
commands. The planner is used for natural-language messages that do not match
that fast path, including contextual continuations such as “faz o próximo
passo”, “vai em frente” and “continua de onde paramos”.

### 2. Canonical resolver

The resolver receives the proposal and resolves identity in this order:

1. A valid application bound to the exact runtime/profile/session.
2. An explicit Notion ID, URL, or menu selection resolved against canonical
   SQLite data.
3. Company, role, and other hints matched against active canonical records.

The resolver returns one of:

- `resolved`: exactly one application, with canonical `application_id`, company,
  role, source, fingerprint, and current state.
- `ambiguous`: all safe candidates and a user-facing confirmation question.
- `unresolved`: the minimum clarification required.
- `stale_or_conflicting`: the identity exists but its fingerprint, stage,
  workspace ownership, or current state is not safe to continue.

Similarity may rank candidates for display, but it cannot select the execution
target. A numeric token is treated as a Notion ID only when the planner context
indicates a vacancy/application reference.

### 3. State inspector and policy

After resolution, the supervisor reads the canonical next step and evaluates
the proposed action against the following policy:

| Action class | Default behavior |
|---|---|
| Conversation, explanation, summary, status read | Execute freely |
| Intake, analysis, FIT_MAP finalization, scoped validation | Execute autonomously when target is unique and intent is clear |
| CV, cover letter, FERAS, skills, scoped derived artifacts | Execute when the user requested the artifact and the target is unique |
| Notion create/update, Gmail draft, OneDrive delivery | Require explicit authorization or persisted approval according to the existing action contract |
| Overwrite, destructive cleanup, cross-bot handoff, ambiguous or stale state | Block or ask for confirmation with the exact scope |

An affirmative such as “sim” is meaningful only when the immediately preceding
assistant turn in the same session presented an explicit executable proposal.
Otherwise it remains ordinary conversation.

### 4. Scoped executor and result

The executor receives only the resolver's canonical `application_id`, the
validated next step, and the allowed action class. It uses existing scoped
specialists, contracts, allowlists, approval records, and delivery receipts.
It must return a structured result with status, application scope, stage,
display text, and blocker details. No successful result may be emitted without
an auditable reply.

The conversation adapter records both sides of the turn. The assistant reply
must say, in plain language, what it understood, what it did, and what remains;
it must not expose internal commands as the only way to continue.

### 5. Audit record

Every planned operational turn records an event containing:

- session identity: runtime, profile, session ID, and turn ID;
- interpreted intent and target hints;
- resolver outcome and canonical `application_id`, when resolved;
- canonical fingerprint and next step observed;
- authorization class and decision;
- executed stage, result status, and blocker reason;
- whether the action was autonomous, confirmed, or approval-gated.

The audit record is diagnostic and cannot become a fallback authority for a
future application selection.

## Error handling

- Planner unavailable, malformed, or timed out: preserve the current session,
  return a concise clarification or deterministic status response, and do not
  execute a guessed action.
- Resolver finds multiple candidates: show the candidates using company, role,
  and Notion ID where available; never choose the closest string match.
- Resolver finds stale or conflicting state: identify the conflict and require
  a scoped resume/reconciliation action.
- Policy denies an action: return the reason and the exact confirmation or
  approval required; do not call a specialist.
- Worker returns no text: synthesize a safe structured response from the
  persisted result, preserving `blocked`/`awaiting_approval` instead of
  converting it into `completed`.
- `/new`: clear conversational/session intent for the new session while
  preserving canonical history and requiring a fresh resolution or an explicit
  resume request. No old pending action may attach to the new session.

## Implementation boundaries

The first implementation should add focused planner and policy boundaries to
the existing `HarnessSupervisor` rather than rewrite the specialist runners.
Expected touch points are:

- `src/career/services/harness_supervisor.py` for planner invocation, policy
  routing, resolution handoff, and audit payloads;
- a focused service module under `src/career/services/` for the structured
  planner contract/policy if the supervisor boundary becomes too large;
- `scripts/telegram_harness_adapter.py` and the dispatch worker only where
  context/result transport requires the new fields;
- `tests/test_harness_dispatch.py`, continuity tests, and worker tests;
- `docs/roadmap.md` and the implementation plan for evidence.

No profile configuration or shared-memory change is part of this item;
`RUNTIME-030` remains separate.

## Acceptance criteria

The item can move to `DONE` only when all of the following are demonstrated:

1. Natural paraphrases for chat, continuation, analysis, CV generation, and
   next-step execution reach the correct workflow without exact keywords.
2. The planner never supplies an executable internal application ID or path.
3. A unique canonical match proceeds; multiple matches and weak matches ask
   for clarification with options.
4. Internal scoped actions advance autonomously only when intent and state are
   clear.
5. Notion, Gmail, OneDrive, overwrites, and handoffs retain their approval or
   confirmation boundary.
6. “Sim”/“ok” is accepted as execution authorization only after an explicit
   offer in the same session; otherwise it remains a conversational reply.
7. `/new`, stale fingerprints, interrupted runs, and cross-bot sessions cannot
   mix identity or pending actions.
8. Both bot containers pass the same route-only and policy tests, with no
   unauthorized filesystem changes.
9. The audit record states “entendi X como candidatura Y” for every operational
   execution.

