from __future__ import annotations

import json
import tempfile

import pytest

from career.services.database import Database
from career.services.query_engine import FilterParser, QueryEngine


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        database = Database(db_path=f.name)
        database.init_schema()
        yield database
        database.close()


@pytest.fixture
def seeded_db(db):
    apps = [
        ("app-1", "Acme Corp", "Engineer", "Fila Agente", 5.5, "pt", "2025-01-01", "2025-01-01"),
        ("app-2", "Beta Inc", "Analyst", "Aplicação em Análise", 7.2, "en", "2025-01-02", "2025-01-02"),
        ("app-3", "Gamma Ltda", "Manager", "Fila Agente", 6.0, "pt", "2025-01-03", "2025-01-03"),
    ]
    for app in apps:
        db.execute(
            """INSERT INTO applications (id, company, role, funil_stage, score, cv_language, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            app,
        )
    return db


class TestFilterParser:
    def test_filter_parser_simple(self):
        parser = FilterParser()
        where, params = parser.parse("funil_stage = 'Aplicação em Análise'")
        assert "funil_stage" in where
        assert "?" in where
        assert params == ("Aplicação em Análise",)

    def test_filter_parser_and(self):
        parser = FilterParser()
        where, params = parser.parse("funil_stage = 'Fila Agente' AND score >= 6.0")
        assert "AND" in where
        assert "funil_stage" in where
        assert "score" in where
        assert ">=" in where
        assert params == ("Fila Agente", 6.0)

    def test_filter_parser_like(self):
        parser = FilterParser()
        where, params = parser.parse("company LIKE '%uber%'")
        assert "LIKE" in where
        assert params == ("%uber%",)

    def test_filter_parser_in(self):
        parser = FilterParser()
        where, params = parser.parse("funil_stage IN ('Fila Agente', 'Aplicação em Análise')")
        assert "IN" in where
        assert params == ("Fila Agente", "Aplicação em Análise")

    def test_filter_parser_empty(self):
        parser = FilterParser()
        where, params = parser.parse("")
        assert where == "1=1"
        assert params == ()

    def test_filter_parser_unknown_column(self):
        parser = FilterParser()
        with pytest.raises(ValueError, match="Unknown column"):
            parser.parse("nonexistent = 'foo'")

    def test_filter_parser_unknown_source(self):
        parser = FilterParser()
        with pytest.raises(ValueError, match="Unknown source"):
            parser.parse("funil_stage = 'foo'", source="invalid")


class TestQueryEngine:
    def test_query_execute(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Aplicação em Análise'")
        assert len(rows) == 1
        assert rows[0]["id"] == "app-2"
        assert rows[0]["company"] == "Beta Inc"

    def test_query_execute_and(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Fila Agente' AND score >= 6.0")
        assert len(rows) == 1
        assert rows[0]["id"] == "app-3"

    def test_query_count(self, seeded_db):
        engine = QueryEngine(seeded_db)
        cnt = engine.count("funil_stage = 'Fila Agente'")
        assert cnt == 2

    def test_query_count_all(self, seeded_db):
        engine = QueryEngine(seeded_db)
        cnt = engine.count("")
        assert cnt == 3

    def test_query_format_json(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Aplicação em Análise'")
        output = engine.format_output(rows, fmt="json")
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "app-2"

    def test_query_format_human(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Aplicação em Análise'")
        output = engine.format_output(rows, fmt="human")
        assert "1 result(s)" in output
        assert "Beta Inc" in output
        assert "Analyst" in output
        assert "7.2" in output

    def test_query_format_ids(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Fila Agente'")
        output = engine.format_output(rows, fmt="ids")
        assert "app-1" in output
        assert "app-3" in output
        assert "app-2" not in output

    def test_query_format_table(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Aplicação em Análise'")
        output = engine.format_output(rows, fmt="table")
        assert "id" in output
        assert "company" in output
        assert "role" in output
        assert "app-2" in output
        assert "Beta Inc" in output

    def test_query_list_filters(self):
        engine = QueryEngine(Database())
        filters = engine.list_filters()
        assert "applications" in filters
        assert "notion_cache" in filters
        assert "funil_stage" in filters["applications"]
        assert "score" in filters["applications"]
        assert "company" in filters["notion_cache"]

    def test_query_limit_offset(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Fila Agente'", limit=1, offset=0)
        assert len(rows) == 1
        assert rows[0]["id"] == "app-1"

    def test_query_empty_result(self, seeded_db):
        engine = QueryEngine(seeded_db)
        rows = engine.execute("funil_stage = 'Nonexistent'")
        assert rows == []
        output = engine.format_output(rows, fmt="human")
        assert "0 result(s)" in output
