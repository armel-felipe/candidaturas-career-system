## Task 7 — Scoped CV cells

Implemented application- and run-scoped `compose_cv`, `render_cv`, and `review_cv` handlers. CV content now carries the candidate-facts revision plus `experience_id`/`evidence_id` references; rendering receives explicit content, output, and application paths; review registers and evaluates the exact published DOCX with an application-local registry and records an approved-artifact manifest under the run review directory.

The integration test executes separate PT-BR and English branches and proves different FIT_MAP revisions, generated DOCX paths and hashes, language-specific content, provenance references, and review paths. No delivery cell is run.

Validation executed:

- `pytest tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -q` — 7 passed
- `pytest -q` — 174 passed

### Review remediation

Closed the follow-up review findings: English DOCX periods are rendered in English;
header identity comes solely from immutable `cv_content`; evidence IDs are opaque,
revision-bound, and resolve through locators in hashed canonical candidate sources;
and the CV language must come from normalized FIT_MAP/intake data rather than marker
heuristics. The renderer now fails if Arial theme injection fails, and the DOCX
validator verifies the actual theme font.

`review_cv` publishes the report, polishing result, approval manifest, and keyword
registry as run-scoped immutable artifacts. The approval manifest binds the exact
DOCX, FIT_MAP, and serialized report hashes. The normal review gate remains limited
to `outputs/`, with the sole exception of a hash-validated cellular `artifacts/cv.docx`
manifest. Cell execution no longer writes application-level `cv_content.json` or a
shared keyword registry.

The PT-BR and English regression branches now execute through separate SQLite
connections in a `ThreadPoolExecutor`; the test inspects DOCX XML, paths, hashes,
run-scoped review evidence, and the absence of shared CV state.

Validation executed after remediation:

- `pytest tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -q --maxfail=1` — 8 passed
- `pytest -q` — 175 passed
- `git diff --check` — passed

### Third review remediation

`validate_canonical_provenance` now recomputes the candidate-facts revision from
the canonical source set, pins the permitted source paths and bytes, and verifies
each evidence record's locator, source excerpt/source value and their hashes.
The evidence catalog is audit data only: the validator independently rebuilds the
renderer-consumed PT-BR and English values through the trusted transformations and
rejects forged values even when the payload's evidence IDs and hashes are rebuilt.

Cellular review acceptance now validates the full render chain: revision layout,
artifact manifest, matching render attempt output, and a parsed passing DOCX
validator report that is bound to application, run, node, attempt, path and hash.
Regression coverage includes a structurally complete forged manifest/report and
PT renderer aliases (`experiencias`, `formacao`, `idiomas`, `resumo`). The renderer
also no longer contains candidate-location defaults.

Validation executed after third remediation:

- `pytest tests/test_custom_cv_generation.py tests/test_cell_cv_pipeline.py tests/test_review_output_cellular_artifact.py -q --maxfail=1` — 11 passed
- `pytest -q` — 178 passed
- `git diff --check` — passed

### Second review remediation

Canonical CV provenance now binds each rendered claim to a revision-pinned source
with an opaque evidence ID, claim kind, exact source locator and SHA-256 of the
rendered value. Validation rejects changes to role, period, bullet, education,
language, stack and every contact field, while also checking canonical source
bytes and the candidate-facts revision.

The review cell publishes `cv_review.json` and `approved_cv_manifest.json` as
the same immutable CellOutput set. The validator consumes those output bytes
directly; mutable application-level review and approval files are no longer
used. Cellular review acceptance now requires a full render-CV artifact manifest
identity, revision/path/hash self-consistency and a persisted passing DOCX
validator record.

The dual-application regression uses a render barrier to prove overlap and
checks both rendered DOCX documents for isolated role, period, education,
language and stack content. Renderer output filenames are required explicitly;
there is no candidate-specific fallback filename.

Validation executed after second remediation:

- `pytest tests/test_custom_cv_generation.py tests/test_cell_cv_pipeline.py tests/test_review_output_cellular_artifact.py -q --maxfail=1` — 10 passed
- `pytest -q` — 177 passed
- `python3 scripts/docx/validate_docx.py <published cellular CV>` — passed
- `git diff --check` — passed
