# ATS Keyword Registry

Purpose: keep a persistent memory of extracted ATS keywords, CV coverage, missing terms and LinkedIn wording candidates across applications.

This registry improves future CVs and LinkedIn profiles by recording which market terms are:

- extracted from each job description;
- defensible from Felipe's evidence base;
- covered as exact strings in the generated CV;
- covered by similar wording when the exact market term was intentionally replaced;
- left missing because they are not defensible or were intentionally excluded;
- reusable as canonical wording for future CV bullets and LinkedIn bullets.

## Files

- `.career-state/derived/keyword_ats_registry.json`: machine-readable registry.
- `scripts/register_keywords.py`: updates the registry from `.career-state/fit_map.json` and, when provided, a generated DOCX.

## When To Update

Run the registry update after every `career-fit-analysis`.

Run it again after every generated CV, passing the DOCX path, so the system can mark exact keyword coverage in the final file.

Recommended command:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv outputs/<generated_cv>.docx
```

If there is no CV yet:

```bash
python scripts/register_keywords.py --fit-map .career-state/fit_map.json
```

## Status Rules

- `covered_cv`: keyword appears as an exact string in the generated CV.
- `covered_similar_cv`: keyword does not appear exactly, but the registry found a similar term in the CV that likely served as the substitute.
- `missing_cv`: keyword was extracted but does not appear in the generated CV.
- `gap`: keyword has no defensible evidence in the FIT_MAP or was marked as gap.
- `covered_by_linkedin`: keyword is appropriate for LinkedIn profile bullets.
- `canonical`: preferred market-facing wording for future CV/LinkedIn use.

When `covered_similar_cv` is used, the record should also preserve:

- `substituted_by_keyword`: which exact CV keyword likely replaced the extracted term;
- `shared_tokens_with_substitute`: token overlap that supported the match;
- `coverage_note`: short explanation of the substitution.

## LinkedIn Rule

LinkedIn should mirror the CV model, using 4 to 8 bullet points. Select the highest-signal covered keywords from the latest relevant FIT_MAP, then write bullets using the same validated facts and numbers.

Preferred LinkedIn bullet shape:

```text
<Keyword / capability>: <scope/context> + <validated result>.
```

Example:

```text
Supply Chain Management and S&OP: led planning across 40K SKUs at Trifil, reducing purchasing costs by 27% and stockouts by 40%.
```

## Do Not Do

- Do not add a keyword to CV or LinkedIn just because it is frequent in the market.
- Do not mark a keyword as covered if it only appears as a loose synonym.
- Do not mark a keyword as `covered_similar_cv` without preserving which wording replaced it.
- Do not use gaps such as specific tools unless Felipe has defensible evidence.
- Do not let LinkedIn become broader than the CV facts. LinkedIn can be more evergreen, but not less factual.
