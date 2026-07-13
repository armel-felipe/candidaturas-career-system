from __future__ import annotations

import tempfile

from career.services.database import Database
from career.services.workflow import WorkflowService


def _make_db() -> Database:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db = Database(db_path=f.name)
    db.init_schema()
    return db


def _seed_application(db: Database, app_id: str = "app-1") -> None:
    db.execute(
        """INSERT INTO applications (id, company, role, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (app_id, "Acme Corp", "Engineer", "2025-01-01T00:00:00", "2025-01-01T00:00:00"),
    )


def test_record_event():
    db = _make_db()
    svc = WorkflowService(db)
    _seed_application(db)

    svc.record_event("app-1", "fit_map.built", fingerprint="abc123", metadata={"score": 0.85})

    events = svc.get_events("app-1")
    assert len(events) == 1
    assert events[0]["event"] == "fit_map.built"
    assert events[0]["fingerprint"] == "abc123"
    assert events[0]["application_id"] == "app-1"

    db.close()


def test_get_latest_event():
    db = _make_db()
    svc = WorkflowService(db)
    _seed_application(db)

    svc.record_event("app-1", "fit_map.template")
    svc.record_event("app-1", "fit_map.built")

    latest = svc.get_latest_event("app-1")
    assert latest is not None
    assert latest["event"] == "fit_map.built"

    db.close()


def test_set_active_application():
    db = _make_db()
    svc = WorkflowService(db)
    _seed_application(db, "app-1")
    _seed_application(db, "app-2")

    svc.set_active_application("app-2")

    active = svc.get_active_application()
    assert active is not None
    assert active["id"] == "app-2"

    db.close()


def test_get_active_application_none():
    db = _make_db()
    svc = WorkflowService(db)

    active = svc.get_active_application()
    assert active is None

    db.close()
