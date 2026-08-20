### Task 3.3 — Supervisor fail-closed

Read first: this brief is the exact requirements contract for Task 3.3.

Files:
- Modify `src/career/services/harness_supervisor.py`.
- Modify `src/career/services/multiagent.py` only where contract/result wiring requires it.
- Create `tests/test_supervisor_contracts.py`.

Interfaces:
- `SpecialistContract.required_artifacts: tuple[str, ...]`.
- `SpecialistContract.required_gates: tuple[str, ...]`.
- `HarnessSupervisor.execute_specialist(application_id: str, contract: SpecialistContract, ...) -> SpecialistResult`.

Required behavior:
1. Specialist execution requires an application_id that resolves in canonical SQLite; global pointers and JSON names cannot select scope.
2. Success requires every required artifact to be registered for the same application_id, current source revision/positioning revision, valid path/content hash and required review/gate receipt. “Any allowed output changed” is never sufficient.
3. A DOCX without review/approval returns a blocked SpecialistResult and records a blocker workflow event.
4. FERAS/carta/habilidades from another application cannot satisfy the current contract, even if filename/kind matches.
5. Contract failure is auditable: application_id, run_id, missing artifact/gate, validator and reason are persisted in workflow_events/receipts; no partial success is returned.
6. Explicit scoped success remains compatible with the current supervisor pipeline and does not alter core_package_sealed/base package stage.

TDD and evidence:
- Add tracked tests first and run them red before implementation.
- Cover missing review, cross-application artifact, stale/mutated artifact, missing gate, valid success and unscoped rejection.
- Run focused supervisor tests plus materializer, gates, artifact provenance, projection and intake suites.
- Do not implement Phase 4 post-processing service or Phase 5 migration.
- Preserve unrelated dirty files and the untracked legacy intake test.
