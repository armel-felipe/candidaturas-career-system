# Notion Application Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the harness list live Notion Aplicações records through validated natural-language filters and route a selected record ID into the existing analysis pipeline.

**Architecture:** Add a read-only query layer to `career.services.notion` that resolves the live schema, parses typed filter requests, builds a native Notion `and` filter, and projects pages into a compact table shape. Expose it through `notion_sync.py` and route conversational list requests in `HarnessSupervisor`, storing a temporary list-selection context in the existing pending-input file.

**Tech Stack:** Python 3, argparse, existing Notion HTTP helpers in `scripts/notion_sync.py`, pytest, Markdown output.

## Global Constraints

- Query the Notion database live for every filtered-list request; do not use SQLite, `notion_cache`, or a local snapshot as fallback.
- Require at least one filter and combine all provided filters with AND semantics.
- Discover properties and option values from the active Notion schema; never invent a field or option value.
- Support only filter operators valid for the resolved Notion property type.
- Keep `notion:list` compatible and make the new list operation read-only.
- Render no more than 20 rows with `ID`, `Cargo`, `Empresa`, `Etapa Funil`, `Aderência`, and `Link`.
- A selected record must use the existing `notion_job_analysis` / `agent:evaluate-notion` flow unchanged.
- Do not modify or stage the pre-existing untracked workflow files.

---

## File Structure

- Modify `src/career/services/notion.py`: own schema normalization, typed query validation, native Notion payload construction, page projection, and short-table rendering.
- Modify `scripts/notion_sync.py`: add a read-only `list-filtered` subcommand that delegates to the service layer rather than duplicating filter logic.
- Modify `package.json`: expose the filtered-list command as `notion:list-filtered` without changing `notion:list`.
- Modify `src/career/services/harness_supervisor.py`: classify conversational requests, execute the query, persist selectable IDs, and resolve an ID reply to the existing analysis workflow.
- Modify `tests/test_query_engine.py`: add isolated unit coverage for the query service using mocked schema/query functions.
- Create `tests/test_harness_notion_filters.py`: cover harness routing and persisted numeric record selection without live Notion access.

### Task 1: Create the typed live-Notion query service

**Files:**
- Modify: `src/career/services/notion.py:1-224`
- Test: `tests/test_query_engine.py`

**Interfaces:**
- Consumes: `legacy_notion.retrieve_data_source(token, data_source_id)`, `legacy_notion.discover_data_source_id(token, database_id)`, `legacy_notion.query_data_source(token, data_source_id, payload)`, `legacy_notion.prop_text(prop)`.
- Produces: `parse_application_filters(text: str, schema: dict) -> list[dict]`, `build_application_filter(filters: list[dict]) -> dict`, `query_live_applications(token: str, database_id: str, filter_text: str, limit: int = 20) -> dict`, and `format_application_table(result: dict) -> str`.

- [ ] **Step 1: Write failing parser and payload tests**

```python
from career.services import notion


SCHEMA = {
    "properties": {
        "Etapa Funil": {"id": "stage", "type": "status", "status": {"options": [{"name": "Fila Agente"}]}},
        "empresa_int": {"id": "company", "type": "rich_text", "rich_text": {}},
        "avaliação de aderencia claude": {"id": "fit", "type": "number", "number": {"format": "number"}},
    }
}


def test_builds_native_and_filter_for_status_and_text():
    filters = notion.parse_application_filters(
        "Etapa Funil Fila Agente e empresa Mercado Livre", SCHEMA
    )
    assert notion.build_application_filter(filters) == {
        "and": [
            {"property": "Etapa Funil", "status": {"equals": "Fila Agente"}},
            {"property": "empresa_int", "rich_text": {"contains": "Mercado Livre"}},
        ]
    }


def test_rejects_unknown_status_option():
    with pytest.raises(ValueError, match="Etapa Funil.*Fila inexistente"):
        notion.parse_application_filters("Etapa Funil Fila inexistente", SCHEMA)


def test_builds_number_comparison_filter():
    filters = notion.parse_application_filters("aderência maior que 7", SCHEMA)
    assert notion.build_application_filter(filters) == {
        "property": "avaliação de aderencia claude", "number": {"greater_than": 7.0}
    }
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/test_query_engine.py -k "native_and_filter or unknown_status_option or number_comparison" -v`

Expected: FAIL because `parse_application_filters` and `build_application_filter` do not exist.

- [ ] **Step 3: Implement schema-backed filter parsing**

Add the following focused helpers to `src/career/services/notion.py`:

