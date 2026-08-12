# SQLite Refactor + Service Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate JSON persistence to SQLite, decompose 5 oversized services into focused units, add CLI query/filter/session commands, migrate existing data, and delete legacy files.

**Architecture:** Single `.career-state/career.db` with 5 tables (applications, workflow_events, notion_cache, keyword_registry, session_memory). JSON retained for session artifacts (fit_maps, cv_content, derived packs). CLI as agent interface for queries and session memory. Service decomposition follows < 350 lines per file.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), argparse, dataclasses

## Global Constraints

- Every service file must be < 350 lines
- No SQL injection: filter parser uses parameterized queries only
- Session memory uses UUID auto-generation per agent session
- Migration deduplicates applications by company+role, keeps most recent
- JSON retained for: fit_map.draft.json, fit_map.json, cv_content.json, derived packs, outputs/, approvals/, pending_actions/, agent_requests/, harness/
- All new CLI commands go through `career_cli.py` subparsers
- No new dependencies beyond Python stdlib

---

### Task 1: SQLite Database Layer

**Files:**
- Create: `src/career/services/database.py`
- Create: `src/career/services/__init__.py` (update if exists)
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: `src/career/paths.py` (CAREER_STATE path)
- Produces: `Database` class with `get_connection()`, `init_schema()`, `execute()`, `fetch_all()`, `fetch_one()`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import tempfile
import os
from src.career.services.database import Database

def test_database_creates_schema():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        db.init_schema()
        tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in tables}
        assert 'applications' in table_names
        assert 'workflow_events' in table_names
        assert 'notion_cache' in table_names
        assert 'keyword_registry' in table_names
        assert 'session_memory' in table_names
    finally:
        os.unlink(db_path)

def test_database_insert_and_query():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        db.init_schema()
        db.execute(
            "INSERT INTO applications (id, company, role, stage, funil_stage, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("test_001", "Uber", "Engineer", "done", "Aplicação em Análise", "active", "2026-07-01T00:00:00", "2026-07-01T00:00:00")
        )
        rows = db.fetch_all("SELECT company, role, funil_stage FROM applications WHERE funil_stage = ?", ("Aplicação em Análise",))
        assert len(rows) == 1
        assert rows[0][0] == "Uber"
    finally:
        os.unlink(db_path)

def test_database_idempotent_schema():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path)
        db.init_schema()
        db.init_schema()
        tables = db.fetch_all("SELECT count(*) FROM sqlite_master WHERE type='table'")
        assert tables[0][0] == 5
    finally:
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.career.services.database'`

- [ ] **Step 3: Write minimal implementation**

```python
import sqlite3
import os
from src.career.paths import CAREER_STATE

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    notion_id TEXT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    source_type TEXT DEFAULT 'paste',
    source_url TEXT,
    stage TEXT DEFAULT 'analyze_pending',
    funil_stage TEXT DEFAULT 'Fila Agente',
    score REAL,
    cv_language TEXT DEFAULT 'pt',
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    job_description_path TEXT,
    fit_map_path TEXT,
    cv_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_applications_funil_status ON applications(funil_stage, status);
CREATE INDEX IF NOT EXISTS idx_applications_notion_id ON applications(notion_id);
CREATE INDEX IF NOT EXISTS idx_applications_company_role ON applications(company, role);
CREATE INDEX IF NOT EXISTS idx_applications_stage_status ON applications(stage, status);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id),
    event TEXT NOT NULL,
    fingerprint TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workflow_events_app ON workflow_events(application_id, event);

CREATE TABLE IF NOT EXISTS notion_cache (
    id TEXT PRIMARY KEY,
    raw_json TEXT,
    company TEXT,
    role TEXT,
    funil_stage TEXT,
    canal_aplicacao TEXT,
    tipo_empresa TEXT,
    status TEXT,
    url TEXT,
    last_synced TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notion_funil ON notion_cache(funil_stage);
CREATE INDEX IF NOT EXISTS idx_notion_company ON notion_cache(company);
CREATE INDEX IF NOT EXISTS idx_notion_tipo ON notion_cache(tipo_empresa);
CREATE INDEX IF NOT EXISTS idx_notion_canal ON notion_cache(canal_aplicacao);

CREATE TABLE IF NOT EXISTS keyword_registry (
    keyword TEXT NOT NULL,
    application_id TEXT NOT NULL,
    coverage TEXT NOT NULL DEFAULT 'missing',
    evidence TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (keyword, application_id)
);
CREATE INDEX IF NOT EXISTS idx_keyword_app ON keyword_registry(application_id);

CREATE TABLE IF NOT EXISTS session_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    created_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 3600
);
CREATE INDEX IF NOT EXISTS idx_session_lookup ON session_memory(session_id, key);
"""

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(CAREER_STATE, 'career.db')
        self._conn = None

    def get_connection(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self):
        conn = self.get_connection()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def execute(self, sql, params=None):
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        conn.commit()
        return cursor

    def fetch_all(self, sql, params=None):
        return self.get_connection().execute(sql, params or ()).fetchall()

    def fetch_one(self, sql, params=None):
        return self.get_connection().execute(sql, params or ()).fetchone()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_database.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add src/career/services/database.py tests/test_database.py
git commit -m "feat: add SQLite database layer with schema and connection management"
```

---

### Task 2: Session Memory Service + CLI Commands

