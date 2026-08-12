from __future__ import annotations

import tempfile

import pytest

from career.services.database import Database
from career.services.packs import build_pack, list_packs, PACK_REGISTRY


def _setup_db():
    db = Database(db_path=tempfile.NamedTemporaryFile(suffix=".db").name)
    db.init_schema()
    db.execute(
        """INSERT INTO applications (id, company, role, score, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("app-1", "Acme Corp", "Engineer", 8.5, "2025-01-01", "2025-01-01"),
    )
    return db


def test_list_packs():
    names = list_packs()
    assert sorted(names) == sorted(["cv_input", "feras", "cover_letter", "habilidades", "fit_map_seed"])


def test_build_cv_pack():
    db = _setup_db()
    result = build_pack("cv_input", "app-1", db)
    assert result["company"] == "Acme Corp"
    assert result["role"] == "Engineer"
    assert result["score"] == 8.5
    db.close()


def test_build_unknown_pack():
    db = _setup_db()
    with pytest.raises(ValueError, match="Unknown pack: nonexistent"):
        build_pack("nonexistent", "app-1", db)
    db.close()


def test_build_all():
    db = _setup_db()
    result = build_pack("cv_input", "app-1", db)
    assert result["application_id"] == "app-1"
    assert result["company"] == "Acme Corp"
    db.close()
