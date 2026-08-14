from __future__ import annotations

import json

from career.services import intake


def test_saved_job_metadata_hints_resolve_selected_url(monkeypatch, tmp_path):
    saved_jobs = tmp_path / "inbox" / "linkedin_saved_jobs.json"
    saved_jobs.parent.mkdir(parents=True)
    saved_jobs.write_text(
        json.dumps(
            {
                "extractedAt": "2026-08-14T13:46:50Z",
                "jobs": [
                    {
                        "jobId": "4453385301",
                        "title": "Gerente de Desenvolvimento de Negócios- Growth",
                        "company": "iFood",
                        "location": "Brasil (Remoto)",
                        "url": "https://www.linkedin.com/jobs/view/4453385301/",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(intake, "INBOX", saved_jobs.parent)

    assert intake._saved_job_metadata_hints_for_url(
        "https://www.linkedin.com/jobs/view/4453385301/?trk=public_jobs"
    ) == {
        "company": "iFood",
        "role": "Gerente de Desenvolvimento de Negócios- Growth",
        "location": "Brasil (Remoto)",
    }


def test_saved_job_metadata_hints_ignore_unmatched_or_invalid_cache(monkeypatch, tmp_path):
    saved_jobs = tmp_path / "inbox" / "linkedin_saved_jobs.json"
    saved_jobs.parent.mkdir(parents=True)
    saved_jobs.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(intake, "INBOX", saved_jobs.parent)

    assert intake._saved_job_metadata_hints_for_url(
        "https://www.linkedin.com/jobs/view/4453385301/"
    ) == {}
