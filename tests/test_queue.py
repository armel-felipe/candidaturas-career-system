from __future__ import annotations

import tempfile

import pytest

from career.services.database import Database
from career.services.queue import QueueBuilder


def test_queue_get_eligible():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "analyze_pending", "active", "2025-01-01", "2025-01-01"),
        )
        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-2", "Beta Inc", "Manager", "done", "active", "2025-01-02", "2025-01-02"),
        )

        queue = QueueBuilder(db)
        eligible = queue.get_eligible(max_items=10)

        assert len(eligible) == 1
        assert eligible[0]["id"] == "app-1"
        assert eligible[0]["stage"] == "analyze_pending"

        db.close()


def test_queue_get_eligible_orders_by_created_at():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-older", "Acme Corp", "Engineer", "generate_pending", "active", "2025-01-01", "2025-01-01"),
        )
        db.execute(
            """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-newer", "Beta Inc", "Manager", "analyze_pending", "active", "2025-01-10", "2025-01-10"),
        )

        queue = QueueBuilder(db)
        eligible = queue.get_eligible(max_items=10)

        assert len(eligible) == 2
        assert eligible[0]["id"] == "app-older"
        assert eligible[1]["id"] == "app-newer"

        db.close()


def test_queue_get_eligible_respects_max_items():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        for i in range(5):
            db.execute(
                """INSERT INTO applications (id, company, role, stage, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"app-{i}", "Acme Corp", "Engineer", "analyze_pending", "active", f"2025-01-0{i+1}", f"2025-01-0{i+1}"),
            )

        queue = QueueBuilder(db)
        eligible = queue.get_eligible(max_items=3)

        assert len(eligible) == 3

        db.close()


def test_queue_get_by_funil_stage():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db = Database(db_path=f.name)
        db.init_schema()

        db.execute(
            """INSERT INTO applications (id, company, role, funil_stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-1", "Acme Corp", "Engineer", "Fila Agente", "active", "2025-01-01", "2025-01-01"),
        )
        db.execute(
            """INSERT INTO applications (id, company, role, funil_stage, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("app-2", "Beta Inc", "Manager", "Aplicação Feita", "active", "2025-01-02", "2025-01-02"),
        )

        queue = QueueBuilder(db)
        result = queue.get_by_funil_stage("Fila Agente")

        assert len(result) == 1
        assert result[0]["id"] == "app-1"

        db.close()