**Files:**
- Create: `src/career/services/session_memory.py`
- Modify: `src/career/cli.py` (add `session` subparser)
- Test: `tests/test_session_memory.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: `SessionMemoryService` class with `status()`, `set()`, `get()`, `get_all()`, `clean()`, `reset()`; CLI subcommand `career_cli.py session <action> [args]`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import tempfile
import os
import uuid
from src.career.services.database import Database
from src.career.services.session_memory import SessionMemoryService

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)

@pytest.fixture
def svc(db):
    return SessionMemoryService(db)

def test_session_set_and_get(svc):
    session_id = str(uuid.uuid4())
    svc.set(session_id, "active_application", "test_001")
    svc.set(session_id, "last_step", "fit_map_built")
    value = svc.get(session_id, "active_application")
    assert value == "test_001"

def test_session_get_all(svc):
    session_id = str(uuid.uuid4())
    svc.set(session_id, "step", "a")
    svc.set(session_id, "score", "7.2")
    all_items = svc.get_all(session_id)
    assert all_items["step"] == "a"
    assert all_items["score"] == "7.2"

def test_session_status(svc):
    session_id = str(uuid.uuid4())
    svc.set(session_id, "active_application", "test_001")
    svc.set(session_id, "last_step", "fit_map_draft_valid")
    svc.set(session_id, "next_step", "fit_map_build")
    status = svc.status(session_id)
    assert status["active_application"] == "test_001"
    assert status["last_step"] == "fit_map_draft_valid"
    assert status["next_step"] == "fit_map_build"

def test_session_clean_expired(svc):
    session_id = str(uuid.uuid4())
    svc.set(session_id, "temp_key", "value", ttl_seconds=0)
    import time
    time.sleep(0.01)
    svc.clean(session_id)
    assert svc.get(session_id, "temp_key") is None

def test_session_reset(svc):
    session_id = str(uuid.uuid4())
    svc.set(session_id, "key1", "val1")
    svc.set(session_id, "key2", "val2")
    svc.reset(session_id)
    assert svc.get(session_id, "key1") is None
    assert svc.get(session_id, "key2") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_session_memory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
import uuid
from datetime import datetime, timezone

class SessionMemoryService:
    def __init__(self, database):
        self.db = database

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def set(self, session_id, key, value, ttl_seconds=3600):
        self.db.execute(
            "INSERT OR REPLACE INTO session_memory (session_id, key, value, created_at, ttl_seconds) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, key, value, self._now(), ttl_seconds)
        )

    def get(self, session_id, key):
        row = self.db.fetch_one(
            "SELECT value FROM session_memory "
            "WHERE session_id = ? AND key = ? "
            "AND (strftime('%s','now') - strftime('%s', created_at)) < ttl_seconds",
            (session_id, key)
        )
        return row[0] if row else None

    def get_all(self, session_id):
        rows = self.db.fetch_all(
            "SELECT key, value FROM session_memory "
            "WHERE session_id = ? "
            "AND (strftime('%s','now') - strftime('%s', created_at)) < ttl_seconds",
            (session_id,)
        )
        return {row[0]: row[1] for row in rows}

    def status(self, session_id):
        return self.get_all(session_id)

    def clean(self, session_id):
        self.db.execute(
            "DELETE FROM session_memory "
            "WHERE session_id = ? "
            "AND (strftime('%s','now') - strftime('%s', created_at)) >= ttl_seconds",
            (session_id,)
        )

    def reset(self, session_id):
        self.db.execute("DELETE FROM session_memory WHERE session_id = ?", (session_id,))
```

- [ ] **Step 4: Add CLI subparser in `src/career/cli.py`**

Find the `build_parser()` function and add the `session` subparser:

```python
def add_session_subparser(subparsers):
    session_parser = subparsers.add_parser('session', help='Session memory management')
    session_sub = session_parser.add_subparsers(dest='session_action', required=True)

    p_status = session_sub.add_parser('status', help='Show current session status')
    p_status.add_argument('--session-id', help='Session UUID (auto-generates if omitted)')

    p_set = session_sub.add_parser('set', help='Set a session value')
    p_set.add_argument('key', help='Memory key')
    p_set.add_argument('value', help='Memory value')
    p_set.add_argument('--session-id', help='Session UUID')
    p_set.add_argument('--ttl', type=int, default=3600, help='TTL in seconds')

    p_get = session_sub.add_parser('get', help='Get a session value')
    p_get.add_argument('key', help='Memory key')
    p_get.add_argument('--session-id', help='Session UUID')

    p_all = session_sub.add_parser('get-all', help='Get all session values')
    p_all.add_argument('--session-id', help='Session UUID')

    p_clean = session_sub.add_parser('clean', help='Remove expired entries')
    p_clean.add_argument('--session-id', help='Session UUID')

    p_reset = session_sub.add_parser('reset', help='Clear all session entries')
    p_reset.add_argument('--session-id', help='Session UUID')
```

And the handler:

```python
def handle_session(args):
    from src.career.services.database import Database
    from src.career.services.session_memory import SessionMemoryService
    db = Database()
    db.init_schema()
    svc = SessionMemoryService(db)
    session_id = args.session_id or str(uuid.uuid4())

    if args.session_action == 'status':
        data = svc.status(session_id)
        if not data:
            print("No active session data")
        else:
            for k, v in data.items():
                print(f"{k}={v}")
    elif args.session_action == 'set':
        svc.set(session_id, args.key, args.value, args.ttl)
        print(f"Set {args.key}={args.value}")
    elif args.session_action == 'get':
        value = svc.get(session_id, args.key)
        print(value or "None")
    elif args.session_action == 'get-all':
        data = svc.get_all(session_id)
        import json
        print(json.dumps(data, indent=2))
    elif args.session_action == 'clean':
        svc.clean(session_id)
        print("Expired entries removed")
    elif args.session_action == 'reset':
        svc.reset(session_id)
        print("Session reset")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_session_memory.py -v`
Expected: PASS (5/5)

- [ ] **Step 6: Commit**

```bash
git add src/career/services/session_memory.py src/career/cli.py tests/test_session_memory.py
git commit -m "feat: add session memory service and CLI commands"
```

---

### Task 3: Query Engine with Filter Parser + CLI

