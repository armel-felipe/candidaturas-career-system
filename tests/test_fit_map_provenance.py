from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from career.cells.executor import CellExecutor
from career.cells import handlers as cell_handlers
from career.services import derived_context, fit_map, provenance
from career.services.application_context import paths_for
from career.services.database import Database
from career.utils import ValidationFailure, read_json, write_json


def _job_text(company: str, role: str, focus: str) -> str:
    body = "\n".join(
        [
            f"# {role}",
            f"Empresa: {company}",
            "## Descricao da vaga",
            f"Buscamos lideranca para {focus} com dados e governanca.",
            "Responsabilidades",
            f"- Liderar {focus} e acompanhar indicadores de desempenho.",
            "- Coordenar stakeholders de produto, operacoes e tecnologia.",
            "Requisitos",
            "- Experiencia em planejamento operacional e lideranca.",
            "- Conhecimento de SQL, dashboards e melhoria continua.",
        ]
    )
    return body + "\n" + (f"Informacao complementar sobre {focus}. " * 20)


def _score_item(label: str) -> dict:
    return {
        "item": label,
        "tipo": "DIRETO",
        "evidencia": "Experiencia comprovada em operacoes",
        "resultado": "Reducao de custo em 13%",
        "nota": 1.0,
        "prova_literal": True,
        "fonte_base": "referencias:1",
    }


def _draft(company: str, role: str, marker: str) -> dict:
    story = {
        "empresa": "iFood",
        "resultado": "Expansao de 400 para 800 cidades",
        "keywords_cobertas": ["operacoes"],
        "angulo": "lideranca operacional baseada em dados",
        "ajustes": ["usar somente escopo comprovado"],
    }
    return {
        "cargo": role,
        "empresa": company,
        "modo": "Modo 1 - vaga especifica",
        "dor_central": f"Escalar {marker} com eficiencia e governanca",
        "keywords_vaga": [
            {"termo": "operacoes", "origem": "requisitos"},
            {"termo": marker, "origem": "responsabilidades"},
        ],
        "competencias_vaga": [
            {"competencia": "lideranca", "tipo": "soft skill"},
            {"competencia": "SQL", "tipo": "ferramenta"},
        ],
        "mapa_ajuste": [
            {
                "termo_vaga": f"{marker}-{index}",
                "tipo_ajuste": "DIRETO",
                "evidencia": "iFood com escala nacional",
                "empresa_origem": "iFood",
                "resultado_numero": "400 para 800 cidades",
                "angulo_sugerido": "conectar escala, dados e execucao",
                "ajustes_feitos": ["preservar o escopo literal"],
                "defensavel": True,
            }
            for index in range(1, 4)
        ],
        "objecoes": [
            {
                "objecao": f"Objecao {index} sobre {marker}",
                "classificacao": "media",
                "origem": "Mudanca de contexto setorial",
                "mitigacao": "Apresentar evidencia operacional transferivel",
                "evidencia_real": "iFood, expansao de 400 para 800 cidades",
            }
            for index in range(1, 4)
        ],
        "nota_aderencia": {
            "final": None,
            "dimensoes": {
                "requisitos_obrigatorios": {"itens": [_score_item("lideranca")]},
                "responsabilidades_principais": {
                    "itens": [_score_item(f"liderar {marker}")]
                },
                "ausencia_gaps_criticos": {
                    "gaps": [
                        {
                            "gap": "Sem experiencia literal no setor da empresa",
                            "severidade": "fraca",
                        }
                    ]
                },
                "diferenciais_desejaveis": {"itens": [_score_item("SQL")]},
            },
        },
        "gaps_sem_cobertura": ["Sem experiencia literal no setor da empresa"],
        "historias_selecionadas": {
            "principal": dict(story),
            "secundaria": {**story, "empresa": "wehandle"},
            "terceira": {**story, "empresa": "VivaReal"},
        },
        "keywords_habilidade_ats": [
            {
                "keyword": f"{marker} keyword {index}",
                "prioridade": index,
                "experiencia_alvo": "iFood",
                "bullet_sugerido": "Responsavel",
                "origem": "ja selecionada",
            }
            for index in range(1, 16)
        ],
    }


