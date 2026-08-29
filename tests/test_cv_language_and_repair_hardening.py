from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from career.services import applications_v2, cv_content, derived_context
from career.services.application_context import paths_for


def test_job_language_detector_is_shared_for_mixed_language_job_text():
    text = """
    # AI Transformation Manager
    Empresa: Modaxo
    Localização: Brasil (Remoto)

    ## Descrição da vaga
    Sobre a vaga

    Job Summary
    You will be a hands-on partner to our Business Units.
    Job Description
    We're looking for a confident AI practitioner.
    Responsibilities
    Identify AI use cases and build lasting capability.
    """

    assert applications_v2.detect_job_language(text) == "en"
    assert derived_context._infer_language(text) == "en"


def test_cell_compose_uses_the_validated_normalized_language_input(tmp_path, monkeypatch):
    from career.cells.capabilities import CapabilitySet
    from career.cells.handlers import _compose_cv

    app_dir = tmp_path / "application"
    app_dir.mkdir()
    fit_map_path = app_dir / "fit_map.json"
    normalized_path = app_dir / "job_normalized.json"
    fit_map_path.write_text(
        json.dumps({"provenance": {"candidate_facts_revision": "facts-v1"}}),
        encoding="utf-8",
    )
    normalized_path.write_text(
        json.dumps({"job_identity": {"language": "en"}}), encoding="utf-8"
    )

    def record(path):
        return {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "application_id": "app-1",
        }

    context = SimpleNamespace(
        application_id="app-1",
        run_id="run-1",
        attempt=1,
        inputs={
            "analyze_fit:fit_map.json": record(fit_map_path),
            "normalize_job:job_normalized.json": record(normalized_path),
        },
        capabilities=CapabilitySet(
            application_root=app_dir,
            read_paths=[app_dir],
            write_paths=[app_dir],
        ),
        paths=SimpleNamespace(),
    )
    captured = {}

    def fake_build(paths, fit_path, candidate_revision, *, language=None):
        captured["language"] = language
        return {"metadata": {"language": language}}

    monkeypatch.setattr(cv_content, "build_cv_content", fake_build)

    _compose_cv(context)

    assert captured["language"] == "en"


def test_ats_coverage_does_not_call_unmaterialized_keyword_exact():
    selected = [
        {
            "id": "operations-lead",
            "company": "Acme",
            "role": "Operations Lead",
            "bullets": ["Led operations and data routines."],
        }
    ]
    top8 = [
        {
            "keyword": "AI Transformation",
            "experiencia_alvo": "Acme — Operations Lead",
            "prioridade": 1,
        }
    ]

    coverage = cv_content._build_ats_coverage(selected, top8)

    assert coverage[0]["coverage_mode"] == "missing_unexplained"


def test_ats_coverage_preserves_an_explicit_fit_map_gap():
    selected = [
        {
            "id": "operations-lead",
            "company": "Acme",
            "role": "Operations Lead",
            "bullets": ["Led operations and data routines."],
        }
    ]
    top8 = [
        {
            "keyword": "AI Transformation",
            "experiencia_alvo": "Acme — Operations Lead",
            "prioridade": 1,
        }
    ]

    coverage = cv_content._build_ats_coverage(
        selected,
        top8,
        declared_gap_keywords=["AI Transformation"],
    )

    assert coverage[0]["coverage_mode"] == "declared_gap"


def test_ats_coverage_resolves_project_targets_and_prefers_supported_story():
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    selected = [
        cv_content._materialize_experience(
            next(item for item in facts if item["id"] == experience_id),
            "operations",
            ats_keywords=[
                {
                    "keyword": "OTIF",
                    "experiencia_alvo": "Trifil — Projeto Entrega Certa",
                    "prioridade": 1,
                }
            ],
        )
        for experience_id in ("ifood_diretor_operacoes", "trifil_sop")
    ]

    coverage = cv_content._build_ats_coverage(
        selected,
        [
            {
                "keyword": "OTIF",
                "experiencia_alvo": "Trifil — Projeto Entrega Certa",
                "prioridade": 1,
            }
        ],
    )

    assert coverage[0]["experience_id"] == "trifil_sop"
    assert coverage[0]["coverage_mode"] == "exact"


def test_ats_materialization_deduplicates_overlapping_last_mile_clauses():
    entry = next(
        item
        for item in cv_content.load_canonical_cv_facts()["experiences"]
        if item["id"] == "ifood_diretor_operacoes"
    )
    materialized = cv_content._materialize_experience(
        entry,
        "operations",
        ats_keywords=[
            {
                "keyword": "Logística de última milha",
                "experiencia_alvo": "iFood — Diretor de Operações",
                "prioridade": 1,
            },
            {
                "keyword": "Last mile",
                "experiencia_alvo": "iFood — Diretor de Operações",
                "prioridade": 2,
            },
        ],
    )

    bullet = materialized["bullets"][1]
    assert bullet.count("logística de última milha") == 1
    assert bullet.count("last mile") == 1