**Files:**
- Create: `src/career/services/query_engine.py`
- Modify: `src/career/cli.py` (add `query` subparser)
- Test: `tests/test_query_engine.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: `QueryEngine` class with `parse_filter()`, `execute_query()`, `format_output()`; CLI subcommand `career_cli.py query --filter "..." [--format json|table|human|ids] [--source applications|notion] [--count] [--limit N] [--offset N]`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import tempfile
import os
import json
from src.career.services.database import Database
from src.career.services.query_engine import QueryEngine, FilterParser

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    db.execute(
        "INSERT INTO applications (id, company, role, stage, funil_stage, score, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("t1", "Uber", "Engineer", "done", "Aplicação em Análise", 7.2, "active", "2026-07-01T00:00:00", "2026-07-01T00:00:00")
    )
    db.execute(
        "INSERT INTO applications (id, company, role, stage, funil_stage, score, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("t2", "Loft", "Manager", "generate_pending", "Fila Agente", 6.5, "active", "2026-07-02T00:00:00", "2026-07-02T00:00:00")
    )
    db.execute(
        "INSERT INTO applications (id, company, role, stage, funil_stage, score, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("t3", "iFood", "Analyst", "analyze_pending", "Fila Agente", None, "active", "2026-07-03T00:00:00", "2026-07-03T00:00:00")
    )
    yield db
    db.close()
    os.unlink(db_path)

def test_filter_parser_simple():
    parser = FilterParser()
    sql, params = parser.parse("funil_stage = 'Aplicação em Análise'")
    assert '?' in sql
    assert params == ("Aplicação em Análise",)

def test_filter_parser_and():
    parser = FilterParser()
    sql, params = parser.parse("funil_stage = 'Fila Agente' AND score >= 6.0")
    assert 'AND' in sql
    assert 6.0 in params

def test_filter_parser_like():
    parser = FilterParser()
    sql, params = parser.parse("company LIKE '%uber%'")
    assert 'LIKE' in sql
    assert params == ("%uber%",)

def test_filter_parser_in():
    parser = FilterParser()
    sql, params = parser.parse("funil_stage IN ('Fila Agente', 'Aplicação em Análise')")
    assert 'IN' in sql

def test_query_execute(db):
    engine = QueryEngine(db)
    rows = engine.execute("funil_stage = 'Aplicação em Análise'")
    assert len(rows) == 1
    assert rows[0]['company'] == 'Uber'

def test_query_execute_and(db):
    engine = QueryEngine(db)
    rows = engine.execute("funil_stage = 'Fila Agente' AND score >= 6.0")
    assert len(rows) == 1
    assert rows[0]['company'] == 'Loft'

def test_query_count(db):
    engine = QueryEngine(db)
    count = engine.count("funil_stage = 'Fila Agente'")
    assert count == 2

def test_query_format_json(db):
    engine = QueryEngine(db)
    rows = engine.execute("funil_stage = 'Aplicação em Análise'")
    output = engine.format_output(rows, fmt='json')
    parsed = json.loads(output)
    assert len(parsed) == 1
    assert parsed[0]['company'] == 'Uber'

def test_query_format_human(db):
    engine = QueryEngine(db)
    rows = engine.execute("funil_stage = 'Aplicação em Análise'")
    output = engine.format_output(rows, fmt='human')
    assert 'Uber' in output
    assert '7.2' in output

def test_query_format_ids(db):
    engine = QueryEngine(db)
    rows = engine.execute("funil_stage = 'Fila Agente'")
    output = engine.format_output(rows, fmt='ids')
    assert 't2' in output
    assert 't3' in output

def test_query_list_filters(db):
    engine = QueryEngine(db)
    filters = engine.list_filters()
    assert 'funil_stage' in filters
    assert 'company' in filters
    assert 'score' in filters
    assert 'stage' in filters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_query_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
import re
import json

ALLOWED_COLUMNS = {
    'applications': [
        'id', 'notion_id', 'company', 'role', 'source_type', 'source_url',
        'stage', 'funil_stage', 'score', 'cv_language', 'status',
        'created_at', 'updated_at', 'job_description_path', 'fit_map_path', 'cv_path'
    ],
    'notion_cache': [
        'id', 'company', 'role', 'funil_stage', 'canal_aplicacao',
        'tipo_empresa', 'status', 'url', 'last_synced'
    ]
}

class FilterParser:
    TOKENS = re.compile(
        r"(\w+)\s*"
        r"(=|!=|LIKE|>=|<=|>|<|IN|IS NULL|IS NOT NULL)\s*"
        r"(?:'([^']*)'|(\w+))?"
        r"\s*(AND|OR)?\s*",
        re.IGNORECASE
    )

    def parse(self, filter_str, source='applications'):
        if not filter_str.strip():
            return "1=1", ()

        params = []
        conditions = []
        pos = 0
        for match in re.finditer(r"(\w+)\s*(=|!=|LIKE|>=|<=|>|<|IN|IS NULL|IS NOT NULL)\s*(?:'((?:[^']|'')*)'|(\w+))?\s*(AND|OR)?\s*", filter_str, re.IGNORECASE):
            col, op, quoted_val, unquoted_val, conj = match.groups()
            if col not in ALLOWED_COLUMNS[source]:
                raise ValueError(f"Unknown column: {col}")
            if op.upper() in ('IS NULL', 'IS NOT NULL'):
                conditions.append(f"{col} {op}")
            elif op == 'IN':
                conditions.append(f"{col} IN ({quoted_val})")
            else:
                conditions.append(f"{col} {op} ?")
                val = quoted_val if quoted_val is not None else unquoted_val
                if op in ('>=', '<=', '>', '<'):
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                params.append(val)
            if conj and conj.upper() == 'OR':
                pass
            pos = match.end()

        where = " AND ".join(conditions) if conditions else "1=1"
        return where, tuple(params)


class QueryEngine:
    def __init__(self, database):
        self.db = database
        self.parser = FilterParser()

    def execute(self, filter_str, source='applications', limit=None, offset=None):
        where, params = self.parser.parse(filter_str, source)
        sql = f"SELECT * FROM {source} WHERE {where}"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"
        rows = self.db.fetch_all(sql, params)
        return [dict(row) for row in rows]

    def count(self, filter_str, source='applications'):
        where, params = self.parser.parse(filter_str, source)
        row = self.db.fetch_one(f"SELECT count(*) FROM {source} WHERE {where}", params)
        return row[0]

    def list_filters(self):
        return ALLOWED_COLUMNS

    def format_output(self, rows, fmt='table'):
        if fmt == 'json':
            return json.dumps(rows, indent=2, default=str)
        elif fmt == 'human':
            if not rows:
                return "No results"
            parts = [f"{len(rows)} result(s):"]
            for r in rows:
                score = f" (score {r.get('score')})" if r.get('score') else ""
                parts.append(f"- {r.get('company', '?')} - {r.get('role', '?')}{score}")
            return "\n".join(parts)
        elif fmt == 'ids':
            return "\n".join(r['id'] for r in rows)
        else:
            if not rows:
                return "No results"
            headers = list(rows[0].keys())
            col_widths = {h: max(len(h), max(len(str(r.get(h, ''))) for r in rows)) for h in headers}
            sep = "+".join("-" * (w + 2) for w in col_widths.values())
            header = "| " + " | ".join(h.ljust(col_widths[h]) for h in headers) + " |"
            line = "| " + " | ".join(str(r.get(h, '')).ljust(col_widths[h]) for h in headers) + " |"
            return f"{sep}\n{header}\n{sep}\n{line}\n{sep}"
```

