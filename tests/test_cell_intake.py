from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career.cells import handlers as cell_handlers
from career.cells.executor import CellExecutor
from career.services import derived_context, intake
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import read_json, write_json


def _job_text(company: str, role: str, focus: str) -> str:
    body = "\n".join(
        [
            f"# {role}",
            f"Empresa: {company}",
            "## Descricao da vaga",
            f"A pessoa liderara {focus} com governanca, dados e melhoria continua.",
            "Responsabilidades",
            f"- Construir o plano de {focus} e acompanhar indicadores operacionais.",
            "- Coordenar times multifuncionais e comunicar riscos executivos.",
            "Requisitos",
            "- Experiencia em operacoes, planejamento e analise de dados.",
            "- Lideranca de equipes e capacidade de execucao transversal.",
        ]
    )
    return body + "\n" + (f"Contexto adicional de {company}. " * 20)


def _seed_identity(paths, *, company: str, role: str) -> None:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": paths.application_id,
            "source_type": "pasted_text",
            "source_id": f"source-{paths.application_id}",
            "company": company,
            "role": role,
        },
    )


def test_capture_source_persists_description_and_source_metadata(tmp_path):
    paths = paths_for("capture-app", root=tmp_path / "applications")
    _seed_identity(paths, company="Acme", role="Head de Operacoes")
    source = _job_text("Acme", "Head de Operacoes", "operacoes nacionais")

    captured = intake.capture_source(
        paths,
        source_text=source,
        source_metadata={"source_type": "pasted_text", "source_id": "paste-1"},
    )

    assert paths.job_description.read_text(encoding="utf-8") == source
    assert read_json(paths.source_metadata) == {
        "application_id": "capture-app",
        "job_description_path": str(paths.job_description),
        "job_fingerprint": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "source_id": "paste-1",
        "source_type": "pasted_text",
    }
    assert captured["job_fingerprint"] == read_json(paths.source_metadata)[
        "job_fingerprint"
    ]


