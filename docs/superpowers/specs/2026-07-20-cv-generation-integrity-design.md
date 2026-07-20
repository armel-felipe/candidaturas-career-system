# CV generation integrity

## Objective

Make the central job-specific CV pipeline fail closed when it cannot produce a complete, internally consistent CV. The change targets English CVs and applies the same structural guarantees to Portuguese CVs.

## Scope

The work is limited to `cv_content.json` validation, `generate_custom_cv.js`, the DOCX reviewer, and regression tests. Previously generated CV scripts and artifacts are out of scope.

## Required behavior

- The language is determined only by explicit, validated metadata. It is never inferred from whether a summary or an experience exists.
- An English CV has English visible labels, summary, role titles, bullets, education, technical stack, and languages. Portuguese connectors or section labels are rejected.
- The Chemical Engineering degree must render as `Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)` in English. `B.Sc.` is not an accepted replacement.
- Experiences are rendered in reverse chronological order based on their normalized dates, independent of persona or input order.
- Education, Technical Stack, and Languages must each contain visible, non-whitespace content. Missing or empty source fields fail before the DOCX is written.
- The reviewer independently checks the rendered DOCX for these conditions, including `Technical Stack` as an English section label.

## Design

The content validator becomes the source-of-truth gate: it validates language-specific field names, required non-empty lists/strings, education canonical wording, and parseable periods. It rejects an input whose experience order is not reverse chronological, rather than silently accepting an order that is later rendered incorrectly.

The renderer consumes only validated language metadata and language-specific values. It has defensive runtime assertions so direct invocation cannot create blank mandatory sections. It preserves the validated experience order rather than applying persona ordering.

The reviewer extracts DOCX text and applies language-aware checks. Its English lexical check must not prescribe Portuguese connector wording. It reports section content, chronology, and degree wording as blockers.

## Tests and acceptance criteria

Regression fixtures will cover one English and one Portuguese content payload. Tests will prove that each required defect fails before the implementation change and that a valid English payload renders a DOCX with the expected labels and degree wording. Negative cases cover: missing metadata language, Portuguese visible text in English fields, `B.Sc.`, ascending experience order, and blank education/stack/languages.

The full Python test suite, relevant Node regression tests, DOCX validation, and reviewer gate will be run after the implementation. The local generator modification is retained only if its behavior survives the regression tests; its current language heuristic is expected to be replaced.

## Delivery

After verification, commit the production changes and tests. Push to the configured GitHub remote and synchronize the configured RPi5 target using the repository's existing synchronization mechanism; if either remote is not configured or returns an error, report that exact blocker without claiming synchronization.