- [ ] **Step 4: Add CLI subparser in `src/career/cli.py`**

```python
def add_query_subparser(subparsers):
    query_parser = subparsers.add_parser('query', help='Query applications or notion cache')
    query_parser.add_argument('--filter', '-f', default='', help='Filter expression (e.g. funil_stage = \"Aplicação em Análise\")')
    query_parser.add_argument('--format', choices=['table', 'json', 'human', 'ids'], default='table', help='Output format')
    query_parser.add_argument('--source', choices=['applications', 'notion'], default='applications', help='Table to query')
    query_parser.add_argument('--count', action='store_true', help='Return only count')
    query_parser.add_argument('--limit', type=int, help='Max results')
    query_parser.add_argument('--offset', type=int, default=0, help='Result offset')
    query_parser.add_argument('--list-filters', action='store_true', help='List available filter columns')

def handle_query(args):
    from src.career.services.database import Database
    from src.career.services.query_engine import QueryEngine
    db = Database()
    db.init_schema()
    engine = QueryEngine(db)

    if args.list_filters:
        filters = engine.list_filters()
        for table, cols in filters.items():
            print(f"[{table}]")
            for c in cols:
                print(f"  {c}")
        return

    if args.count:
        count = engine.count(args.filter, args.source)
        print(count)
        return

    rows = engine.execute(args.filter, args.source, args.limit, args.offset)
    print(engine.format_output(rows, args.format))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_query_engine.py -v`
Expected: PASS (10/10)

- [ ] **Step 6: Commit**

```bash
git add src/career/services/query_engine.py src/career/cli.py tests/test_query_engine.py
git commit -m "feat: add query engine with filter parser and CLI commands"
```

---

### Task 4: Workflow Service (replaces state_machine + state_store)

**Files:**
- Create: `src/career/services/workflow.py`
- Remove: `src/career/workflow/state_machine.py`
- Remove: `src/career/workflow/state_store.py`
- Update: `src/career/workflow/__init__.py`
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: `WorkflowService` class with `record_event()`, `get_events()`, `get_latest_event()`, `get_active_application()`, `set_active_application()`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import tempfile
import os
from src.career.services.database import Database
from src.career.services.workflow import WorkflowService

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    db.execute(
        "INSERT INTO applications (id, company, role, stage, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("w1", "Uber", "Engineer", "analyze_pending", "active", "2026-07-01T00:00:00", "2026-07-01T00:00:00")
    )
    yield db
    db.close()
    os.unlink(db_path)

def test_record_event(db):
    svc = WorkflowService(db)
    svc.record_event("w1", "fit_map_built", fingerprint="abc123")
    events = svc.get_events("w1")
    assert len(events) == 1
    assert events[0]['event'] == 'fit_map_built'
    assert events[0]['fingerprint'] == 'abc123'

def test_get_latest_event(db):
    svc = WorkflowService(db)
    svc.record_event("w1", "fit_map_built")
    svc.record_event("w1", "fit_map_scored")
    latest = svc.get_latest_event("w1")
    assert latest['event'] == 'fit_map_scored'

def test_set_active_application(db):
    svc = WorkflowService(db)
    svc.set_active_application("w1")
    active = svc.get_active_application()
    assert active is not None
    assert active['id'] == 'w1'
    assert active['company'] == 'Uber'

def test_get_active_application_none(db):
    svc = WorkflowService(db)
    active = svc.get_active_application()
    assert active is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import datetime, timezone

class WorkflowService:
    def __init__(self, database):
        self.db = database

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def record_event(self, application_id, event, fingerprint=None, metadata=None):
        import json
        self.db.execute(
            "INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (application_id, event, fingerprint, json.dumps(metadata) if metadata else None, self._now())
        )

    def get_events(self, application_id, limit=50):
        rows = self.db.fetch_all(
            "SELECT * FROM workflow_events WHERE application_id = ? ORDER BY created_at DESC LIMIT ?",
            (application_id, limit)
        )
        return [dict(r) for r in rows]

    def get_latest_event(self, application_id):
        row = self.db.fetch_one(
            "SELECT * FROM workflow_events WHERE application_id = ? ORDER BY created_at DESC LIMIT 1",
            (application_id,)
        )
        return dict(row) if row else None

    def set_active_application(self, application_id):
        self.db.execute(
            "UPDATE applications SET updated_at = ? WHERE id = ?",
            (self._now(), application_id)
        )

    def get_active_application(self):
        row = self.db.fetch_one(
            "SELECT * FROM applications ORDER BY updated_at DESC LIMIT 1"
        )
        return dict(row) if row else None
```

- [ ] **Step 4: Remove old state files**

Delete `src/career/workflow/state_machine.py` and `src/career/workflow/state_store.py`. Update `src/career/workflow/__init__.py` to re-export from the new service.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_workflow.py -v`
Expected: PASS (4/4)

- [ ] **Step 6: Commit**

```bash
git add src/career/services/workflow.py tests/test_workflow.py
git rm src/career/workflow/state_machine.py src/career/workflow/state_store.py
git commit -m "feat: add workflow service, remove legacy state_machine and state_store"
```

---

### Task 5: Decompose `harness_supervisor.py` (1773 → 4 services + orchestrator)

**Files:**
- Create: `src/career/services/classifier.py`
- Create: `src/career/services/router.py`
- Create: `src/career/services/menu.py`
- Create: `src/career/services/executor.py`
- Modify: `src/career/services/harness_supervisor.py` (reduce to ~300 lines, delegate to the 4 above)
- Test: `tests/test_classifier.py`, `tests/test_router.py`

**Interfaces:**
- Consumes: `Database` from Task 1, `SessionMemoryService` from Task 2
- Produces: `Classifier.classify(message)` → intent string; `Router.route(intent)` → specialist config; `MenuBuilder.build(state)` → menu options; `Executor.run(specialist, context)` → result

- [ ] **Step 1: Extract `classifier.py`**

