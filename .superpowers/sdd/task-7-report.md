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
