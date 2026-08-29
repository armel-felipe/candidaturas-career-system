from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor


def _insert_application(database, application_id, company, role):
    database.execute(
        """INSERT INTO applications
           (id, company, role, created_at, updated_at, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (application_id, company, role, "2026-08-25", "2026-08-25", "active"),
    )


def test_bot02_canary_keeps_composite_and_confirmation_scoped(tmp_path):
    database = Database(tmp_path / "control-plane" / "career.db")
    database.init_schema()
    _insert_application(database, "app_ca", "C&A Brasil", "Gerente de Logistica")
    _insert_application(database, "app_jobgether", "Jobgether", "Director, PMO")
    database.execute(
        """INSERT INTO deliveries
           (delivery_id, application_id, artifact_version_id, channel, status, delivered_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("delivery_jobgether", "app_jobgether", None, "onedrive", "delivered", "2026-08-20"),
    )
    database.close()

    supervisor = HarnessSupervisor(tmp_path)
    session = {
        "runtime": "hermes",
        "profile_id": "canary-profile",
        "session_id": "canary-session",
    }
    composite = supervisor.handle_message(
        "crie o cv, envie para o onedrive e crie o registro no notion application_id app_ca",
        channel="telegram",
        execute=False,
        runtime_context=session,
    )
    assert composite["decision"]["workflow"] == "pipeline"
    assert composite["decision"]["parameters"]["application_id"] == "app_ca"

    supervisor._write_pending_input(
        {
            "input_kind": "confirmation",
            "session_id": "canary-session",
            "application_id": "app_ca",
            "turn_id": "canary-turn",
            "display_text": "Gerar o CV?",
        }
    )
    confirmation = supervisor.handle_message(
        "sim",
        channel="telegram",
        execute=True,
        runtime_context=session,
    )
    assert confirmation["result"] == {
        "status": "completed",
        "kind": "confirmation",
        "answer": True,
        "application_id": "app_ca",
        "turn_id": "canary-turn",
    }

    status = supervisor.handle_message(
        "vc entregou cv para essa vaga no onedrive? application_id app_ca",
        channel="telegram",
        execute=True,
    )
    assert status["result"]["blocker_reason"] == "delivery_receipt_missing"
    assert "Jobgether" not in str(status)
