import hashlib
import json

import pytest

from career.cells.capabilities import CapabilitySet
from career.cells.executor import CellExecutor
from career.cells.handlers import CellExecutionContext, production_handler_registry
from career.services.application_context import paths_for
from career.services.database import Database


def _branch_context(tmp_path, application_id, node_id, fit_map):
    paths = paths_for(application_id, root=tmp_path / "applications")
    staging = paths.cells_dir / node_id / "1" / "staging"
    staging.mkdir(parents=True)
    fit_path = paths.app_dir / "inputs" / "fit_map.json"
    fit_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(fit_map).encode("utf-8")
    fit_path.write_bytes(raw)
    return CellExecutionContext(
        application_id=application_id,
        run_id="run-1",
        node_id=node_id,
        attempt=1,
        paths=paths,
        manifest_path=paths.cells_dir / node_id / "1" / "manifest.json",
        staging_dir=staging,
        inputs={"analyze_fit:fit_map.json": {"path": str(fit_path), "sha256": hashlib.sha256(raw).hexdigest()}},
        output_paths=(),
        capabilities=CapabilitySet(application_root=paths.app_dir, read_paths=[paths.app_dir], write_paths=[staging]),
        repair_scope="test",
    )


def test_feras_can_complete_when_cv_is_blocked(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    orchestrator = CellExecutor(database, applications_root=tmp_path / "applications")
    try:
        run_id = orchestrator.plan("app-1", {"cv", "feras"}).run_id
        orchestrator.mark_validated(run_id, "analyze_fit")
        orchestrator.fail(run_id, "compose_cv", "ats_blocker")

        assert "generate_feras" in orchestrator.ready_nodes(run_id)
    finally:
        database.close()


@pytest.mark.parametrize(
    ("node_id", "artifact_name"),
    [
        ("generate_feras", "feras.md"),
        ("generate_cover_letter", "cover_letter.md"),
        ("generate_habilidades", "habilidades.md"),
    ],
)
def test_output_branch_rejects_fit_map_pointer_from_another_application(tmp_path, node_id, artifact_name):
    context = _branch_context(
        tmp_path,
        "app-1",
        node_id,
        {"application_id": "app-2", "cargo": "Diretor", "empresa": "Acme"},
    )

    with pytest.raises(ValueError, match="another application"):
        production_handler_registry()[node_id](context)


def test_remaining_output_branches_publish_compact_identity_handovers(tmp_path):
    fit_map = {
        "application_id": "app-1",
        "cargo": "Diretor de Operações",
        "empresa": "Acme",
        "keywords_para_ats": ["operações", "dados", "planejamento"],
        "historias_selecionadas": {"principal": {"resultado": "reduziu custos em 13%"}},
    }
    handlers = production_handler_registry()
    for node_id, artifact_name in (
        ("generate_feras", "feras.md"),
        ("generate_cover_letter", "cover_letter.md"),
        ("generate_habilidades", "habilidades.md"),
    ):
        output = handlers[node_id](_branch_context(tmp_path, "app-1", node_id, fit_map))
        assert artifact_name in output.artifacts
        assert output.handover["application_id"] == "app-1"
        assert output.handover["run_id"] == "run-1"
        assert len(json.dumps(output.handover, sort_keys=True).encode("utf-8")) <= 2048