def test_ats_materialization_keeps_alternative_story_claims_on_their_source_role():
    facts = {
        item["id"]: item for item in cv_content.load_canonical_cv_facts()["experiences"]
    }
    keywords = [
        {
            "keyword": "Gestão de P&L",
            "experiencia_alvo": "iFood — Head/Diretor de Operações / wehandle — Head de Operações",
            "prioridade": 1,
        },
        {
            "keyword": "Desenvolvimento de lideranças",
            "experiencia_alvo": "VivaReal — Gerente / iFood — Head/Diretor de Operações",
            "prioridade": 2,
        },
        {
            "keyword": "Excelência operacional",
            "experiencia_alvo": "Trifil — Projeto Entrega Certa / wehandle — Head de Operações",
            "prioridade": 3,
        },
    ]

    rendered = {
        experience_id: cv_content._materialize_experience(
            facts[experience_id], "operations", ats_keywords=keywords
        )
        for experience_id in (
            "wehandle_head_operacoes",
            "ifood_diretor_operacoes",
            "vivareal_planejamento_operacoes",
            "trifil_sop",
        )
    }

    rendered_text = {
        key: " ".join(value["bullets"]).casefold()
        for key, value in rendered.items()
    }
    assert "gestão de p&l" not in rendered_text["wehandle_head_operacoes"]
    assert "gestão de p&l" in rendered_text["ifood_diretor_operacoes"]
    assert "desenvolvimento de lideranças" not in rendered_text["ifood_diretor_operacoes"]
    assert "desenvolvimento de lideranças" in rendered_text["vivareal_planejamento_operacoes"]
    assert "excelência operacional" in rendered_text["trifil_sop"]
    assert "excelência operacional" not in rendered_text["wehandle_head_operacoes"]


def test_daki_picking_clause_stays_on_trifil_expedicao():
    facts = {
        item["id"]: item for item in cv_content.load_canonical_cv_facts()["experiences"]
    }
    keywords = [
        {
            "keyword": "Produtividade de Picking",
            "experiencia_alvo": "Trifil — Coordenador de Expedição",
            "prioridade": 1,
        }
    ]
    rendered = {
        experience_id: cv_content._materialize_experience(
            facts[experience_id], "operations", ats_keywords=keywords
        )
        for experience_id in ("trifil_expedicao", "trifil_sop")
    }
    assert "produtividade de picking" in " ".join(rendered["trifil_expedicao"]["bullets"]).casefold()
    assert "produtividade de picking" not in " ".join(rendered["trifil_sop"]["bullets"]).casefold()


def test_new_canonical_ats_clauses_have_experience_scopes():
    facts = {
        item["id"]: item for item in cv_content.load_canonical_cv_facts()["experiences"]
    }
    scoped_keywords = {
        "Governança Operacional": "iFood — Diretor de Operações",
        "Liderança Interfuncional": "iFood — Diretor de Operações",
        "Automação de Processos": "iFood — Head/Diretor de Operações / wehandle — Head de Operações",
        "Escalabilidade Operacional": "iFood — Diretor de Operações",
        "Otimização de Processos": "Trifil — Projeto Entrega Certa / wehandle — Head de Operações",
    }
    expected_owner = {
        "Governança Operacional": "ifood_diretor_operacoes",
        "Liderança Interfuncional": "ifood_diretor_operacoes",
        "Automação de Processos": "wehandle_head_operacoes",
        "Escalabilidade Operacional": "ifood_diretor_operacoes",
        "Otimização de Processos": "wehandle_head_operacoes",
    }
    for keyword, target in scoped_keywords.items():
        owner = expected_owner[keyword]
        for experience_id, entry in facts.items():
            materialized = cv_content._materialize_experience(
                entry,
                "operations",
                ats_keywords=[
                    {"keyword": keyword, "experiencia_alvo": target, "prioridade": 1}
                ],
            )
            text = " ".join(materialized["bullets"]).casefold()
            if experience_id == owner:
                assert cv_content._normalize(keyword) in cv_content._normalize(text)
            else:
                assert cv_content._normalize(keyword) not in cv_content._normalize(text)


def test_daki_legacy_targets_fall_back_to_canonical_evidence_owner():
    """A broad/legacy FIT_MAP target must not suppress an authorized clause."""
    facts = {
        item["id"]: item for item in cv_content.load_canonical_cv_facts()["experiences"]
    }
    keywords = [
        {
            "keyword": "Excelência Operacional",
            "experiencia_alvo": "Trifil — Analista",
            "prioridade": 1,
        },
        {
            "keyword": "Produtividade de Picking",
            "experiencia_alvo": "iFood — Diretor de Operações",
            "prioridade": 2,
        },
    ]

    rendered = {
        experience_id: cv_content._materialize_experience(
            facts[experience_id], "operations", ats_keywords=keywords
        )
        for experience_id in ("trifil_sop", "trifil_expedicao", "ifood_diretor_operacoes")
    }
    sop_text = " ".join(rendered["trifil_sop"]["bullets"])
    expedition_text = " ".join(rendered["trifil_expedicao"]["bullets"])
    ifood_text = " ".join(rendered["ifood_diretor_operacoes"]["bullets"])

    assert "excelência operacional" in sop_text.casefold()
    assert "produtividade de picking" in expedition_text.casefold()
    assert "excelência operacional" not in ifood_text.casefold()
    assert "produtividade de picking" not in ifood_text.casefold()