def _seed_application(paths, *, company: str, role: str, marker: str) -> None:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        paths.identity,
        {
            "kind": "application_identity",
            "application_id": paths.application_id,
            "source_type": "pasted_text",
            "source_id": f"source-{marker}",
            "company": company,
            "role": role,
        },
    )
    paths.job_description.write_text(
        _job_text(company, role, marker), encoding="utf-8"
    )
    write_json(paths.fit_map_draft, _draft(company, role, marker))


def _run_through_fit(executor: CellExecutor, run_id: str) -> None:
    first = executor.run_ready(run_id)
    assert [(item.node_id, item.status) for item in first] == [
        ("normalize_job", "validated")
    ]
    prepared = executor.prepare_ready_node(run_id, "analyze_fit")
    application_id = executor.resume(run_id).application_id
    paths = paths_for(application_id, root=executor.applications_root)
    _bind_draft(paths, run_id, prepared.attempt, prepared.manifest_path)
    second = executor.run_ready(run_id)
    assert next(
        item for item in second if item.node_id == "analyze_fit"
    ).status == "validated"


def _bind_draft(paths, run_id: str, attempt: int, manifest_path: Path) -> None:
    write_json(
        paths.app_dir / "fit_map.draft.binding.json",
        {
            "kind": "cellular_fit_map_draft_binding",
            "application_id": paths.application_id,
            "run_id": run_id,
            "node_id": "analyze_fit",
            "attempt": attempt,
            "job_fingerprint": hashlib.sha256(
                paths.job_description.read_bytes()
            ).hexdigest(),
            "draft_sha256": hashlib.sha256(
                paths.fit_map_draft.read_bytes()
            ).hexdigest(),
            "manifest_path": str(manifest_path.resolve()),
        },
    )


def _published_artifact(database: Database, run_id: str, name: str) -> dict:
    row = database.fetch_one(
        """SELECT path, content_hash FROM artifacts
           WHERE run_id = ? AND artifact_name = ?
           ORDER BY created_at DESC LIMIT 1""",
        (run_id, name),
    )
    assert row is not None
    return row


def test_analyze_fit_rejects_a_normalized_fingerprint_from_another_application(
    tmp_path,
):
    first = paths_for("fit-app-a", root=tmp_path / "applications")
    second = paths_for("fit-app-b", root=tmp_path / "applications")
    _seed_application(first, company="Acme", role="Head A", marker="alpha")
    _seed_application(second, company="Beta", role="Head B", marker="beta")
    first_normalized = derived_context.normalize_job(first)

    with pytest.raises(ValidationFailure, match="fingerprint"):
        fit_map.build_application_fit_map(
            second,
            expected_job_fingerprint=first_normalized["handover"][
                "job_fingerprint"
            ],
            candidate_facts_revision=first_normalized["handover"][
                "candidate_facts_revision"
            ],
            produced_by_attempt=1,
            contract_version="1",
        )


def test_candidate_facts_revision_covers_every_canonical_normalize_source(tmp_path):
    paths = paths_for("revision-app", root=tmp_path / "applications")
    _seed_application(paths, company="Acme", role="Head A", marker="alpha")

    assert {
        derived_context.KEYWORD_DICTIONARY_PATH,
        derived_context.CAREER_KEYWORDS_PATH,
        derived_context.SELF_KNOWLEDGE_PATH,
        derived_context.PROFILE_RESTRICTIONS_PATH,
    }.issubset(provenance.CANDIDATE_FACT_SOURCES)
    normalized = derived_context.normalize_job(paths)

    assert normalized["handover"]["candidate_facts_revision"] == (
        provenance.candidate_facts_revision()
    )


def test_normalize_job_rejects_a_supplied_candidate_facts_revision_mismatch(tmp_path):
    paths = paths_for("revision-mismatch-app", root=tmp_path / "applications")
    _seed_application(paths, company="Acme", role="Head A", marker="alpha")

    with pytest.raises(ValidationFailure, match="candidate facts revision mismatch"):
        derived_context.normalize_job(
            paths,
            candidate_facts_revision="0" * 64,
        )