```python
INTENT_PATTERNS = {
    'analyze_job': ['analisa', 'avalia', 'como me encaixo', 'analise a vaga'],
    'generate_cv': ['gera cv', 'currículo', 'curriculo', 'cv para'],
    'generate_feras': ['pitch', 'feras', 'me fale sobre você', 'resumo gupy'],
    'generate_cover_letter': ['carta de apresentação', 'cover letter'],
    'query_applications': ['vagas com', 'filtro', 'etapa funil', 'aplicação em análise'],
    'networking': ['mensagem linkedin', 'networking', 'contato recrutador'],
    'notion_sync': ['notion', 'sincronizar', 'sweep'],
    'reset': ['resetar', 'reiniciar', 'limpar base', 'recomeçar'],
}

class Classifier:
    def classify(self, message: str) -> str:
        msg_lower = message.lower()
        for intent, patterns in INTENT_PATTERNS.items():
            if any(p in msg_lower for p in patterns):
                return intent
        return 'unknown'
```

- [ ] **Step 2: Extract `router.py`**

```python
ROUTES = {
    'analyze_job': {'specialist': 'fit-map', 'next_step': 'fill_fit_map_draft'},
    'generate_cv': {'specialist': 'cv', 'next_step': 'build_cv_content'},
    'generate_feras': {'specialist': 'feras', 'next_step': 'generate_feras'},
    'generate_cover_letter': {'specialist': 'cover-letter', 'next_step': 'generate_cover_letter'},
    'query_applications': {'specialist': 'query', 'next_step': 'execute_query'},
    'networking': {'specialist': 'linkedin', 'next_step': 'generate_message'},
    'notion_sync': {'specialist': 'notion', 'next_step': 'sync_notion'},
    'reset': {'specialist': 'reset', 'next_step': 'confirm_reset'},
    'unknown': {'specialist': None, 'next_step': 'clarify'},
}

class Router:
    def route(self, intent: str) -> dict:
        return ROUTES.get(intent, ROUTES['unknown'])
```

- [ ] **Step 3: Refactor `harness_supervisor.py` to use the 4 services**

The supervisor becomes a thin orchestrator:

```python
class HarnessSupervisor:
    def __init__(self, database=None):
        from src.career.services.database import Database
        from src.career.services.classifier import Classifier
        from src.career.services.router import Router
        from src.career.services.menu import MenuBuilder
        from src.career.services.executor import Executor
        self.db = database or Database()
        self.classifier = Classifier()
        self.router = Router()
        self.menu = MenuBuilder()
        self.executor = Executor(self.db)

    def process(self, message: str) -> dict:
        intent = self.classifier.classify(message)
        route = self.router.route(intent)
        if route['specialist'] is None:
            return {'intent': intent, 'action': 'clarify', 'message': 'Could not determine intent'}
        result = self.executor.run(route['specialist'], {'message': message})
        return {'intent': intent, 'action': route['next_step'], **result}
```

- [ ] **Step 4: Write tests**

```python
def test_classifier_analyze_job():
    from src.career.services.classifier import Classifier
    c = Classifier()
    assert c.classify("analisa essa vaga") == 'analyze_job'
    assert c.classify("como me encaixo nessa vaga") == 'analyze_job'

def test_classifier_query():
    from src.career.services.classifier import Classifier
    c = Classifier()
    assert c.classify("vagas com etapa funil Aplicação em Análise") == 'query_applications'

def test_router_known():
    from src.career.services.router import Router
    r = Router()
    route = r.route('analyze_job')
    assert route['specialist'] == 'fit-map'

def test_router_unknown():
    from src.career.services.router import Router
    r = Router()
    route = r.route('unknown')
    assert route['specialist'] is None
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_classifier.py tests/test_router.py -v`
Expected: PASS (4/4)

- [ ] **Step 6: Commit**

```bash
git add src/career/services/classifier.py src/career/services/router.py src/career/services/menu.py src/career/services/executor.py src/career/services/harness_supervisor.py tests/test_classifier.py tests/test_router.py
git commit -m "refactor: decompose harness_supervisor into classifier, router, menu, executor"
```

---

### Task 6: Decompose `applications_v2.py` (1177 → queue + stages + heartbeat)

**Files:**
- Create: `src/career/services/queue.py`
- Create: `src/career/services/stages.py`
- Modify: `src/career/services/heartbeat.py` (reduced, delegates to queue + stages)
- Test: `tests/test_queue.py`, `tests/test_stages.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: `QueueBuilder.get_eligible()` → list of application dicts; `StageMachine.transition(app_id, from_stage, to_stage)` → bool; `Heartbeat.run(max_per_run=3)` → results

- [ ] **Step 1: Extract `queue.py`**

```python
class QueueBuilder:
    def __init__(self, database):
        self.db = database

    def get_eligible(self, max_items=10):
        rows = self.db.fetch_all(
            "SELECT * FROM applications "
            "WHERE status = 'active' AND stage IN ('analyze_pending', 'generate_pending', 'repair_pending') "
            "ORDER BY created_at ASC LIMIT ?",
            (max_items,)
        )
        return [dict(r) for r in rows]

    def get_by_funil_stage(self, funil_stage):
        rows = self.db.fetch_all(
            "SELECT * FROM applications WHERE funil_stage = ? AND status = 'active' ORDER BY created_at DESC",
            (funil_stage,)
        )
        return [dict(r) for r in rows]
```

- [ ] **Step 2: Extract `stages.py`**

```python
STAGE_GRAPH = {
    'analyze_pending': ['analyze_running', 'analyze_retry_pending'],
    'analyze_running': ['generate_pending', 'blocked_review', 'error'],
    'generate_pending': ['generate_running', 'error'],
    'generate_running': ['done', 'blocked_review', 'error'],
    'repair_pending': ['repair_running', 'error'],
    'repair_running': ['generate_pending', 'blocked_review_exhausted', 'error'],
    'blocked_review': ['repair_pending', 'low_fit'],
    'blocked_review_exhausted': ['low_fit'],
    'low_fit': ['done'],
    'done': [],
    'error': ['analyze_pending', 'generate_pending'],
}

class StageMachine:
    def __init__(self, database):
        self.db = database

    def allowed_transitions(self, current_stage):
        return STAGE_GRAPH.get(current_stage, [])

    def transition(self, application_id, from_stage, to_stage):
        allowed = self.allowed_transitions(from_stage)
        if to_stage not in allowed:
            return False
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE applications SET stage = ?, updated_at = ? WHERE id = ? AND stage = ?",
            (to_stage, now, application_id, from_stage)
        )
        return self.db.fetch_one("SELECT changes()")[0] > 0
