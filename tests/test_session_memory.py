from __future__ import annotations

import tempfile
import time

import pytest

from career.services.database import Database
from career.services.session_memory import SessionMemoryService


def _make_service() -> tuple[SessionMemoryService, Database]:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    db = Database(db_path=f.name)
    db.init_schema()
    svc = SessionMemoryService(db)
    return svc, db, f.name


def test_session_set_and_get():
    svc, db, path = _make_service()
    try:
        svc.set("s1", "key_a", "value_a")
        assert svc.get("s1", "key_a") == "value_a"
        assert svc.get("s1", "nonexistent") is None
    finally:
        db.close()


def test_session_get_all():
    svc, db, path = _make_service()
    try:
        svc.set("s1", "k1", "v1")
        svc.set("s1", "k2", "v2")
        svc.set("s1", "k3", "v3")
        all_ = svc.get_all("s1")
        assert all_ == {"k1": "v1", "k2": "v2", "k3": "v3"}
    finally:
        db.close()


def test_session_status():
    svc, db, path = _make_service()
    try:
        svc.set("s1", "active_application", "app-123")
        svc.set("s1", "last_step", "fit_map.build")
        svc.set("s1", "next_step", "cv.build_content")
        status = svc.status("s1")
        assert status["active_application"] == "app-123"
        assert status["last_step"] == "fit_map.build"
        assert status["next_step"] == "cv.build_content"
    finally:
        db.close()


def test_session_clean_expired():
    svc, db, path = _make_service()
    try:
        svc.set("s1", "ephemeral", "gone", ttl_seconds=0)
        svc.set("s1", "permanent", "stays", ttl_seconds=3600)
        time.sleep(0.01)
        svc.clean("s1")
        assert svc.get("s1", "ephemeral") is None
        assert svc.get("s1", "permanent") == "stays"
    finally:
        db.close()


def test_session_reset():
    svc, db, path = _make_service()
    try:
        svc.set("s1", "k1", "v1")
        svc.set("s1", "k2", "v2")
        assert len(svc.get_all("s1")) == 2
        svc.reset("s1")
        assert svc.get_all("s1") == {}
    finally:
        db.close()
