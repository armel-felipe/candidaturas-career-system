### Task 3.2 — SQLite context materializers

Read first: this brief is the exact requirements contract for Task 3.2.

Files:
- Create `src/career/services/context_materializer.py`.
- Modify `src/career/services/derived_context.py` and `src/career/services/multiagent.py`.
- Create `tests/test_context_materialization.py`.

Interfaces:
- `ContextMaterializer.build(application_id: str, kind: str, revision_id: str | None = None) -> Mapping[str, Any]`.
- `ContextMaterializer.export_json(application_id: str, kind: str, destination: Path) -> ExportReceipt`.

Required behavior:
1. Build `fit_map_seed`, `cv_input`, `feras_input`, and `habilidades_input` from canonical SQLite application/revision/reference data, not by reading derived JSON.
2. Every payload includes application_id, source revision identifiers, canonical payload hash, and generated_at metadata.
3. `export_json` is a one-way materialization: destination must be application-scoped or an explicitly supplied temporary path; export is never read back as authority. Return receipt with path, hash, application_id, revision_id, kind and expiration/created metadata.
4. Two applications with same artifact filename/kind cannot share context; mismatched/unknown application or revision fails closed.
5. Update derived_context/multiagent consumers to request materialized in-memory context by explicit application_id; compatibility JSON remains output-only and cannot select a vacancy.

TDD and evidence:
- Add tracked tests first and run them red before implementation.
- Test all four kinds, revision pinning, content/hash metadata, export one-way semantics, unknown/mismatched scope, and cross-application isolation.
- Run focused materializer tests plus neighboring 3.1, persistence, analysis, gate and projection tests.
- Do not implement supervisor contracts (Task 3.3), migration (Phase 5), or runtime cutover (Phase 8).
- Preserve unrelated dirty files and the untracked legacy intake test.
