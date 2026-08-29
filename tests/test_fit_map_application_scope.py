from __future__ import annotations

from career.services import fit_map
from career.utils import write_json


def test_status_uses_registry_next_to_application_fit_map(monkeypatch, tmp_path):
    app_dir = tmp_path / ".career-state" / "applications_v2" / "app-scope"
    draft_path = app_dir / "fit_map.draft.json"
    fit_map_path = app_dir / "fit_map.json"
    job_path = app_dir / "job_description.md"
    registry_path = app_dir / "derived" / "keyword_ats_registry.json"
    write_json(draft_path, {})
    write_json(
        fit_map_path,
        {
            "cargo": "Head de Operações",
            "empresa": "Acme",
            "keywords_habilidade_ats": [{"keyword": "Governança Operacional"}],
        },
    )
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text("Acme Head de Operações", encoding="utf-8")
    write_json(
        registry_path,
        {
            "applications": [
                {
                    "application_key": "acme__head_de_opera_es",
                    "keyword_records": [{"canonical": "Governança Operacional"}],
                }
            ]
        },
    )
    monkeypatch.setattr(fit_map, "KEYWORD_REGISTRY", tmp_path / "global-missing.json")
    monkeypatch.setattr(fit_map, "CAREER_STATE", tmp_path / ".career-state")
    monkeypatch.setattr(fit_map, "_fit_map_state_fingerprint_match", lambda *_args: True)

    result = fit_map.status(
        draft_path=draft_path,
        fit_map_path=fit_map_path,
        job_description_path=job_path,
    )
    guidance = fit_map.resume_guidance(
        draft_path=draft_path,
        fit_map_path=fit_map_path,
        job_description_path=job_path,
    )
    guard = fit_map.progress_guard(
        draft_path=draft_path,
        fit_map_path=fit_map_path,
        job_description_path=job_path,
    )

    assert result["keyword_registration"]["registered"] is True
    assert result["keyword_registration"]["path"] == str(registry_path)
    assert guidance["status"]["keyword_registration"]["path"] == str(registry_path)
    assert guidance["status"]["keyword_registration"]["registered"] is True
    assert guard["status"]["keyword_registration"]["path"] == str(registry_path)
    assert guard["status"]["keyword_registration"]["registered"] is True
