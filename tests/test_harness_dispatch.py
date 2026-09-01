import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from career.services.harness_supervisor import HarnessSupervisor
from career.services.maintenance_orchestrator import MaintenanceOrchestrator

from tests.test_canonical_maintenance import make_git_fixture


def _maintenance_payload(**overrides):
    payload = {
        "kind": "canonical_maintenance",
        "requester_profile": "vagas_bot_01",
        "objective": "corrigir leitor canonico",
        "allowed_paths": ["src/career/services/cv_content.py"],
        "roadmap_id": "MAINT-002",
        "spec": {
            "requirements": [
                {"id": "REQ-1", "text": "Encaminhar pedido ao orquestrador"}
            ]
        },
        "evidence": {"error": "falha reproduzida pelo bot"},
    }
    payload.update(overrides)
    return payload


class _ApprovedMaintenanceRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_attempt(self, request: dict[str, object], attempt_number: int) -> dict[str, object]:
        patch_path = self.root.parent / f"candidate-{attempt_number}.patch"
        patch_text = (
            "--- a/src/career/services/cv_content.py\n"
            "+++ b/src/career/services/cv_content.py\n"
            "@@ -1 +1 @@\n"
            "-BASE\n"
            "+CHANGED\n"
        )
        patch_path.write_text(patch_text, encoding="utf-8")
        checks = {
            "status": "passed",
            "commands": [
                {"name": name, "returncode": 0}
                for name in [
                    "git_diff_check",
                    "base_commit",
                    "changed_paths",
                    "candidate_diff",
                    "required_pytest",
                ]
            ],
            "changed_files": ["src/career/services/cv_content.py"],
        }
        review = {
            "status": "approved",
            "score": 99.0,
            "requirements": [
                {"id": "REQ-1", "status": "met", "evidence": "offline canary"}
            ],
            "blockers": [],
            "warnings": [],
            "reviewer_model": "maintenance-reviewer",
            "diff_sha256": hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
            "spec_sha256": hashlib.sha256(
                json.dumps(
                    request["spec"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        }
        return {
            "status": "approved",
            "candidate": {
                "patch_path": str(patch_path),
                "changed_files": ["src/career/services/cv_content.py"],
            },
            "checks": checks,
            "review": review,
        }

    def post_apply_checks(
        self, request: dict[str, object], patch_path: Path
    ) -> dict[str, object]:
        assert patch_path.is_file()
        return self.run_attempt(request, 1)["checks"]


def _maintenance_root(tmp_path):
    return make_git_fixture(
        tmp_path,
        files={"src/career/services/cv_content.py": "BASE\n"},
    )


@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_bot_maintenance_request_is_not_classified_as_pasted_job(profile):
    decision = HarnessSupervisor().classify(
        json.dumps(_maintenance_payload(requester_profile=profile))
    )

    assert decision.workflow == "maintenance"
    assert decision.requires_approval is False


def test_maintenance_prose_is_not_classified_as_maintenance():
    decision = HarnessSupervisor().classify(
        "manutencao canonica solicitada pelo bot para corrigir src/career/services/cv_content.py"
    )

    assert decision.workflow != "maintenance"


def test_maintenance_request_requires_canonical_application_scope_when_cellular(
    tmp_path, monkeypatch
):
    class ExplodingOrchestrator:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("cellular scope must block before orchestrator")

    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        ExplodingOrchestrator,
        raising=False,
    )
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(_maintenance_payload(cellular=True)),
        execute=True,
    )

    assert result["status"] == "blocked"
    assert result["result"]["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "explicit_application_scope_required"


def test_maintenance_request_execute_false_prepares_and_validates(tmp_path):
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(_maintenance_payload()),
        execute=False,
    )

    assert result["status"] == "prepared"
    assert result["executed"] is False
    assert result["decision"]["workflow"] == "maintenance"
    assert result["result"]["status"] == "prepared"
    assert result["result"]["validation"]["status"] == "ok"
    assert result["result"]["request"]["requester_profile"] == "vagas_bot_01"


@pytest.mark.parametrize("status", ["blocked", "rejected", "committed"])
def test_maintenance_request_execute_true_preserves_orchestrator_status(
    tmp_path, monkeypatch, status
):
    captured = {}

    class FakeOrchestrator:
        def __init__(self, root):
            captured["root"] = root

        def process(self, request_path):
            captured["request_path"] = request_path
            request = json.loads(request_path.read_text(encoding="utf-8"))
            captured["request"] = request
            return {
                "status": status,
                "request_id": request["request_id"],
                "attempts": 1,
                "blocker_reason": "reviewer_rejected" if status != "committed" else None,
            }

    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        FakeOrchestrator,
        raising=False,
    )
    supervisor = HarnessSupervisor(_maintenance_root(tmp_path))

    result = supervisor.handle_message(
        json.dumps(
            _maintenance_payload(
                cellular=True,
                application_id="app_demo",
                run_id="run_demo",
            )
        ),
        execute=True,
    )

    assert result["status"] == status
    assert result["result"]["status"] == status
    assert result["result"]["application_id"] == "app_demo"
    assert captured["request"]["run_id"] == "run_demo"