def test_project_target_resolves_only_the_project_owner_role():
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    target = "Trifil — Projeto Entrega Certa"
    matches = {
        item["id"]
        for item in facts
        if cv_content._experience_matches_target(item, target)
    }
    assert matches == {"trifil_sop"}


def test_summary_never_interpolates_vacancy_dor_central():
    facts = cv_content.load_canonical_cv_facts()["experiences"]
    selected = [
        cv_content._materialize_experience(item, "operations")
        for item in facts[:5]
    ]
    vacancy_problem = "PROBLEMA EXCLUSIVO DA VAGA MODAXO"

    summary, _support = cv_content._build_summary(
        selected,
        {
            "cargo": "AI Transformation Manager",
            "dor_central": vacancy_problem,
        },
        positioning={"caso": "conectar operação e transformação"},
    )

    assert vacancy_problem not in summary


def test_repair_and_run_does_not_leave_reserved_attempt_on_failure(tmp_path):
    from career.cells.executor import CellExecutor
    from career.services.database import Database

    database = Database(tmp_path / "career.db")
    database.init_schema()
    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={},
        validators={},
    )
    try:
        plan = executor.plan("repair-app", {"cv"})
        executor.fail(plan.run_id, "capture_source", "initial failure")

        repaired, _results = executor.repair_and_run(
            plan.run_id, "capture_source", "retry failure"
        )

        row = database.fetch_one(
            "SELECT status, reserved_by, reservation_expires_at "
            "FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (plan.run_id, "capture_source"),
        )
        assert row["status"] == "blocked"
        assert row["reserved_by"] is None
        assert row["reservation_expires_at"] is None
        assert cv_content.read_json(repaired.manifest_path)["status"] == "blocked"
    finally:
        database.close()


def test_fit_map_repair_defers_until_external_draft_binding_exists(tmp_path):
    from career.cells.executor import CellExecutor
    from career.services.database import Database

    database = Database(tmp_path / "career.db")
    database.init_schema()
    executor = CellExecutor(
        database,
        applications_root=tmp_path / "applications",
        handlers={},
        validators={},
    )
    try:
        plan = executor.plan("repair-fit-map-app", {"cv"})
        executor.mark_validated(plan.run_id, "normalize_job")
        prepared = executor.prepare_ready_node(plan.run_id, "analyze_fit")
        executor.defer_prepared_attempt(prepared, reason="seed prior attempt")
        executor.fail(plan.run_id, "analyze_fit", "draft binding invalid")

        executor.repair_and_run(plan.run_id, "analyze_fit", "retry after agent repair")

        row = database.fetch_one(
            "SELECT status, reserved_by, reservation_expires_at "
            "FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (plan.run_id, "analyze_fit"),
        )
        assert row["status"] == "planned"
        assert row["reserved_by"] is None
        assert row["reservation_expires_at"] is None
    finally:
        database.close()


def test_fit_map_repair_never_executes_stale_draft_binding(tmp_path):
    from career.cells.executor import CellExecutor
    from career.services.database import Database

    database = Database(tmp_path / "career.db")
    database.init_schema()
    root = tmp_path / "applications"
    executor = CellExecutor(
        database,
        applications_root=root,
        handlers={},
        validators={},
    )
    try:
        application_id = "repair-fit-map-stale-binding-app"
        plan = executor.plan(application_id, {"cv"})
        executor.mark_validated(plan.run_id, "normalize_job")
        paths = paths_for(application_id, root=root)
        paths.app_dir.mkdir(parents=True, exist_ok=True)
        paths.fit_map_draft.write_text('{"draft": true}', encoding="utf-8")
        prepared = executor.prepare_ready_node(plan.run_id, "analyze_fit")
        binding = {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": application_id,
            "run_id": plan.run_id,
            "node_id": "analyze_fit",
            "attempt": prepared.attempt,
            "job_fingerprint": "",
            "draft_sha256": applications_v2.sha256_file(paths.fit_map_draft),
            "manifest_path": str(prepared.manifest_path.resolve()),
        }
        (paths.app_dir / "fit_map.draft.binding.json").write_text(
            json.dumps(binding), encoding="utf-8"
        )
        executor.defer_prepared_attempt(prepared, reason="seed stale binding")

        executor.repair_and_run(
            plan.run_id,
            "analyze_fit",
            "retry must regenerate the externally-authored draft",
        )

        row = database.fetch_one(
            "SELECT status, reserved_by, reservation_expires_at "
            "FROM cell_nodes WHERE run_id = ? AND node_id = ?",
            (plan.run_id, "analyze_fit"),
        )
        assert row["status"] == "planned"
        assert row["reserved_by"] is None
        assert row["reservation_expires_at"] is None
    finally:
        database.close()
