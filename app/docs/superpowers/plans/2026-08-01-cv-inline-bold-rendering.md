# CV Inline Bold Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert balanced Markdown bold markers in custom-CV text into real bold DOCX runs.

**Architecture:** Keep Markdown interpretation at the final rendering boundary. A small helper in the existing Node DOCX renderer maps text segments to `TextRun`s; existing structured bold runs are unchanged. The integration test reads the emitted DOCX XML so it validates the consumer-visible file rather than implementation details.

**Tech Stack:** Node.js, `docx`, Python `pytest`, OOXML.

## Global Constraints

- Parse only balanced `**text**` pairs; unmatched markers remain literal.
- Do not alter CV content or regenerate the user-edited OneDrive documents.
- Preserve the renderer's structured `{ text, bold }` and `{ prefixo, enfoque, sufixo }` input behavior.

---

### Task 1: Cover inline bold DOCX rendering

**Files:**
- Modify: `tests/test_custom_cv_generation.py`
- Modify: `scripts/docx/generate_custom_cv.js`

**Interfaces:**
- Consumes: string-backed summary and experience bullet fields from `cv_content.json`.
- Produces: DOCX text runs where `**gestão de equipes**` becomes a bold run containing `gestão de equipes`.

- [x] **Step 1: Write the failing integration test**

```python
def test_renderer_converts_markdown_bold_to_bold_docx_run(tmp_path):
    payload = portuguese_payload()
    payload["resumo"] = "Liderei **gestão de equipes** com resultados."
    document = render_cv_document(payload, tmp_path)
    runs = document.findall(".//w:r", NS)
    assert "**" not in "".join(node.text or "" for node in document.findall(".//w:t", NS))
    assert any(
        run.find("w:rPr/w:b", NS) is not None
        and "gestão de equipes" in "".join(node.text or "" for node in run.findall(".//w:t", NS))
        for run in runs
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_custom_cv_generation.py::test_renderer_converts_markdown_bold_to_bold_docx_run -v`

Expected: FAIL because the document retains the markers and does not create a bold run.

- [x] **Step 3: Write the minimal renderer implementation**

Add `markdownRuns(text, options)` to split balanced `**...**` segments into normal and bold `TextRun` values. Use it for string-backed paragraphs and bullets; keep explicit structured runs unchanged.

- [x] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/test_custom_cv_generation.py::test_renderer_converts_markdown_bold_to_bold_docx_run -v`

Expected: PASS.

- [x] **Step 5: Run the renderer regression suite**

Run: `pytest tests/test_custom_cv_generation.py -v`

Expected: PASS with no failures.

- [x] **Step 6: Commit the implementation**

Stage only the renderer, test, and this plan; commit message: `fix: render inline markdown bold in CV DOCX`.
