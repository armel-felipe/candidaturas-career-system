# Notion Application Filters Design

## Goal

Allow natural-language requests to list records in the Notion `Aplicações` database using at least one filter, especially `Etapa Funil`. The returned short table must let Felipe select a Notion record ID and immediately start the existing job-analysis pipeline.

## Scope

- Read the Notion database live for every list request.
- Support one or more filters joined by `e` (AND).
- Resolve property names and valid values from the live Notion schema.
- Support compatible operations for `status`, `select`, `checkbox`, `date`, text, and number properties.
- Return `ID`, role, company, `Etapa Funil`, fit score, and Notion link in a table of at most 20 rows.
- Accept a returned record ID as the next conversational input and route it to the existing `agent:evaluate-notion -- <ID>` flow.

## Non-Goals

- No writes to Notion.
- No changes to FIT_MAP, CV, or other downstream analysis stages.
- No cache-based filtering or reuse of stale local application data.
- No unrestricted query language or unvalidated property names.

## Interaction Contract

Examples of supported requests:

- `traga vagas com Etapa Funil Fila Agente`
- `liste registros com Etapa Funil Aplicação andamento e empresa Mercado Livre`
- `traga vagas com aderência maior que 7`

All supplied filters use AND semantics. A request must contain at least one filter. A generic request such as `traga vagas` must not dump the database; it returns the supported filter fields and the currently valid values for `Etapa Funil`.

The query response is a short Markdown table with columns `ID`, `Cargo`, `Empresa`, `Etapa Funil`, `Aderência`, and `Link`. It states the applied filters and total returned count. A zero-row result is valid and states the filters used.

After a list response, the user can reply with `123` or `Notion 123`. The harness treats this as the unique Notion `ID` and invokes the existing analysis route, preserving its intake, FIT_MAP, and validation behavior.

## Architecture

### Notion Query Service

`src/career/services/notion.py` owns the read-only query service. It discovers the active database schema, maps conversational aliases to actual Notion property names, validates values and operators against the declared property type, builds an official Notion filter payload, and projects results into the short-table record shape.

The service queries the Notion database directly. It does not use `notion_cache`, the SQLite query engine, or a local snapshot.

### CLI Compatibility

`scripts/notion_sync.py` receives a dedicated read-only filtered-list subcommand. Existing `notion:list` behavior remains available unchanged. The new command is the canonical implementation bridge for CLI and harness use.

### Conversational Routing

The classifier and harness recognize list/filter requests before generic Notion handling. The harness parses the supported conversational filter forms, invokes the query service, and records the displayed record IDs as pending list-selection context. Numeric replies resolve only against that context, then route to the existing `notion_job_analysis` workflow.

## Filter Semantics

The initial parser recognizes canonical names and configured aliases, including `Etapa Funil`, `empresa`, `cargo`, and `aderência`. It supports exact equality by default and typed comparison phrases where meaningful, such as `maior que` for numbers and dates.

For `status` and `select`, a requested value must be present in the schema options after case- and accent-insensitive matching. For checkboxes, accepted values are `sim` and `não`. For text, matching uses the supported Notion text operator. For dates and numbers, the parser emits only the corresponding typed filters.

Unknown fields, unsupported operators, ambiguous aliases, and invalid values are rejected before the Notion query. The response identifies the problem and lists valid options when the schema exposes them. The system never guesses an option value.

## Error Handling

- A Notion schema or query failure returns a concise blocked result without falling back to local cache.
- Empty results return a completed result with zero rows and the applied filters.
- A numeric reply that is not in the pending list context returns a selection error and preserves the last list context.
- A selected ID continues through the existing `agent:evaluate-notion` path; any missing or insufficient job description remains governed by that pipeline.

## Tests

Unit tests will cover:

- Alias normalization and schema-property resolution.
- Validation of property type, value, and operator.
- Construction of native Notion AND filter payloads.
- Formatting of the 20-row short table and empty results.
- Harness routing of list requests and numeric selections to the existing Notion analysis workflow.

Tests use mocked Notion schema and query responses. They require no credentials and make no live Notion requests.
