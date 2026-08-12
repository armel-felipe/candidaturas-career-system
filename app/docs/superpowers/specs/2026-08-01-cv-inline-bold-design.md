# CV Inline Bold Rendering Design

## Goal

Render Markdown bold markers (`**text**`) as bold DOCX runs, without exposing the markers in the generated CV.

## Scope

The change is limited to `scripts/docx/generate_custom_cv.js`, the shared renderer for custom CVs, and its integration test suite. It applies to all plain-text inputs rendered by the script, including the summary and experience bullets.

## Design

Add one small renderer helper that splits a string on balanced `**...**` pairs. It will produce normal `TextRun` instances for surrounding text and bold `TextRun` instances for the enclosed text. Text without a complete pair, including unmatched `**`, remains literal so content is never silently discarded.

The existing `paragraph` and `bullet` paths will use this helper for string-backed content. Structured runs that already contain an explicit `bold` property retain their current behavior.

## Validation

Add an integration test that renders a fixture containing inline Markdown bold. It will read `word/document.xml` and assert that:

- the visible text no longer contains `**`;
- the marked phrase is present in a run with Word bold formatting;
- surrounding text remains present and unbolded.

The two affected files will then be regenerated from their preserved content artifacts and inspected to ensure no literal markers remain.

## Non-goals

- General Markdown support (italics, links, lists, headings).
- Changing CV wording, formatting, or the existing explicit structured-run API.