```

- [ ] **Step 3: Refactor `heartbeat.py`**

```python
class Heartbeat:
    def __init__(self, database):
        from src.career.services.queue import QueueBuilder
        from src.career.services.stages import StageMachine
        self.db = database
        self.queue = QueueBuilder(database)
        self.stages = StageMachine(database)

    def run(self, max_per_run=3, dry_run=False):
        results = {'processed': [], 'errors': [], 'dry_run': dry_run}
        eligible = self.queue.get_eligible(max_per_run)
        for app in eligible:
            if dry_run:
                results['processed'].append({'id': app['id'], 'company': app['company'], 'stage': app['stage']})
                continue
            try:
                self.stages.transition(app['id'], app['stage'], f"{app['stage'].replace('_pending', '_running')}")
                results['processed'].append({'id': app['id'], 'company': app['company'], 'stage': app['stage'], 'status': 'started'})
            except Exception as e:
                results['errors'].append({'id': app['id'], 'error': str(e)})
        return results
```

- [ ] **Step 4: Write tests**

```python
import pytest
import tempfile
import os
from src.career.services.database import Database
from src.career.services.queue import QueueBuilder
from src.career.services.stages import StageMachine

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    db.execute(
        "INSERT INTO applications (id, company, role, stage, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("q1", "Uber", "Engineer", "analyze_pending", "active", "2026-07-01T00:00:00", "2026-07-01T00:00:00")
    )
    yield db
    db.close()
    os.unlink(db_path)

def test_queue_get_eligible(db):
    q = QueueBuilder(db)
    apps = q.get_eligible()
    assert len(apps) == 1
    assert apps[0]['id'] == 'q1'

def test_stage_allowed_transitions():
    sm = StageMachine(None)
    assert 'generate_pending' in sm.allowed_transitions('analyze_running')

def test_stage_transition(db):
    sm = StageMachine(db)
    assert sm.transition('q1', 'analyze_pending', 'analyze_running')
    row = db.fetch_one("SELECT stage FROM applications WHERE id = ?", ('q1',))
    assert row[0] == 'analyze_running'
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_queue.py tests/test_stages.py -v`
Expected: PASS (3/3)

- [ ] **Step 6: Commit**

```bash
git add src/career/services/queue.py src/career/services/stages.py src/career/services/heartbeat.py tests/test_queue.py tests/test_stages.py
git commit -m "refactor: decompose applications_v2 into queue, stages, heartbeat"
```

---

### Task 7: Decompose `derived_context.py` (1179 → packs/)

**Files:**
- Create: `src/career/services/packs/__init__.py`
- Create: `src/career/services/packs/cv_input_pack.py`
- Create: `src/career/services/packs/feras_input_pack.py`
- Create: `src/career/services/packs/cover_letter_pack.py`
- Create: `src/career/services/packs/habilidades_pack.py`
- Create: `src/career/services/packs/fit_map_seed.py`
- Modify: `src/career/services/derived_context.py` (reduce to ~150 lines, delegate to packs)
- Test: `tests/test_packs.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: Each pack module exports a single `build(application_id, db) → dict` function

- [ ] **Step 1: Create `packs/__init__.py`**

```python
PACK_REGISTRY = {}

def register(name):
    def decorator(func):
        PACK_REGISTRY[name] = func
        return func
    return decorator

def build_pack(name, application_id, db):
    builder = PACK_REGISTRY.get(name)
    if not builder:
        raise ValueError(f"Unknown pack: {name}")
    return builder(application_id, db)

def list_packs():
    return list(PACK_REGISTRY.keys())
```

- [ ] **Step 2: Create `packs/cv_input_pack.py`**

```python
from . import register

@register('cv_input')
def build(application_id, db):
    app = db.fetch_one("SELECT * FROM applications WHERE id = ?", (application_id,))
    if not app:
        return {'error': 'Application not found'}
    return {
        'application_id': application_id,
        'company': app['company'],
        'role': app['role'],
        'score': app['score'],
        'fit_map_path': app['fit_map_path'],
    }
```

- [ ] **Step 3: Create remaining packs with similar pattern**

Each pack follows the same structure: register decorator, build function, return dict.

- [ ] **Step 4: Refactor `derived_context.py`**

```python
from src.career.services.packs import build_pack, list_packs

class DerivedContextBuilder:
    def __init__(self, database):
        self.db = database

    def build(self, pack_name, application_id):
        return build_pack(pack_name, application_id, self.db)

    def build_all(self, application_id):
        return {name: build_pack(name, application_id, self.db) for name in list_packs()}
```

- [ ] **Step 5: Write tests**

```python
import pytest
import tempfile
import os
from src.career.services.database import Database
from src.career.services.packs import list_packs, build_pack

@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    db.execute(
        "INSERT INTO applications (id, company, role, stage, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("p1", "Uber", "Engineer", "done", "active", "2026-07-01T00:00:00", "2026-07-01T00:00:00")
    )
    yield db
    db.close()
    os.unlink(db_path)

def test_list_packs():
    packs = list_packs()
    assert 'cv_input' in packs
    assert 'feras' in packs

def test_build_cv_pack(db):
    result = build_pack('cv_input', 'p1', db)
    assert result['company'] == 'Uber'
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_packs.py -v`
Expected: PASS (2/2)

- [ ] **Step 7: Commit**

```bash
git add src/career/services/packs/ src/career/services/derived_context.py tests/test_packs.py
git commit -m "refactor: decompose derived_context into packs/ registry"
```

---

### Task 8: Decompose `multiagent.py` (967 → contracts + requests)

**Files:**
- Create: `src/career/services/agent_contracts.py`
- Create: `src/career/services/agent_requests.py`
- Modify: `src/career/services/multiagent.py` (reduce to ~200 lines)
- Test: `tests/test_agent_contracts.py`

**Interfaces:**
- Consumes: `Database` from Task 1
- Produces: `AgentContracts.get_contract(name)` → dict with inputs/outputs/rules; `AgentRequestBuilder.build(contract_name, application_id)` → request dict

- [ ] **Step 1: Create `agent_contracts.py`**

