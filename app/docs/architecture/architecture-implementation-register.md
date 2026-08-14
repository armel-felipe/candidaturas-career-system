# Architecture implementation register

| Approved component | Implementation | Evidence | Commit | Status |
|---|---|---|---|---|
| Canonical source validation | `src/career/services/application_handoff.py` | `tests/test_application_handoff.py` source validation and fingerprint tests | `33aaadd` | Implemented |
| Compose-resolved target | `ApplicationHandoffService.resolve_target` | bot 01/02 resolution test; CLI choices | `33aaadd` | Implemented |
| Dry-run/apply boundary | `ApplicationHandoffService.handoff` | mutation-free dry-run test and real iFood dry-run | `33aaadd` | Implemented |
| Stale-target quarantine | `.handoff_quarantine/<timestamp>...` | stale fixture and old-fingerprint tests | `33aaadd` | Implemented |
| Shared SQLite registration | `applications`, `profile_application_bindings`, `application_runs`, `cell_nodes`, `cell_inputs`, `cell_requests`, `workflow_events` | cellular registration test | `33aaadd` | Implemented |
| Bounded fresh cell | one `analyze_fit` plan, manifest, and request | request limit and allowlist assertions | `33aaadd` | Implemented |
| Compact CV skill input | synchronized `.agents/skills/cv-generator/SKILL.md` and `app/.agents/skills/cv-generator/SKILL.md` under 50 KB | `tests/test_skill_context_budget.py`; bot 02 request validation | `e799ab0` | Implemented |
| Scope control | `scope-change-log.md` | explicit exclusion of downstream side effects | `33aaadd` | Implemented |
| Operational documentation | this register and `controlled-application-handoff.md` | reviewed alongside implementation | `33aaadd` | Implemented |

The register is updated when a component changes. A future change that modifies source files, allowed inputs, target selection, cell contract, or external side effects requires a new scope-log entry and a new dry-run test.
