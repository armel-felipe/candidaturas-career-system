import hashlib
import json

import pytest

from career.cells.capabilities import CapabilitySet
from career.cells.contracts import CELL_CONTRACTS
from career.cells.executor import CellExecutor
from career.cells.handlers import CellExecutionContext, production_handler_registry
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import ValidationFailure


def _branch_context(tmp_path, application_id, node_id, fit_map):
    paths = paths_for(application_id, root=tmp_path / "applications")
    staging = paths.cells_dir / node_id / "1" / "staging"
    staging.mkdir(parents=True)
    fit_path = paths.app_dir / "inputs" / "fit_map.json"
    fit_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(fit_map).encode("utf-8")
    fit_path.write_bytes(raw)
    inputs = {"analyze_fit:fit_map.json": {"path": str(fit_path), "sha256": hashlib.sha256(raw).hexdigest()}}
    for name, payload in {
        "normalize_job:job_normalized.json": {"application_id": application_id, "kind": "job_normalized"},
        "normalize_job:handover_summary.json": {"application_id": application_id, "job_fingerprint": "job-hash"},
        "normalize_job:evidence_index.json": {"application_id": application_id, "kind": "evidence_index"},
    }.items():
        path = paths.app_dir / "inputs" / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        inputs[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return CellExecutionContext(
        application_id=application_id,
        run_id="run-1",
        node_id=node_id,
        attempt=1,
        paths=paths,
        manifest_path=paths.cells_dir / node_id / "1" / "manifest.json",
        staging_dir=staging,
        inputs=inputs,
        output_paths=(),
        capabilities=CapabilitySet(application_root=paths.app_dir, read_paths=[paths.app_dir], write_paths=[staging]),
        repair_scope="test",
    )


def test_feras_can_complete_when_cv_is_blocked(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    orchestrator = CellExecutor(database, applications_root=tmp_path / "applications")
    try:
        paths_for("app-1", root=tmp_path / "applications").app_dir.mkdir(parents=True)
        paths_for("app-1", root=tmp_path / "applications").job_description.write_text("job", encoding="utf-8")
        run_id = orchestrator.plan("app-1", {"cv", "feras"}).run_id
        orchestrator.mark_validated(run_id, "normalize_job")
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
        {"cargo": "Diretor", "empresa": "Acme"},
    )
    context.inputs["analyze_fit:fit_map.json"]["application_id"] = "app-2"

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


def test_output_contracts_consume_normalized_and_fit_inputs_and_publish_evidence():
    assert CELL_CONTRACTS["deliver_cv"].requires == ("render_cv", "review_cv")
    for node_id in ("generate_feras", "generate_cover_letter", "generate_habilidades"):
        contract = CELL_CONTRACTS[node_id]
        assert contract.requires == ("normalize_job", "analyze_fit")
        assert {"handover_summary.json", "evidence_index.json"} <= {
            path.rsplit("/", 1)[-1] for path in contract.produces
        }


def test_feras_review_rejects_tampered_content_even_when_nonempty(tmp_path):
    paths = paths_for("app-1", root=tmp_path / "applications")
    staging = paths.cells_dir / "review_feras" / "1" / "staging"
    staging.mkdir(parents=True)
    artifact = paths.app_dir / "inputs" / "feras.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("nonempty but not a FERAS document", encoding="utf-8")
    context = CellExecutionContext(
        application_id="app-1", run_id="run-1", node_id="review_feras", attempt=1,
        paths=paths, manifest_path=staging.parent / "manifest.json", staging_dir=staging,
        inputs={"generate_feras:feras.md": {"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}},
        output_paths=(), capabilities=CapabilitySet(application_root=paths.app_dir, read_paths=[paths.app_dir], write_paths=[staging]), repair_scope="test",
    )

    with pytest.raises(ValidationFailure, match="feras"):
        production_handler_registry()["review_feras"](context)


def test_feras_review_rejects_a_tampered_artifact_hash_before_approval(tmp_path):
    paths = paths_for("app-1", root=tmp_path / "applications")
    staging = paths.cells_dir / "review_feras" / "1" / "staging"
    staging.mkdir(parents=True)
    artifact = paths.app_dir / "inputs" / "feras.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# FERAS", encoding="utf-8")
    context = CellExecutionContext(
        application_id="app-1", run_id="run-1", node_id="review_feras", attempt=1,
        paths=paths, manifest_path=staging.parent / "manifest.json", staging_dir=staging,
        inputs={"generate_feras:feras.md": {"path": str(artifact), "sha256": "0" * 64}},
        output_paths=(), capabilities=CapabilitySet(application_root=paths.app_dir, read_paths=[paths.app_dir], write_paths=[staging]), repair_scope="test",
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        production_handler_registry()["review_feras"](context)