def test_two_production_cell_runs_keep_descriptions_packs_fit_maps_and_inputs_scoped(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths_by_id = {
        "prod-app-a": paths_for("prod-app-a", root=applications_root),
        "prod-app-b": paths_for("prod-app-b", root=applications_root),
    }
    _seed_application(
        paths_by_id["prod-app-a"],
        company="Acme",
        role="Head de Operacoes",
        marker="alpha",
    )
    _seed_application(
        paths_by_id["prod-app-b"],
        company="Beta",
        role="Diretor de Planejamento",
        marker="beta",
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("production cells must not configure global paths")

    monkeypatch.setattr(derived_context, "configure_derived_dir", forbidden)
    monkeypatch.setattr(derived_context, "configure_state_store_path", forbidden)

    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        plans = {
            application_id: executor.plan(application_id, {"cv", "feras"})
            for application_id in paths_by_id
        }
        for plan in plans.values():
            _run_through_fit(executor, plan.run_id)

        published = {
            application_id: _published_artifact(
                database, plan.run_id, "fit_map.json"
            )
            for application_id, plan in plans.items()
        }
        assert published["prod-app-a"]["path"] != published["prod-app-b"]["path"]
        assert published["prod-app-a"]["content_hash"] != published["prod-app-b"][
            "content_hash"
        ]

        for application_id, plan in plans.items():
            paths = paths_by_id[application_id]
            fit_payload = read_json(Path(published[application_id]["path"]))
            derived_manifest = read_json(paths.derived_dir / "manifest.json")
            provenance = fit_payload["provenance"]
            assert provenance == {
                "candidate_facts_revision": derived_manifest[
                    "candidate_facts_revision"
                ],
                "contract_version": "1",
                "draft_sha256": hashlib.sha256(
                    paths.fit_map_draft.read_bytes()
                ).hexdigest(),
                "job_fingerprint": hashlib.sha256(
                    paths.job_description.read_bytes()
                ).hexdigest(),
                "produced_by_attempt": 1,
            }
            attempt_manifest = read_json(
                paths.cells_dir
                / plan.run_id
                / "analyze_fit"
                / "1"
                / "manifest.json"
            )
            draft_inputs = [
                value
                for key, value in attempt_manifest["inputs"].items()
                if key == "fit_map_draft"
            ]
            assert draft_inputs == [
                {
                    "path": str(paths.fit_map_draft.resolve()),
                    "revision": None,
                    "sha256": hashlib.sha256(
                        paths.fit_map_draft.read_bytes()
                    ).hexdigest(),
                    "source_kind": "file",
                }
            ]
            assert Path(published[application_id]["path"]).is_relative_to(
                paths.app_dir
            )
    finally:
        database.close()


def test_changed_fit_map_revision_invalidates_only_that_app_contract_descendants(
    tmp_path,
):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    first = paths_for("repair-app-a", root=applications_root)
    second = paths_for("repair-app-b", root=applications_root)
    _seed_application(first, company="Acme", role="Head A", marker="alpha")
    _seed_application(second, company="Beta", role="Head B", marker="beta")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        first_plan = executor.plan(first.application_id, {"cv", "feras"})
        second_plan = executor.plan(second.application_id, {"cv", "feras"})
        _run_through_fit(executor, first_plan.run_id)
        _run_through_fit(executor, second_plan.run_id)
        original = _published_artifact(database, first_plan.run_id, "fit_map.json")
        original_bytes = Path(original["path"]).read_bytes()

        for plan in (first_plan, second_plan):
            executor.mark_validated(plan.run_id, "compose_cv")
            executor.mark_validated(plan.run_id, "generate_feras")

        changed = read_json(first.fit_map_draft)
        changed["dor_central"] = "Escalar alpha com uma nova governanca regional"
        write_json(first.fit_map_draft, changed)
        repair = executor.repair(
            first_plan.run_id, "analyze_fit", "new fit evidence"
        )
        _bind_draft(
            first,
            first_plan.run_id,
            repair.attempt,
            repair.manifest_path,
        )

        # Reserving a repair cannot invalidate descendants before a new FIT_MAP exists.
        assert executor.node_status(first_plan.run_id, "compose_cv") == "validated"
        assert executor.node_status(first_plan.run_id, "generate_feras") == "validated"
        assert executor.node_status(second_plan.run_id, "compose_cv") == "validated"
        assert executor.node_status(second_plan.run_id, "generate_feras") == "validated"

        repaired = executor.run_ready(first_plan.run_id)
        fit_result = next(item for item in repaired if item.node_id == "analyze_fit")
        assert fit_result.status == "validated"
        revised = _published_artifact(database, first_plan.run_id, "fit_map.json")
        assert revised["content_hash"] != original["content_hash"]
        assert revised["path"] != original["path"]
        assert Path(original["path"]).read_bytes() == original_bytes
        assert read_json(Path(revised["path"]))["provenance"][
            "produced_by_attempt"
        ] == 2
        first_descendant_attempts = database.fetch_all(
            """SELECT node_id, status FROM cell_attempts
               WHERE run_id = ? AND node_id IN ('compose_cv', 'generate_feras')
                 AND attempt = 1
               ORDER BY node_id""",
            (first_plan.run_id,),
        )
        assert [(row["node_id"], row["status"]) for row in first_descendant_attempts] == [
            ("compose_cv", "superseded"),
            ("generate_feras", "superseded"),
        ]
    finally:
        database.close()


def test_unchanged_fit_map_repair_preserves_declared_descendants(tmp_path):
    database = Database(tmp_path / "career.db")
    database.init_schema()
    applications_root = tmp_path / "applications"
    paths = paths_for("unchanged-repair-app", root=applications_root)
    _seed_application(paths, company="Acme", role="Head A", marker="alpha")
    executor = CellExecutor(
        database,
        applications_root=applications_root,
        handlers=cell_handlers.production_handler_registry(),
        validators=cell_handlers.production_validator_registry(),
    )
    try:
        plan = executor.plan(paths.application_id, {"cv", "feras"})
        _run_through_fit(executor, plan.run_id)
        executor.mark_validated(plan.run_id, "compose_cv")
        executor.mark_validated(plan.run_id, "generate_feras")

        repair = executor.repair(
            plan.run_id, "analyze_fit", "verify unchanged fit"
        )
        _bind_draft(paths, plan.run_id, repair.attempt, repair.manifest_path)
        assert executor.node_status(plan.run_id, "compose_cv") == "validated"
        assert executor.node_status(plan.run_id, "generate_feras") == "validated"

        repaired = executor.run_ready(plan.run_id)
        assert next(item for item in repaired if item.node_id == "analyze_fit").status == "validated"
        assert executor.node_status(plan.run_id, "compose_cv") == "validated"
        assert executor.node_status(plan.run_id, "generate_feras") == "validated"
    finally:
        database.close()


def test_provenance_validator_rejects_tampered_candidate_revision(tmp_path):
    paths = paths_for("tamper-app", root=tmp_path / "applications")
    _seed_application(paths, company="Acme", role="Head A", marker="alpha")
    normalized = derived_context.normalize_job(paths)
    payload = fit_map.build_application_fit_map(
        paths,
        expected_job_fingerprint=normalized["handover"]["job_fingerprint"],
        candidate_facts_revision=normalized["handover"][
            "candidate_facts_revision"
        ],
        produced_by_attempt=1,
        contract_version="1",
    )
    payload["provenance"]["candidate_facts_revision"] = "0" * 64

    with pytest.raises(ValidationFailure, match="candidate facts revision"):
        fit_map.validate_application_fit_map(
            payload,
            application_paths=paths,
            expected_candidate_facts_revision=normalized["handover"][
                "candidate_facts_revision"
            ],
        )


def test_provenance_validator_rejects_tampered_draft_hash(tmp_path):
    paths = paths_for("draft-tamper-app", root=tmp_path / "applications")
    _seed_application(paths, company="Acme", role="Head A", marker="alpha")
    normalized = derived_context.normalize_job(paths)
    payload = fit_map.build_application_fit_map(
        paths,
        expected_job_fingerprint=normalized["handover"]["job_fingerprint"],
        candidate_facts_revision=normalized["handover"][
            "candidate_facts_revision"
        ],
        produced_by_attempt=1,
        contract_version="1",
    )
    payload["provenance"]["draft_sha256"] = "0" * 64

    with pytest.raises(ValidationFailure, match="draft SHA-256 mismatch"):
        fit_map.validate_application_fit_map(
            payload,
            application_paths=paths,
            expected_candidate_facts_revision=normalized["handover"][
                "candidate_facts_revision"
            ],
        )
