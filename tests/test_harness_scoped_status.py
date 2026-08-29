from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor


def test_delivery_status_without_application_scope_is_blocked(tmp_path):
    result = HarnessSupervisor(tmp_path).handle_message(
        "vc entregou cv para essa vaga no onedrive?",
        channel="telegram",
        execute=True,
    )

    assert result["result"]["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "explicit_application_scope_required"


def test_delivery_status_with_scope_reads_only_that_application(tmp_path):
    database = Database(tmp_path / "control-plane" / "career.db")
    database.init_schema()
    database.execute(
        """INSERT INTO applications
           (id, company, role, created_at, updated_at, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("app_ca", "C&A Brasil", "Gerente de Logistica", "2026-08-25", "2026-08-25", "active"),
    )
    database.execute(
        """INSERT INTO applications
           (id, company, role, created_at, updated_at, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("app_jobgether", "Jobgether", "Director, PMO", "2026-08-20", "2026-08-20", "active"),
    )
    database.execute(
        """INSERT INTO deliveries
           (delivery_id, application_id, artifact_version_id, channel, status, delivered_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("delivery_jobgether", "app_jobgether", None, "onedrive", "delivered", "2026-08-20"),
    )
    database.close()

    supervisor = HarnessSupervisor(tmp_path)
    result = supervisor.handle_message(
        "vc entregou cv para essa vaga no onedrive? application_id app_ca",
        channel="telegram",
        execute=True,
    )

    assert result["decision"]["workflow"] == "application_status"
    assert result["result"]["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "delivery_receipt_missing"
