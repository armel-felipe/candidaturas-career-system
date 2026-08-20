### Task 3.3 final summary-scope fix

Read first: this brief is the exact correction contract.

Problem: a scoped supervisor execution can finish with a response decoration that calls `fit_map.payload_summary()` without `application_id` or application-local FIT_MAP path. That reads root JSON and can show another vacancy's company, score or gaps.

Required behavior:
- Every supervisor final response/menu/summary for a scoped execution must use the same resolved application_id and application-local materialized/SQLite snapshot. No call may default to root `.career-state/fit_map.json`.
- If no application scope exists, return a blocked result; do not decorate with global summary.
- Add a real regression that plants contaminated root FIT_MAP JSON, executes/builds a scoped response for another application, and asserts contaminated company/score/gaps never appear.
- Preserve the fail-closed SpecialistContract gates/artifact provenance and legacy adapter tests.

Use TDD red first. Modify task-owned supervisor/tests/report only, preserve unrelated dirty changes. Run focused plus neighboring suites, commit and report exact evidence. Do not start Phase 4.