```python
def _normalize_filter_text(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def parse_application_filters(text: str, schema: dict) -> list[dict]:
    """Return validated typed filter clauses; raise ValueError for any invalid request."""
    clauses = [item.strip() for item in re.split(r"\s+e\s+", text, flags=re.IGNORECASE) if item.strip()]
    if not clauses:
        raise ValueError("Informe pelo menos um filtro.")
    return [_parse_application_filter_clause(clause, schema) for clause in clauses]


def build_application_filter(filters: list[dict]) -> dict:
    """Translate validated clauses to one official Notion filter or an AND group."""
    payloads = [_build_notion_filter_clause(item) for item in filters]
    return payloads[0] if len(payloads) == 1 else {"and": payloads}
```

Implement `_parse_application_filter_clause` by first matching the longest schema property name or alias at the beginning of the clause, then parsing the remaining text as either an explicit comparator (`maior que`, `maior ou igual a`, `menor que`, `menor ou igual a`, or `igual a`) or an exact-value request. It must return `{"property_name": str, "property_type": str, "operator": str, "value": str | float | bool}`. Implement `_build_notion_filter_clause` to emit the native property object.

Use exact equality for `status` and `select`, `contains` for `title` and `rich_text`, `equals` for `checkbox`, and `greater_than`, `greater_than_or_equal_to`, `less_than`, `less_than_or_equal_to`, or `equals` for `number` and `date`. Reject every other schema type with a message naming the property and its unsupported type. For `status` and `select`, match option names accent- and case-insensitively but preserve the schema's original option spelling in the payload.

- [ ] **Step 4: Run parser and payload tests**

Run: `pytest tests/test_query_engine.py -k "native_and_filter or unknown_status_option or number_comparison" -v`

Expected: PASS.

- [ ] **Step 5: Commit the typed parser**

```bash
git add src/career/services/notion.py tests/test_query_engine.py
git commit -m "feat: add typed Notion application filters"
```

### Task 2: Query live pages and render the compact result

**Files:**
- Modify: `src/career/services/notion.py`
- Test: `tests/test_query_engine.py`

**Interfaces:**
- Consumes: `parse_application_filters`, `build_application_filter`, and the legacy live Notion schema/query helpers from Task 1.
- Produces: `query_live_applications(token, database_id, filter_text, limit=20)` with `status`, `filters`, `count`, `records`, and `available_statuses`; `format_application_table(result)`.

- [ ] **Step 1: Write failing live-query and rendering tests**

```python
def test_query_live_applications_uses_schema_and_native_filter(monkeypatch):
    monkeypatch.setattr(notion.legacy_notion, "discover_data_source_id", lambda *_: "source-1")
    monkeypatch.setattr(notion.legacy_notion, "retrieve_data_source", lambda *_: SCHEMA)
    captured = {}
    def query_data_source(_token, _source, payload):
        captured["payload"] = payload
        return {"results": []}
    monkeypatch.setattr(
        notion.legacy_notion,
        "query_data_source",
        query_data_source,
    )

    result = notion.query_live_applications("token", "database", "Etapa Funil Fila Agente")

    assert result["count"] == 0
    assert captured["payload"]["filter"] == {
        "property": "Etapa Funil", "status": {"equals": "Fila Agente"}
    }
    assert captured["payload"]["page_size"] == 20


def test_format_application_table_uses_only_short_columns():
    text = notion.format_application_table({
        "filters": ["Etapa Funil = Fila Agente"],
        "count": 1,
        "records": [{
            "record_id": 123, "role": "Director", "company": "Acme",
            "status": "Fila Agente", "fit_score": 8.0, "notion_url": "https://notion.so/123",
        }],
    })
    assert "ID | Cargo | Empresa | Etapa Funil | Aderência | Link" in text
    assert "123" in text
    assert "description" not in text
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/test_query_engine.py -k "live_applications or short_columns" -v`

Expected: FAIL because live-query and table formatter functions do not exist.

- [ ] **Step 3: Implement live query and projection**

Implement `query_live_applications` with these exact rules:

```python
def query_live_applications(token: str, database_id: str, filter_text: str, limit: int = 20) -> dict:
    if not filter_text.strip():
        raise ValueError("Informe pelo menos um filtro. Use Etapa Funil com um dos status disponíveis.")
    data_source_id = legacy_notion.discover_data_source_id(token, database_id)
    schema = legacy_notion.retrieve_data_source(token, data_source_id)
    filters = parse_application_filters(filter_text, schema)
    payload = {"page_size": min(max(limit, 1), 20), "filter": build_application_filter(filters)}
    response = legacy_notion.query_data_source(token, data_source_id, payload)
    records = [_direct_application_record(page) for page in response.get("results", [])]
    return {"status": "completed", "filters": _display_filters(filters), "count": len(records), "records": records, "available_statuses": _status_options(schema)}
```

Render Markdown with exactly the six specified columns. Escape pipe characters in cell values, render missing values as `-`, and return a concise zero-result line that includes the applied filter display strings. Do not request a second page: the feature limit is 20 displayed records.