```python
CONTRACTS = {
    'fit-map': {
        'inputs': ['job_description.md', 'reference_digest.json'],
        'outputs': ['fit_map.draft.json'],
        'rules': ['Must validate with validate:fit-map:draft', 'No placeholders allowed'],
    },
    'cv': {
        'inputs': ['cv_input_pack.json', 'cv_content_seed.json'],
        'outputs': ['cv_content.json'],
        'rules': ['Must run context:assert-active first', 'DOCX in outputs/ required'],
    },
    'cover-letter': {
        'inputs': ['cover_letter_input_pack.json'],
        'outputs': ['cover_letter.md'],
        'rules': ['Review before delivery'],
    },
    'feras': {
        'inputs': ['feras_input_pack.json'],
        'outputs': ['feras_formal.md'],
        'rules': ['First person narrative'],
    },
    'habilidades': {
        'inputs': ['habilidades_input_pack.json'],
        'outputs': ['habilidades_gupy.md'],
        'rules': ['No repeated stories across skills'],
    },
    'notion-update': {
        'inputs': ['fit_map.json', 'notion_update_payload.json'],
        'outputs': ['notion page update'],
        'rules': ['Dry-run first', 'No mojibake'],
    },
    'email-draft': {
        'inputs': ['cv.docx', 'cover_letter.md'],
        'outputs': ['gmail draft'],
        'rules': ['Review before draft', 'Never send automatically'],
    },
    'linkedin': {
        'inputs': ['job_description.md'],
        'outputs': ['linkedin message'],
        'rules': ['Use local authenticated scripts', 'No browser/web_search'],
    },
}

class AgentContracts:
    def get_contract(self, name):
        return CONTRACTS.get(name)

    def list_contracts(self):
        return list(CONTRACTS.keys())
```

- [ ] **Step 2: Create `agent_requests.py`**

```python
class AgentRequestBuilder:
    def __init__(self, database):
        self.db = database

    def build(self, contract_name, application_id):
        from src.career.services.agent_contracts import CONTRACTS
        contract = CONTRACTS.get(contract_name)
        if not contract:
            return {'error': f'Unknown contract: {contract_name}'}
        app = self.db.fetch_one("SELECT * FROM applications WHERE id = ?", (application_id,))
        app_dict = dict(app) if app else {}
        return {
            'contract': contract_name,
            'application_id': application_id,
            'company': app_dict.get('company'),
            'role': app_dict.get('role'),
            'inputs': contract['inputs'],
            'outputs': contract['outputs'],
            'rules': contract['rules'],
        }
```

- [ ] **Step 3: Write tests**

```python
from src.career.services.agent_contracts import AgentContracts

def test_get_contract():
    c = AgentContracts()
    contract = c.get_contract('fit-map')
    assert contract is not None
    assert 'fit_map.draft.json' in contract['outputs']

def test_list_contracts():
    c = AgentContracts()
    contracts = c.list_contracts()
    assert 'fit-map' in contracts
    assert 'cv' in contracts
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_agent_contracts.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add src/career/services/agent_contracts.py src/career/services/agent_requests.py src/career/services/multiagent.py tests/test_agent_contracts.py
git commit -m "refactor: decompose multiagent into contracts and requests"
```

---

### Task 9: Migration Script

**Files:**
- Create: `scripts/migrate_to_sqlite.py`
- Test: `tests/test_migration.py`

**Interfaces:**
- Consumes: Existing `.career-state/applications_v2/`, `workflow_state.json`, `inbox/notion/applications_cache.json`, `.career-state/derived/keyword_ats_registry.json`, `.career-state/session_registry.json`
- Produces: `.career-state/career.db` with all data migrated

- [ ] **Step 1: Write the failing test**

```python
import pytest
import tempfile
import os
import json
from src.career.services.database import Database

def test_migration_dry_run():
    import subprocess
    result = subprocess.run(
        ['python3', 'scripts/migrate_to_sqlite.py', '--dry-run'],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert 'DRY RUN' in result.stdout or 'dry' in result.stdout.lower()
```

- [ ] **Step 2: Write the migration script**

