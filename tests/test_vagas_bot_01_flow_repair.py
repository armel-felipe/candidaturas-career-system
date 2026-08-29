from __future__ import annotations

from pathlib import Path

from career.services import application_context
from career.services import intake as intake_service
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.utils import sha256_text


def test_saved_job_selection_resolves_existing_application_from_sqlite(tmp_path: Path):
    url = "https://www.linkedin.com/jobs/view/4456867143/"
    database = Database(tmp_path / "control-plane" / "career.db")
    repository = ApplicationRepository(database)
    repository.create_application(
        ApplicationIdentity(
            application_id="jobgether-existing",
            company="Jobgether",
            role="Director of Operations & Service Growth",
            source_type="linkedin_job",
            source_url=url,
            aliases={"linkedin_job_source_id": url},
        )
    )

    supervisor = HarnessSupervisor(tmp_path)

    assert supervisor._resolve_linkedin_application_id(url) == "jobgether-existing"


def test_saved_job_route_passes_existing_application_id_to_intake(tmp_path, monkeypatch):
    url = "https://www.linkedin.com/jobs/view/4456867143/"
    database = Database(tmp_path / "control-plane" / "career.db")
    ApplicationRepository(database).create_application(
        ApplicationIdentity(
            application_id="jobgether-existing",
            company="Jobgether",
            role="Director of Operations & Service Growth",
            source_type="linkedin_job",
            source_url=url,
            aliases={"linkedin_job_source_id": url},
        )
    )
    supervisor = HarnessSupervisor(tmp_path)
    supervisor._write_menu_state(
        {
            "menu_context": "linkedin_saved_jobs",
            "numbered_items": [
                {
                    "number": 2,
                    "id": "saved-job-2",
                    "title": "Director of Operations & Service Growth",
                    "description": "Jobgether | Remote",
                    "prompt": url,
                }
            ],
        }
    )
    captured = {}

    def fake_from_linkedin_job(*args, **kwargs):
        captured.update(kwargs)
        return {"status": "saved", "application_id": "jobgether-existing"}

    monkeypatch.setattr(intake_service, "from_linkedin_job", fake_from_linkedin_job)
    monkeypatch.setattr(supervisor, "_bind_session_to_intake", lambda *args, **kwargs: None)
    monkeypatch.setattr(supervisor, "execute_specialist", lambda *args, **kwargs: {"status": "completed", "step": "fit-map"})
    monkeypatch.setattr(supervisor, "_decorate_result_payload", lambda result: result)
    monkeypatch.setattr(supervisor, "_sync_menu_state_for_result", lambda result: None)

    supervisor.handle_message("analise a vaga 2", execute=True)

    assert captured["application_id"] == "jobgether-existing"
    assert captured["database"] is supervisor.db


def test_alias_compatibility_mirror_permission_error_does_not_escape(tmp_path, monkeypatch):
    alias_index = tmp_path / "application_alias_index.json"
    monkeypatch.setattr(application_context, "ALIAS_INDEX", alias_index)

    def deny_write(_path, _payload):
        raise PermissionError(13, "permission denied")

    monkeypatch.setattr(application_context, "write_json", deny_write)

    assert (
        application_context._update_alias_index(
            "jobgether-existing",
            {"linkedin_job_source_id": "https://www.linkedin.com/jobs/view/4456867143/"},
        )
        is False
    )


def test_persist_intake_keeps_explicit_application_id_case(tmp_path, monkeypatch):
    career_state = tmp_path / ".career-state"
    monkeypatch.setattr(application_context, "ROOT", tmp_path)
    monkeypatch.setattr(application_context, "CAREER_STATE", career_state)
    monkeypatch.setattr(application_context, "APPLICATIONS_DIR", career_state / "applications_v2")
    monkeypatch.setattr(application_context, "ALIAS_INDEX", career_state / "application_alias_index.json")
    source_text = "Director of Operations & Service Growth\n" + ("Operational context. " * 40)
    application_id = "local_20260827T140831_411140_jobgether_2e6f9365"

    _paths, record = application_context.persist_intake(
        source_type="linkedin_job",
        source_id="https://www.linkedin.com/jobs/view/4456867143/",
        company="Jobgether",
        role="Director of Operations & Service Growth",
        source_text=source_text,
        fingerprint=sha256_text(source_text),
        preferred_id=application_id,
        source_url="https://www.linkedin.com/jobs/view/4456867143/",
        database=Database(tmp_path / "control-plane" / "career.db"),
    )

    assert record.application_id == application_id
