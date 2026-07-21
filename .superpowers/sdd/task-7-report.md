## Task 7 — Scoped CV cells

Implemented application- and run-scoped `compose_cv`, `render_cv`, and `review_cv` handlers. CV content now carries the candidate-facts revision plus `experience_id`/`evidence_id` references; rendering receives explicit content, output, and application paths; review registers and evaluates the exact published DOCX with an application-local registry and records an approved-artifact manifest under the run review directory.

The integration test executes separate PT-BR and English branches and proves different FIT_MAP revisions, generated DOCX paths and hashes, language-specific content, provenance references, and review paths. No delivery cell is run.

Validation executed:

- `pytest tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -q` — 7 passed
- `pytest -q` — 174 passed