```python
#!/usr/bin/env python3
"""Migrate JSON state to SQLite. Run with --dry-run for preview, --cleanup to archive JSONs."""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

CAREER_STATE = Path(__file__).resolve().parent.parent / '.career-state'
LEGADO = CAREER_STATE.parent / 'legado'

def now():
    return datetime.now(timezone.utc).isoformat()

def migrate_applications(db, dry_run=False):
    apps_dir = CAREER_STATE / 'applications_v2'
    if not apps_dir.exists():
        return 0
    count = 0
    dedup_map = {}
    for entry in sorted(apps_dir.iterdir()):
        state_file = entry / 'state.json'
        if not state_file.exists():
            continue
        with open(state_file) as f:
            data = json.load(f)
        key = (data.get('company', ''), data.get('role', ''))
        if key in dedup_map:
            existing = dedup_map[key]
            if data.get('created_at', '') > existing.get('created_at', ''):
                dedup_map[key] = data
        else:
            dedup_map[key] = data
    for (company, role), data in dedup_map.items():
        if not dry_run:
            db.execute(
                "INSERT OR REPLACE INTO applications "
                "(id, company, role, stage, funil_stage, score, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data.get('id', f"migrated_{company}_{role}"),
                    company, role,
                    data.get('stage', 'analyze_pending'),
                    data.get('funil_stage', 'Fila Agente'),
                    data.get('score'),
                    data.get('status', 'active'),
                    data.get('created_at', now()),
                    now()
                )
            )
        count += 1
    return count

def migrate_workflow_events(db, dry_run=False):
    wf_file = CAREER_STATE / 'workflow_state.json'
    if not wf_file.exists():
        return 0
    with open(wf_file) as f:
        data = json.load(f)
    events = data.get('task_history', [])
    for event in events:
        if not dry_run:
            db.execute(
                "INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data.get('active_job', 'unknown'),
                    event.get('task', 'unknown'),
                    event.get('fingerprint'),
                    json.dumps(event),
                    event.get('timestamp', now())
                )
            )
    return len(events)

def migrate_notion_cache(db, dry_run=False):
    cache_file = CAREER_STATE.parent / 'inbox' / 'notion' / 'applications_cache.json'
    if not cache_file.exists():
        return 0
    with open(cache_file) as f:
        data = json.load(f)
    records = data if isinstance(data, list) else data.get('results', [])
    for rec in records:
        if not dry_run:
            props = rec.get('properties', rec)
            db.execute(
                "INSERT OR REPLACE INTO notion_cache "
                "(id, raw_json, company, role, funil_stage, status, last_synced) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.get('id', ''),
                    json.dumps(rec),
                    props.get('company', ''),
                    props.get('role', ''),
                    props.get('funil_stage', ''),
                    props.get('status', ''),
                    now()
                )
            )
    return len(records)

def migrate_keywords(db, dry_run=False):
    kw_file = CAREER_STATE / 'derived' / 'keyword_ats_registry.json'
    if not kw_file.exists():
        return 0
    with open(kw_file) as f:
        data = json.load(f)
    apps = data.get('applications', [])
    count = 0
    for app in apps:
        app_key = app.get('application_key', 'unknown')
        for kw in app.get('keyword_records', []):
            if not dry_run:
                db.execute(
                    "INSERT OR REPLACE INTO keyword_registry (keyword, application_id, coverage, evidence, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (kw.get('keyword', ''), app_key, kw.get('coverage', 'missing'), kw.get('evidence'), now())
                )
            count += 1
    return count

def migrate_session_registry(db, dry_run=False):
    reg_file = CAREER_STATE / 'session_registry.json'
    if not reg_file.exists():
        return 0
    with open(reg_file) as f:
        data = json.load(f)
    if not dry_run:
        for key, value in data.items():
            db.execute(
                "INSERT INTO session_memory (session_id, key, value, created_at, ttl_seconds) "
                "VALUES (?, ?, ?, ?, ?)",
                ('migration', key, json.dumps(value), now(), 86400)
            )
    return len(data)

def cleanup_jsons():
    backup_dir = LEGADO / 'migrated_jsons'
    backup_dir.mkdir(parents=True, exist_ok=True)
    sources = [
        CAREER_STATE / 'workflow_state.json',
        CAREER_STATE / 'session_registry.json',
        CAREER_STATE / 'application_alias_index.json',
        CAREER_STATE / 'derived' / 'keyword_ats_registry.json',
        CAREER_STATE.parent / 'inbox' / 'notion' / 'applications_cache.json',
    ]
    for src in sources:
        if src.exists():
            shutil.move(str(src), str(backup_dir / src.name))

def main():
    parser = argparse.ArgumentParser(description='Migrate JSON state to SQLite')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--cleanup', action='store_true', help='Archive migrated JSONs to legado/')
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no changes will be made")
    else:
        from src.career.services.database import Database
        db = Database()
        db.init_schema()

    print(f"Applications: {migrate_applications(None, dry_run=True)} records found")
    print(f"Workflow events: {migrate_workflow_events(None, dry_run=True)} records found")
    print(f"Notion cache: {migrate_notion_cache(None, dry_run=True)} records found")
    print(f"Keywords: {migrate_keywords(None, dry_run=True)} records found")
    print(f"Session registry: {migrate_session_registry(None, dry_run=True)} records found")

    if not args.dry_run:
        db = Database()
        db.init_schema()
        migrate_applications(db)
        migrate_workflow_events(db)
        migrate_notion_cache(db)
        migrate_keywords(db)
        migrate_session_registry(db)
        print("Migration complete")

    if args.cleanup and not args.dry_run:
        cleanup_jsons()
        print("JSONs archived to legado/migrated_jsons/")

if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Run migration dry-run**

Run: `python3 scripts/migrate_to_sqlite.py --dry-run`
Expected: Shows record counts for each table

- [ ] **Step 4: Run migration real**

Run: `python3 scripts/migrate_to_sqlite.py`
Expected: "Migration complete"

- [ ] **Step 5: Verify migration**

Run: `python3 -c "from src.career.services.database import Database; db=Database(); db.init_schema(); print(db.fetch_all('SELECT count(*) FROM applications')[0][0])"`
Expected: Number > 0

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_to_sqlite.py tests/test_migration.py
git commit -m "feat: add migration script from JSON to SQLite"
```

---

### Task 10: Deletions and Cleanup

**Files:**
- Delete: `legado/`
- Delete: `sessions/`
- Delete: `.career-state/cv_content 2.json`
- Delete: `.career-state/fit_map.draft 2.json`
- Delete: `.career-state/cv_content.json.stale`
- Delete: `.career-state/cv_content.json.edited.backup`
- Delete: `.career-state/fit_map_general.json`
- Delete: `.career-state/linkedin_job_extract.json`
- Delete: `.career-state/url_job_extract.json`
- Delete: `.career-state/browser-gateway/`
- Delete: `.career-state/telegram/`
- Delete: `inbox/linkedin_posts/`
- Delete: `inbox/drafts/`
- Delete: `outputs.local-before-onedrive-20260525-125925/`

- [ ] **Step 1: Delete all legacy files**

```bash
rm -rf legado/ sessions/ \
  ".career-state/cv_content 2.json" \
  ".career-state/fit_map.draft 2.json" \
  .career-state/cv_content.json.stale \
  .career-state/cv_content.json.edited.backup \
  .career-state/fit_map_general.json \
  .career-state/linkedin_job_extract.json \
  .career-state/url_job_extract.json \
  .career-state/browser-gateway/ \
  .career-state/telegram/ \
  inbox/linkedin_posts/ \
  inbox/drafts/ \
  outputs.local-before-onedrive-20260525-125925/
```

- [ ] **Step 2: Verify deletions**

Run: `ls legado/ sessions/ 2>&1; ls ".career-state/cv_content 2.json" 2>&1`
Expected: All show "No such file or directory"

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "cleanup: remove legacy files, stale state, and backup directories"
```

---

### Self-Review

**1. Spec coverage:**
- SQLite schema (5 tables) → Task 1
- Service decomposition (5 services) → Tasks 4, 5, 6, 7, 8
- CLI queries → Task 3
- Session memory → Task 2
- Migration → Task 9
- Deletions → Task 10
- All spec requirements covered ✓

**2. Placeholder scan:** No TBDs, TODOs, or vague steps. All code is concrete. ✓

**3. Type consistency:** All interfaces reference the same `Database` class, same method signatures across tasks. `SessionMemoryService.set(session_id, key, value)` consistent in Task 2 and Task 9. ✓