- [ ] **Step 4: Run the focused tests**

Run: `pytest tests/test_query_engine.py -k "live_applications or short_columns" -v`

Expected: PASS.

- [ ] **Step 5: Commit live querying and formatting**

```bash
git add src/career/services/notion.py tests/test_query_engine.py
git commit -m "feat: list filtered Notion applications live"
```

### Task 3: Expose a read-only CLI command

**Files:**
- Modify: `scripts/notion_sync.py:2891-3033`
- Modify: `package.json:64-84`
- Test: `tests/test_query_engine.py`

**Interfaces:**
- Consumes: `career.services.notion.notion_config`, `query_live_applications`, and `format_application_table`.
- Produces: `python3 scripts/notion_sync.py list-filtered --filter "Etapa Funil Fila Agente" [--limit 20]` and `npm run notion:list-filtered -- --filter "Etapa Funil Fila Agente"`.

- [ ] **Step 1: Write failing CLI delegation tests**

```python
def test_list_filtered_cli_delegates_to_service(monkeypatch, capsys):
    monkeypatch.setattr(notion_sync, "notion_config", lambda: ("token", "database"))
    monkeypatch.setattr(
        "career.services.notion.query_live_applications",
        lambda *_args, **_kwargs: {"status": "completed", "filters": ["Etapa Funil = Fila Agente"], "count": 0, "records": []},
    )
    monkeypatch.setattr("sys.argv", ["notion_sync.py", "list-filtered", "--filter", "Etapa Funil Fila Agente"])

    assert notion_sync.main() == 0
    assert "0 registro(s)" in capsys.readouterr().out
```

- [ ] **Step 2: Run the CLI test and verify failure**

Run: `pytest tests/test_query_engine.py::test_list_filtered_cli_delegates_to_service -v`

Expected: FAIL because `list-filtered` is not an argparse command.

- [ ] **Step 3: Add the CLI parser and package script**

Add this parser beside the current `list` parser:

```python
filtered_list_parser = subparsers.add_parser("list-filtered")
filtered_list_parser.add_argument("--filter", required=True)
filtered_list_parser.add_argument("--limit", type=int, default=20)
```

In `main`, import `career.services.notion` only in the `list-filtered` branch, call `query_live_applications(token, database_id, args.filter, args.limit)`, print `format_application_table(result)`, and convert `ValueError` into a concise user-facing error with return code `2`. Add this package entry:

```json
"notion:list-filtered": "./scripts/python.sh scripts/notion_sync.py list-filtered"
```

Do not alter the `list_pages` implementation or the existing `notion:list` command.

- [ ] **Step 4: Run the CLI test and existing list tests**

Run: `pytest tests/test_query_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the CLI surface**

```bash
git add scripts/notion_sync.py package.json tests/test_query_engine.py
git commit -m "feat: expose filtered Notion list command"
```

### Task 4: Route filtered list requests and selected IDs in the harness

**Files:**
- Modify: `src/career/services/harness_supervisor.py:122-248,374-508,918-948`
- Create: `tests/test_harness_notion_filters.py`

**Interfaces:**
- Consumes: `career.services.notion.notion_config`, `query_live_applications`, and `format_application_table`.
- Produces: `workflow == "notion_application_list"`, pending input with `input_kind == "notion_record_selection"`, and numeric selection rewritten to `avalie vaga Notion <ID>`.

- [ ] **Step 1: Write failing routing and selection tests**

```python
from pathlib import Path

from career.services.harness_supervisor import HarnessSupervisor


def test_classifies_notion_status_list_request():
    supervisor = HarnessSupervisor(root=Path.cwd())
    decision = supervisor.classify("traga vagas com Etapa Funil Fila Agente")
    assert decision.workflow == "notion_application_list"
    assert decision.parameters == {"filter_text": "Etapa Funil Fila Agente"}


def test_selection_from_filtered_list_routes_to_existing_analysis(tmp_path, monkeypatch):
    supervisor = HarnessSupervisor(root=tmp_path)
    supervisor._write_pending_input({"input_kind": "notion_record_selection", "record_ids": [123]})
    pending = supervisor._resolve_pending_input("123")
    assert pending == {"input_kind": "notion_record_selection", "message": "avalie vaga Notion 123"}


def test_rejects_id_not_returned_by_filtered_list(tmp_path):
    supervisor = HarnessSupervisor(root=tmp_path)
    supervisor._write_pending_input({"input_kind": "notion_record_selection", "record_ids": [123]})
    assert supervisor._resolve_pending_input("999") is None