@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_structured_profile_request_commits_in_disposable_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    production_target = Path(__file__).resolve().parents[1] / "src/career/services/cv_content.py"
    production_before = production_target.read_bytes()
    root = _maintenance_root(tmp_path / "checkout")
    base_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    payload = _maintenance_payload(
        requester_profile=profile,
        application_id="app_disposable",
        run_id="run_disposable",
        base_commit=base_commit,
    )
    orchestrator = MaintenanceOrchestrator(root, runner=_ApprovedMaintenanceRunner(root))
    monkeypatch.setattr(
        orchestrator,
        "reload_profiles_if_needed",
        lambda changed_paths: {
            "status": "not_required",
            "policy": {"runtime_affecting": False, "changed_paths": changed_paths},
            "command": None,
            "docker_compose_ps": "",
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "resume_original_run",
        lambda request: {
            "status": "resumed",
            "command": [
                "npm",
                "run",
                "applications:run",
                "--",
                "--application-id",
                request["application_id"],
                "--run-id",
                request["run_id"],
                "--run-agent",
            ],
            "returncode": 0,
            "stdout": "resumed\n",
            "stderr": "",
        },
    )
    monkeypatch.setattr(
        "career.services.harness_supervisor.MaintenanceOrchestrator",
        lambda candidate_root: orchestrator,
    )

    result = HarnessSupervisor(root).handle_message(
        json.dumps(payload),
        execute=True,
    )

    assert result["status"] == "committed"
    assert result["executed"] is True
    assert result["result"]["request"]["requester_profile"] == profile
    assert result["result"]["review"]["score"] >= 99.0
    assert result["result"]["reload"]["status"] == "not_required"
    assert result["result"]["resume"]["status"] == "resumed"
    receipt_path = Path(str(result["result"]["receipt_path"]))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "committed"
    assert receipt["requester_profile"] == profile
    assert receipt["commit"] == result["result"]["commit"]
    assert receipt["review"]["score"] >= 99.0
    assert receipt["reload"]["status"] == "not_required"
    assert receipt["resume"]["status"] == "resumed"
    assert production_target.read_bytes() == production_before
    committed_paths = subprocess.run(
        ["git", "-C", str(root), "show", "--format=", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert committed_paths == ["src/career/services/cv_content.py"]


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


def test_harness_result_report_is_not_classified_as_a_pasted_job():
    message = """
    Resumo do resultado (executado pelo HarnessSupervisor)
    Status: blocked — a mensagem não foi executada (executed: false).
    O supervisor classificou errado a sua mensagem como vaga colada.
    Workflow: pasted_job_missing_metadata. Stage: intake. Confidence: high.
    O bloqueio objetivo está relacionado ao CV e ao fit_map, não a uma nova vaga.
    O próximo passo é confirmar o estado de applications_v2.py e preparar o patch.
    Quer que eu confirme o estado atual e corrija os sinais em inglês?
    """ + (" Contexto operacional do resultado. " * 30)

    decision = HarnessSupervisor().classify(message)

    assert decision.workflow == "generic_assistant"
    assert decision.reason == "harness_result_report"


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


def test_explicit_cellular_resume_exposes_permission_preflight_blocker(monkeypatch):
    supervisor = HarnessSupervisor()
    supervisor.db.fetch_one = lambda *_args: {"application_id": "app_modaxo"}

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=(
                '{"status":"blocked","error":"cellular workspace preflight '
                'cannot read identity.json (owner=0:0 mode=600)"}'
            ),
            stderr="",
        )

    monkeypatch.setattr("career.services.harness_supervisor.subprocess.run", fake_run)

    result = supervisor._resume_cellular_run(
        application_id="app_modaxo",
        run_id="run_modaxo",
        repair_node=None,
        reason="retomar o mesmo run",
    )

    assert result["status"] == "blocked"
    assert result["blocker_reason"] == "cellular_workspace_permission"
    assert "UID 10000" in result["next_action"]
