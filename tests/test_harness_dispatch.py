from types import SimpleNamespace

from career.services.harness_supervisor import HarnessSupervisor


def test_cv_onedrive_notion_is_one_scoped_pipeline():
    decision = HarnessSupervisor().classify(
        "crie o cv, envie para o onedrive e crie o registro no notion "
        "application_id local_test"
    )

    assert decision.workflow == "pipeline"
    assert decision.parameters["application_id"] == "local_test"
    assert decision.parameters["requested_steps"] == ["cv", "onedrive", "notion"]


def test_application_id_prevents_collecting_notion_id():
    decision = HarnessSupervisor().classify(
        "retome application_id local_test e prossiga com CV, OneDrive e Notion"
    )

    assert decision.workflow == "pipeline"
    assert decision.workflow != "collect_notion_id"


def test_explicit_run_resume_precedes_long_pasted_job_detection():
    message = """
    Retome a candidatura existente no mesmo run. Não faça novo intake nem nova análise.
    application_id: local_20260827T151213_541737_modaxo_8959c053
    run_id: run_62621fc435554290be1fbe127968c29b
    Repare compose_cv, depois render_cv e review_cv.
    """ + (" Contexto operacional da candidatura. " * 30)

    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "resume"
    assert decision.stage == "resume"
    assert decision.parameters == {
        "application_id": "local_20260827T151213_541737_modaxo_8959c053",
        "run_id": "run_62621fc435554290be1fbe127968c29b",
        "repair_node": "compose_cv",
    }


def test_explicit_run_resume_extracts_natural_language_repair_node():
    supervisor = HarnessSupervisor.__new__(HarnessSupervisor)

    decision = supervisor.classify(
        "Repare primeiro o normalize_job e depois prossiga no mesmo run. "
        "application_id: app_modaxo run_id: run_123"
    )

    assert decision.workflow == "resume"
    assert decision.parameters["repair_node"] == "normalize_job"


def test_explicit_cellular_resume_runs_scoped_official_repair_command(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout='{"status":"completed"}', stderr="")

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node="compose_cv",
        reason="corrigir o conteúdo do CV no mesmo run",
    )

    assert result["status"] == "completed"
    assert captured["command"][:8] == [
        "npm", "run", "applications:repair", "--",
        "--application-id", "app_modaxo", "--run-id", "run_modaxo",
    ]
    assert "--node" in captured["command"]


def test_explicit_cellular_resume_runs_agent_nodes_for_plain_run(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout='{"status":"ready"}', stderr="")

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node=None,
        reason="retomar o mesmo run",
    )

    assert result["status"] == "completed"
    assert captured["command"][-1] == "--run-agent"
