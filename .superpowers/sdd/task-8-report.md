# Task 8 — Cellular output and receipt branches

## Result

Implemented the Recovery Slice D production branches for FERAS, cover letter,
habilidades, Notion initial/final synchronization, and CV delivery.

## TDD evidence

1. Added `tests/test_cell_notion_delivery.py` and
   `tests/test_cell_deliverable_branches.py` before production changes.
2. RED command:

   ```text
   pytest tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py -q
   7 failed, 1 passed
   ```

   The expected failures were missing injectable Notion/delivery clients and
   absent remaining production branch handlers.
3. GREEN commands:

   ```text
   pytest tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py -q
   8 passed

   pytest -q
   187 passed
   ```

## Delivered behavior

- `production_handler_registry` now accepts injected `notion_client` and
  `delivery_client`; no default cellular handler performs a real remote write.
- Notion and delivery requests use deterministic hashes from application/node
  identity, target/operation, and input artifact hashes.
- Validated receipts are immutable, bounded JSON files at
  `cells/<node>/receipts/<run>/<request-hash>.json`; matching retries reuse
  them before a second external mutation or delivery.
- The executor exposes only those receipt cache paths to the three declared
  external-effect nodes. Their resource locks remain the declarative contract
  locks (`notion-write` and `delivery:onedrive-cv`).
- Receipts contain operation, target, request/response hashes, application/run/
  node identity, and Notion page/record or delivery artifact identity.
- FERAS, cover letter, and habilidades now have explicit FIT_MAP-scoped
  generate/review handlers and compact application/run handovers; they remain
  independent from the CV branch.
- FIT_MAP and approved-CV pointers reject a declared foreign application.
- The text-only Notion extra-artifact reader now rejects DOCX and other binary
  extensions.

## Safety

Tests use injected fakes only. No Notion API or rclone/OneDrive write was
performed. `.inbox/` was not touched.

## Review remediation

Follow-up review findings were remediated with a second RED/GREEN cycle.

- `deliver_cv` now directly requires both `render_cv` and `review_cv`; its
  approval manifest must bind the exact rendered DOCX path and SHA-256 before
  the adapter can be called. An executor-level test executes that complete
  dependency chain with a fake delivery client.
- Default production wiring now creates lazy `NotionCellAdapter` and
  `CanonicalDeliveryCellAdapter` instances. They perform no configuration read
  or external operation during construction and fail with explicit preflight
  errors only when the external node runs without configuration.
- Each non-CV output branch requires both normalized job packs and FIT_MAP,
  publishes its text plus branch handover/evidence artifacts, and reviews with
  the applicable FERAS, cover-letter, or habilidades validation policy.
- Input records now retain application/run/node and immutable artifact-manifest
  pointers. Handlers validate those pointers before reading artifacts.
- Notion request hashing includes target status; initial and final receipt
  idempotence are both covered. Receipt write scope is exactly
  `receipts/<run_id>`.

Final verification after remediation:

```text
pytest tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py tests/test_cell_executor.py tests/test_cell_planner.py -q
48 passed

pytest -q
194 passed
```
