### Task 3.3 final menu-scope fix

Read first: this brief is the exact correction contract.

Problem: scoped supervisor responses still expose global `active_intake` and root `workflow_state.json` metadata, allowing a Conexa result to be accompanied by Instaleap context and no application_id.

Required behavior:
- A scoped final menu/response must include the resolved `application_id` and only data derived from that application’s SQLite/materialized snapshot.
- Remove global `active_intake`/root workflow_state fields from the response, or reconstruct equivalent metadata from the resolved application; never read global pointers for execution or presentation.
- Add a real regression with contaminated root `workflow_state.json`/active pointer for another company and assert it cannot appear in a scoped response.
- Preserve the root FIT_MAP contamination fix and all specialist contract/gate/artifact tests.

Use TDD red first. Modify task-owned supervisor/tests/report only; preserve unrelated dirty files. Run focused plus neighboring suites, commit and report exact evidence. Do not start Phase 4.