```

- [ ] **Step 2: Run the harness tests and verify failure**

Run: `pytest tests/test_harness_notion_filters.py -v`

Expected: FAIL because the new workflow and selection input kind are not implemented.

- [ ] **Step 3: Implement request detection and live execution**

In `classify`, before generic Notion analysis and write handling, recognize list verbs (`traga`, `liste`, `listar`, `registros`, `vagas com`) only when at least one filter expression is present. Return:

```python
return self._decision(
    "notion_application_list",
    "query",
    "high",
    "notion_live_filtered_list_request",
    parameters={"filter_text": extracted_filter_text},
)
```

In `handle_message`, add a `notion_application_list` branch that obtains credentials only through `career.services.notion.notion_config`, executes the live service, writes `pending_input.json` with `input_kind: notion_record_selection` and only the returned numeric `record_ids`, and returns a completed payload with `kind: notion_application_list`, `display_text`, `count`, and `filters`.

Extend `_resolve_pending_input` with an exact numeric match for `notion_record_selection`. Rewrite a listed ID to `avalie vaga Notion <ID>` and delete the pending context. For any unlisted numeric reply, retain the pending context and let the caller return `notion_record_selection_not_found` with the valid IDs. Preserve the existing menu-number behavior by resolving filtered-list pending input before menu selection.

- [ ] **Step 4: Run the harness tests and relevant regression tests**

Run: `pytest tests/test_harness_notion_filters.py tests/test_agent_contracts.py tests/test_session_memory.py -v`

Expected: PASS.

- [ ] **Step 5: Commit harness routing**

```bash
git add src/career/services/harness_supervisor.py tests/test_harness_notion_filters.py
git commit -m "feat: route filtered Notion lists to analysis"
```

### Task 5: Validate the complete change and document the command

**Files:**
- Modify: `.opencode/skills/notion-transactions/SKILL.md`
- Modify: `AGENTS.md`
- Test: `tests/test_query_engine.py`
- Test: `tests/test_harness_notion_filters.py`

**Interfaces:**
- Consumes: the CLI command and harness flow from Tasks 1-4.
- Produces: documented conversational examples and a fully verified filtered-list feature.

- [ ] **Step 1: Add failing behavior coverage for no-filter guidance**

```python
def test_no_filter_request_returns_status_guidance(monkeypatch):
    supervisor = HarnessSupervisor(root=Path.cwd())
    result = supervisor.handle_message("traga vagas", execute=True)
    assert result["status"] == "awaiting_input"
    assert "Etapa Funil" in result["result"]["display_text"]
```

- [ ] **Step 2: Run the guidance test and verify failure**

Run: `pytest tests/test_harness_notion_filters.py::test_no_filter_request_returns_status_guidance -v`

Expected: FAIL because generic list requests do not yet return filter guidance.

- [ ] **Step 3: Implement generic-list guidance and update operational docs**

Return `awaiting_input` for generic list phrases with `input_kind: notion_application_filter` and a concise display message that names `Etapa Funil` and requests at least one filter. Add the following examples to the Notion skill and the Notion section of `AGENTS.md`:

```text
traga vagas com Etapa Funil Fila Agente
liste registros com Etapa Funil Aplicação andamento e empresa Mercado Livre
```

Document that the source is live Notion, filters are AND-only, and replying with a listed ID starts the existing analysis pipeline.

- [ ] **Step 4: Run all targeted tests and structural validation**

Run: `pytest tests/test_query_engine.py tests/test_harness_notion_filters.py tests/test_agent_contracts.py tests/test_session_memory.py -v && npm run validate:structure`

Expected: all pytest tests PASS and structure validation reports success.

- [ ] **Step 5: Perform a manual safe smoke check**

Run: `npm run harness -- --message "traga vagas com Etapa Funil Fila Agente" --channel cli`

Expected: a read-only short table with only matching records, or a concise blocked error if Notion credentials/network access are unavailable. Do not write to Notion.

- [ ] **Step 6: Commit documentation and final validation coverage**

```bash
git add AGENTS.md .opencode/skills/notion-transactions/SKILL.md tests/test_harness_notion_filters.py
git commit -m "docs: document live Notion application filters"
```

## Plan Self-Review

- Spec coverage: Tasks 1-2 implement live schema discovery, typed validation, native Notion filters, compact output, status options, empty results, and the 20-row limit. Task 3 provides the compatible CLI surface. Task 4 provides conversational routing and safe ID selection into the existing analysis route. Task 5 enforces generic-list guidance, documentation, structural validation, and a read-only smoke check.
- Placeholder scan: no incomplete work markers or unspecified test cases remain.
- Type consistency: Tasks 1-2 define the query-service functions consumed by Tasks 3-4. Task 4 writes and resolves the explicit `notion_record_selection` pending-input kind. The selected message matches the existing `NOTION_ID_RE` analysis path exactly.
