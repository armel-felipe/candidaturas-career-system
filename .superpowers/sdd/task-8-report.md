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