def test_production_capture_handler_publishes_immutable_source_and_handover(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("capture-cell", root=applications_root)
    _seed_identity(paths, company="Acme", role="Head de Operacoes")
    source = _job_text("Acme", "Head de Operacoes", "operacoes nacionais")
    (paths.app_dir / "source_input.md").write_text(source, encoding="utf-8")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        plan = executor.plan(paths.application_id, {"cv"})
        result = executor.run_ready(plan.run_id)

        assert [(item.node_id, item.status) for item in result] == [
            ("capture_source", "validated")
        ]
        assert paths.job_description.read_text(encoding="utf-8") == source
        attempt = read_json(result[0].manifest_path)
        published = attempt["outputs"][0]
        assert Path(published["path"]).read_text(encoding="utf-8") == source
        handover = read_json(result[0].manifest_path.parent / "handover_summary.json")
        assert handover["application_id"] == paths.application_id
        assert handover["job_fingerprint"] == hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()
    finally:
        database.close()


def test_changed_source_invalidates_only_its_application_descendants(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    first = paths_for("source-repair-a", root=applications_root)
    second = paths_for("source-repair-b", root=applications_root)
    for paths, company, focus in (
        (first, "Acme", "alpha"),
        (second, "Beta", "beta"),
    ):
        _seed_identity(paths, company=company, role="Operations Lead")
        (paths.app_dir / "source_input.md").write_text(
            _job_text(company, "Operations Lead", focus), encoding="utf-8"
        )
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        first_plan = executor.plan(first.application_id, {"cv", "feras"})
        second_plan = executor.plan(second.application_id, {"cv", "feras"})
        for plan in (first_plan, second_plan):
            assert executor.run_ready(plan.run_id)[0].node_id == "capture_source"
            assert executor.run_ready(plan.run_id)[0].node_id == "normalize_job"
            for node_id in ("analyze_fit", "compose_cv", "generate_feras"):
                executor.mark_validated(plan.run_id, node_id)
        second_description = second.job_description.read_bytes()

        changed_source = _job_text("Acme", "Operations Lead", "alpha revisado")
        (first.app_dir / "source_input.md").write_text(
            changed_source, encoding="utf-8"
        )
        repaired = executor.repair(
            first_plan.run_id, "capture_source", "source description changed"
        )

        assert {
            node_id: executor.node_status(first_plan.run_id, node_id)
            for node_id in ("normalize_job", "analyze_fit", "compose_cv", "generate_feras")
        } == {
            "normalize_job": "superseded",
            "analyze_fit": "superseded",
            "compose_cv": "superseded",
            "generate_feras": "superseded",
        }
        assert {
            node_id: executor.node_status(second_plan.run_id, node_id)
            for node_id in ("normalize_job", "analyze_fit", "compose_cv", "generate_feras")
        } == {
            "normalize_job": "validated",
            "analyze_fit": "validated",
            "compose_cv": "validated",
            "generate_feras": "validated",
        }
        assert "normalize_job" in repaired.invalidated
        capture_result = next(
            item
            for item in executor.run_ready(first_plan.run_id)
            if item.node_id == "capture_source"
        )
        assert capture_result.status == "validated"
        assert first.job_description.read_text(encoding="utf-8") == changed_source
        assert second.job_description.read_bytes() == second_description
    finally:
        database.close()


def test_normalization_keeps_fingerprints_and_packs_per_application(
    tmp_path, monkeypatch
):
    first = paths_for("normalize-app-a", root=tmp_path / "applications")
    second = paths_for("normalize-app-b", root=tmp_path / "applications")
    for paths, company, role, focus in (
        (first, "Acme", "Head de Operacoes", "operacoes nacionais"),
        (second, "Beta", "Diretor de Planejamento", "S&OP regional"),
    ):
        _seed_identity(paths, company=company, role=role)
        paths.job_description.write_text(
            _job_text(company, role, focus), encoding="utf-8"
        )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("cellular normalization must not configure global paths")

    monkeypatch.setattr(derived_context, "configure_derived_dir", forbidden)
    monkeypatch.setattr(derived_context, "configure_state_store_path", forbidden)

    first_result = derived_context.normalize_job(first)
    second_result = derived_context.normalize_job(second)

    first_manifest = read_json(first.derived_dir / "manifest.json")
    second_manifest = read_json(second.derived_dir / "manifest.json")
    assert first_manifest["fingerprint"] != second_manifest["fingerprint"]
    assert first_manifest["application_id"] == first.application_id
    assert second_manifest["application_id"] == second.application_id
    assert first_manifest["candidate_facts_revision"] == second_manifest[
        "candidate_facts_revision"
    ]
    assert first_result["handover"]["job_fingerprint"] == first_manifest[
        "fingerprint"
    ]
    assert second_result["handover"]["job_fingerprint"] == second_manifest[
        "fingerprint"
    ]

    required_packs = {
        "active_context",
        "job_extract",
        "job_sections",
        "job_requirements",
        "job_responsibilities",
        "job_company_context",
        "job_keywords",
        "reference_digest",
        "candidate_evidence_pack",
        "candidate_evidence_by_theme",
        "fit_map_seed",
        "job_normalized",
        "handover_summary",
        "evidence_index",
    }
    assert required_packs <= set(first_manifest["outputs"])
    assert required_packs <= set(second_manifest["outputs"])
    assert all(
        (first.derived_dir / f"{name}.json").is_file() for name in required_packs
    )
    assert all(
        (second.derived_dir / f"{name}.json").is_file() for name in required_packs
    )


def test_normalization_rejects_a_job_path_from_another_application(tmp_path):
    first = paths_for("path-app-a", root=tmp_path / "applications")
    second = paths_for("path-app-b", root=tmp_path / "applications")
    for paths, company in ((first, "Acme"), (second, "Beta")):
        _seed_identity(paths, company=company, role="Operations Lead")
        paths.job_description.write_text(
            _job_text(company, "Operations Lead", "delivery"), encoding="utf-8"
        )

    try:
        derived_context.normalize_job(
            first, job_description_path=second.job_description
        )
    except ValueError as exc:
        assert "application" in str(exc).casefold()
    else:  # pragma: no cover - makes the negative contract explicit
        raise AssertionError("cross-application job paths must be rejected")
