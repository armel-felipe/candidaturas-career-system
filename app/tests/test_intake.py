from __future__ import annotations

from types import SimpleNamespace

import pytest

from career.services import intake
from career.services.database import Database


def _stubbed_paste_intake(monkeypatch, tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    monkeypatch.setattr(intake, "Database", lambda: database, raising=False)
    monkeypatch.setattr(
        intake.application_context_service,
        "ensure_application",
        lambda **kwargs: SimpleNamespace(
            application_id=f"{kwargs['company'].lower()}_{kwargs['role'].lower()}",
        ),
    )
    monkeypatch.setattr(
        intake.project_service,
        "save_job_description",
        lambda *_args, **_kwargs: tmp_path / "job.md",
    )
    monkeypatch.setattr(
        intake,
        "_run_ready_pipeline",
        lambda *_args, **kwargs: {"source_type": kwargs["source_type"]},
    )
    return database


def test_hermes_intake_claims_current_profile(monkeypatch, tmp_path):
    database = _stubbed_paste_intake(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "agent-a"))

    result = intake.from_paste(
        company="Acme",
        role="Ops",
        text="job text",
        state_store=object(),
    )

    assert result["profile_binding"]["application_id"] == result["application_id"]
    database.close()


def test_new_job_for_bound_profile_requires_explicit_release(monkeypatch, tmp_path):
    database = _stubbed_paste_intake(monkeypatch, tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "agent-a"))

    intake.from_paste(company="Acme", role="Ops", text="job a", state_store=object())

    with pytest.raises(ValueError, match="profile_has_active_application"):
        intake.from_paste(company="Beta", role="Strategy", text="job b", state_store=object())
    database.close()
