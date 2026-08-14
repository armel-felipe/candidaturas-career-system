# Architecture implementation register

| Approved component | Implementation | Evidence | Status |
|---|---|---|---|
| Canonical source validation | `src/career/services/application_handoff.py` | `tests/test_application_handoff.py` source validation and fingerprint tests | Implemented |
| Compose-resolved target | `ApplicationHandoffService.resolve_target` | bot 01/02 resolution test; CLI choices | Implemented |
| Dry-run/apply boundary | `ApplicationHandoffService.handoff` | mutation-free dry-run test and real iFood dry-run | Implemented |
| Stale-target quarantine | `.handoff_quarantine/<timestamp>...` | stale fixture and old-fingerprint tests | Implemented |
| Shared SQLite registration | `applications`, `profile_application_bindings`, `application_runs`, `cell_nodes`, `cell_inputs`, `cell_requests`, `workflow_events` | cellular registration test | Implemented |
| Bounded fresh cell | one `analyze_fit` plan, manifest, and request | request limit and allowlist assertions | Implemented |
| Scope control | `scope-change-log.md` | explicit exclusion of downstream side effects | Implemented |
| Operational documentation | this register and `controlled-application-handoff.md` | reviewed alongside implementation | Implemented |

The register is updated when a component changes. A future change that modifies source files, allowed inputs, target selection, cell contract, or external side effects requires a new scope-log entry and a new dry-run test.
