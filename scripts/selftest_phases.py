#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import bootstrap

ROOT = bootstrap()

from career.paths import CAREER_STATE, OUTPUTS
from career.schemas.fit_map import FitMapDraftSchema, FitMapFinalSchema
from career.schemas.notion import NotionApplicationsCacheSchema
from career.schemas.review import CvReviewReportSchema
from career.utils import read_json
from career.utils import ValidationFailure
from career.workflow.state_machine import WorkflowStateMachine
import notion_sync
import register_keywords
import review_output
from career.services import applications_v2 as applications_service
from career.services import review as review_service


def run_command(args: list[str]) -> None:
    if args and args[0] == "npm":
        args = ["npm.cmd", *args[1:]]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed ({' '.join(args)}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def phase_1() -> None:
    NotionApplicationsCacheSchema(read_json(ROOT / "inbox/notion/applications_cache.json")).validate()
    FitMapFinalSchema(read_json(CAREER_STATE / "fit_map.json")).validate()
    report_path = OUTPUTS / "_tmp" / "output_review_report.json"
    if report_path.exists():
        CvReviewReportSchema(read_json(report_path)).validate()


def phase_2() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        draft_path = Path(tmp_dir) / "fit_map.draft.json"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        FitMapDraftSchema(read_json(draft_path)).payload
    run_command([sys.executable, "scripts/career_cli.py", "notion", "build-cache"])


def phase_3() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "reset-state"])
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "run-task", "notion.build_cache"])
    state = read_json(CAREER_STATE / "workflow_state.json")
    if "notion_cache_ready" not in state.get("completed_states", []):
        raise SystemExit("Workflow state did not register notion_cache_ready")


def phase_4() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "project", "validate-structure"])


def phase_5() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "workflow", "reset-state"])
    try:
        run_command([sys.executable, "scripts/career_cli.py", "workflow", "run-task", "fit_map.score"])
    except SystemExit:
        return
    raise SystemExit("State machine test failed: fit_map.score should not run before fit_map.build")


def phase_6() -> None:
    run_command([sys.executable, "scripts/career_cli.py", "notion", "refresh"])


def phase_7() -> None:
    run_command(["npm", "run", "validate:structure"])


def phase_8() -> None:
    session_path = ROOT / "session-ses_1def.md"
    job_path = ROOT / "inbox" / "job_descriptions" / "tprime_tecnologia_goevo_head_de_operacoes_saas.md"
    if not session_path.exists() or not job_path.exists():
        raise SystemExit("Stall regression fixture missing")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        draft_path = tmp / "fit_map.draft.json"
        fit_map_path = tmp / "fit_map.json"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        fit_map_path.write_text(
            json.dumps(
                {
                    "cargo": "Head de Revenue Operations",
                    "empresa": "iugu",
                    "modo": "Modo 1 - vaga especifica",
                    "dor_central": "fixture",
                    "keywords_vaga": [],
                    "competencias_vaga": [],
                    "keywords_para_ats": [],
                    "mapa_ajuste": [],
                    "objecoes": [],
                    "nota_aderencia": {"final": 1, "dimensoes": {}},
                    "gaps_sem_cobertura": [],
                    "historias_selecionadas": {},
                    "keywords_habilidade_ats": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "scripts/diagnose_session_stall.py",
                str(session_path),
                "--draft",
                str(draft_path),
                "--fit-map",
                str(fit_map_path),
                "--job-description",
                str(job_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 1:
            raise SystemExit(f"Expected stalled session exit code 1, got {result.returncode}:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(result.stdout)
        expected = {
            "stalled": True,
            "last_completed_step": "fit-map:template",
            "next_required_step": "preencher .career-state/fit_map.draft.json",
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise SystemExit(f"Unexpected stall diagnosis for {key}: {payload.get(key)!r}")
        signals = payload.get("signals", {})
        if not signals.get("draft_placeholder") or not signals.get("fit_map_stale"):
            raise SystemExit(f"Stall diagnosis missed expected signals: {signals}")


def phase_9() -> None:
    machine = WorkflowStateMachine(
        {"fit_map_draft_valid"},
        {"fit_map.validate_draft": {"active_job_fingerprint": "old-job"}},
        "new-job",
    )
    try:
        machine.ensure_task_allowed("fit_map.build")
    except ValidationFailure:
        return
    raise SystemExit("State machine should block FIT_MAP build when prerequisite belongs to another job")


def phase_10() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        draft_path = Path(tmp_dir) / "fit_map.draft.json"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "fit-map",
                "validate-stage",
                "extract",
                "--path",
                str(draft_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            raise SystemExit("validate-stage extract should fail while template placeholders remain")


def phase_11() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        job_dir = Path(tmp_dir)
        job_path = job_dir / "atvos_gerente_de_planejamento_integrado_s_op_s_oe.md"
        job_path.write_text(
            "# Atvos - Gerente de Planejamento Integrado (S&OP | S&OE)\n\nDescrição real da vaga.\n",
            encoding="utf-8",
        )
        fit_map = {
            "empresa": "Atvos",
            "cargo": "Gerente de Planejamento Integrado (S&OP | S&OE)",
        }
        text, path, source = notion_sync.select_job_description_for_update(
            fit_map,
            None,
            "Pesquisa Inicial\nFeedback em caso de Reprovação",
            saved_job_dir=job_dir,
        )
        if source != "saved_job_description" or path != job_path or "Descrição real da vaga" not in text:
            raise SystemExit(
                "Notion manual-template update should select saved active job description, "
                f"got source={source!r}, path={path!r}"
            )


def phase_12() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        artifact = tmp / "cv.docx"
        fit_map = tmp / "fit_map.json"
        registry = tmp / "registry.json"
        report = tmp / "output_review_report.json"
        artifact.write_bytes(b"docx")
        fit_map.write_text("{}", encoding="utf-8")
        registry.write_text("{}", encoding="utf-8")

        original_run = review_service.subprocess.run
        original_build = review_service.legacy_review_output.build_cv_review
        try:
            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            review_service.subprocess.run = lambda *args, **kwargs: Result()
            review_service.legacy_review_output.build_cv_review = lambda *args, **kwargs: {
                "kind": "cv",
                "artifact": str(artifact),
                "company": "Atvos",
                "role": "Gerente",
                "approved": False,
                "approved_for_delivery": False,
                "ats_policy": {
                    "top8": {"score": 4.0, "score_max": 8},
                    "top15": {"score": 6.0, "score_max": 15},
                },
                "blockers": [{"id": "ats_top8_minimum_score", "message": "blocked", "evidence": ""}],
                "warnings": [],
                "totals": {
                    "weight_total_passed": 6,
                    "weight_total_total": 7,
                    "minor_passed": 10,
                    "minor_total": 11,
                    "minor_rate": 0.9091,
                    "blockers": 1,
                    "warnings": 0,
                },
                "weight_total_checks": [{"id": "top8_keywords_covered", "passed": False}],
                "minor_checks": [],
                "top8_keywords": [],
                "summary_chars": 100,
            }
            try:
                review_service.approve_cv(artifact, fit_map, registry, report)
            except SystemExit as exc:
                if "not approved" not in str(exc):
                    raise
            else:
                raise SystemExit("approve_cv should fail when review report approved=false")
        finally:
            review_service.subprocess.run = original_run
            review_service.legacy_review_output.build_cv_review = original_build


def phase_13() -> None:
    fit_map = {
        "keywords_habilidade_ats": [
            {
                "keyword": "Plano Operacional Unico",
                "prioridade": 1,
                "origem": "já selecionada",
            }
        ],
        "keywords_vaga": [],
        "gaps_sem_cobertura": [],
    }
    records = register_keywords.keyword_records(
        fit_map,
        "Busco posição liderando o Plano Operacional Único entre áreas.",
    )
    if records[0]["status"] != "covered_cv":
        raise SystemExit(f"Expected accent-insensitive covered_cv, got {records[0]}")

    top8, missing = review_output.top_keyword_results(
        fit_map,
        {"keyword_records": [{"keyword": "Plano Operacional Unico", "status": "missing_cv"}]},
        ["Busco posição liderando o Plano Operacional Único entre áreas."],
        {"entries": {}},
    )
    if missing or not top8[0]["covered"]:
        raise SystemExit(f"Expected reviewer normalized evidence coverage, got top8={top8}, missing={missing}")


def phase_14() -> None:
    def fit_map_for(classes: list[str]) -> dict:
        gaps = [
            f"Keyword {index} gap"
            for index, coverage_class in enumerate(classes, start=1)
            if coverage_class == "declared_gap"
        ]
        return {
            "keywords_habilidade_ats": [
                {
                    "keyword": f"Keyword {index}",
                    "prioridade": index,
                    "origem": "gap" if coverage_class == "declared_gap" else "já selecionada",
                }
                for index, coverage_class in enumerate(classes, start=1)
            ],
            "keywords_vaga": [],
            "gaps_sem_cobertura": gaps,
        }

    def application_for(classes: list[str]) -> dict:
        status_by_class = {
            "covered_exact": "covered_cv",
            "covered_similar": "covered_similar_cv",
            "declared_gap": "gap",
            "missing_unexplained": "missing_cv",
        }
        return {
            "keyword_records": [
                {
                    "keyword": f"Keyword {index}",
                    "status": status_by_class[coverage_class],
                }
                for index, coverage_class in enumerate(classes, start=1)
            ]
        }

    optimal_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "covered_similar",
        "declared_gap",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(optimal_classes),
        application_for(optimal_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if missing or summary["score"] != 6.6 or summary["level"] != "optimal":
        raise SystemExit(f"Expected optimal ATS policy case, got summary={summary}, missing={missing}")

    minimum_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "covered_similar",
        "declared_gap",
        "declared_gap",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(minimum_classes),
        application_for(minimum_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if missing or summary["score"] != 5.6 or summary["level"] != "minimum":
        raise SystemExit(f"Expected minimum ATS policy case, got summary={summary}, missing={missing}")

    blocked_classes = [
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_exact",
        "covered_similar",
        "missing_unexplained",
        "missing_unexplained",
        "missing_unexplained",
    ]
    results, missing = review_output.top_keyword_results(
        fit_map_for(blocked_classes),
        application_for(blocked_classes),
        [],
        {"entries": {}},
    )
    summary = review_output.ats_score_summary(results, limit=8)
    if len(missing) != 3 or summary["score"] != 4.8 or summary["level"] != "blocked":
        raise SystemExit(f"Expected blocked ATS policy case, got summary={summary}, missing={missing}")


def phase_15() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        draft_path = tmp / "fit_map.draft.json"
        fit_map_path = tmp / "fit_map.json"
        job_path = tmp / "allied_brasil_gerente_supply_chain_e_pricing.md"
        run_command([sys.executable, "scripts/career_cli.py", "fit-map", "template", "--output", str(draft_path)])
        fit_map_path.write_text(
            json.dumps(
                {
                    "cargo": "Gerente de Planejamento Integrado",
                    "empresa": "Atvos",
                    "modo": "Modo 1 - vaga especifica",
                    "dor_central": "fixture",
                    "keywords_vaga": [],
                    "competencias_vaga": [],
                    "keywords_para_ats": [],
                    "mapa_ajuste": [],
                    "objecoes": [],
                    "nota_aderencia": {"final": 1, "dimensoes": {}},
                    "gaps_sem_cobertura": [],
                    "historias_selecionadas": {},
                    "keywords_habilidade_ats": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        job_path.write_text("Allied Brasil\nGerente Supply Chain e Pricing\n", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "fit-map",
                "guard",
                "--draft",
                str(draft_path),
                "--fit-map",
                str(fit_map_path),
                "--job-description",
                str(job_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 1:
            raise SystemExit(f"Guard should block placeholder draft, got {result.returncode}:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(result.stdout)
        if payload.get("guard") != "blocked" or payload.get("next_required_step") != "preencher .career-state/fit_map.draft.json":
            raise SystemExit(f"Unexpected guard payload: {payload}")
        if "PARE A NARRATIVA" not in payload.get("instruction", ""):
            raise SystemExit(f"Guard instruction should be explicit, got: {payload.get('instruction')}")


def phase_16() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        output = tmp / "general_cv_strategy.json"
        report = tmp / "general_cv_strategy.md"

        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--output",
                str(output),
                "--report",
                str(report),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV default strategy should pass:\n{result.stdout}\n{result.stderr}")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("mode") != "concise" or payload.get("bullet_count_per_experience") != 3:
            raise SystemExit(f"Default general CV should be concise with 3 bullets, got {payload}")

        output_5 = tmp / "general_cv_strategy_5.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "expanded",
                "--bullet-count",
                "5",
                "--output",
                str(output_5),
                "--report",
                str(tmp / "report_5.md"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV expanded with 5 bullets should pass:\n{result.stdout}\n{result.stderr}")
        payload_5 = json.loads(output_5.read_text(encoding="utf-8"))
        if payload_5.get("bullet_count_per_experience") != 5:
            raise SystemExit(f"Expected 5 bullets, got {payload_5}")

        concise_default_cluster = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "concise",
                "--output",
                str(tmp / "concise.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if concise_default_cluster.returncode != 0:
            raise SystemExit(
                "General CV concise without cluster should default to operations cluster:\n"
                f"{concise_default_cluster.stdout}\n{concise_default_cluster.stderr}"
            )
        payload_concise = json.loads((tmp / "concise.json").read_text(encoding="utf-8"))
        if payload_concise.get("dominant_cluster") != "operacoes_supply_logistica":
            raise SystemExit(f"Expected default operations cluster for concise CV, got {payload_concise}")

        concise_output = tmp / "general_cv_strategy_concise.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/career_cli.py",
                "general-cv",
                "strategy",
                "--mode",
                "concise",
                "--dominant-cluster",
                "operacoes_supply_logistica",
                "--output",
                str(concise_output),
                "--report",
                str(tmp / "report_concise.md"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise SystemExit(f"General CV concise with cluster should pass:\n{result.stdout}\n{result.stderr}")
        concise_payload = json.loads(concise_output.read_text(encoding="utf-8"))
        clusters = set(concise_payload.get("clusters", {}))
        if concise_payload.get("mode") != "concise" or clusters != {"operacoes_supply_logistica"}:
            raise SystemExit(f"Concise mode should only cover dominant cluster, got {concise_payload}")


def phase_17() -> None:
    applications = [
        {"record_id": 10, "status": "Em análise", "description_chars": 100, "title": "A"},
        {"record_id": 11, "status": "Aplicação Feita", "description_chars": 100, "title": "B"},
        {"record_id": 12, "status": "Analisando", "description_chars": 100, "title": "C"},
        {"record_id": 13, "status": "Aplicação em Análise", "description_chars": 0, "title": "D"},
        {"record_id": 14, "status": "Reprocessar", "description_chars": 100, "title": "E"},
        {"record_id": 15, "status": "Aplicação em Análise", "description_chars": 100, "title": "F", "is_archived": True},
    ]
    selected = applications_service._eligible(applications, applications_service.DEFAULT_CONFIG, 3)
    if [item["title"] for item in selected] != ["E", "D", "C"]:
        raise SystemExit(f"Unexpected heartbeat queue selection: {selected}")
    if applications_service.DEFAULT_CONFIG["no_description_status"] != "Sem descrição de vaga":
        raise SystemExit("Unexpected no-description Notion status spelling")
    if applications_service.detect_job_language("About the role\nResponsibilities\nRequirements") != "en":
        raise SystemExit("Expected English job description detection")
    if applications_service.detect_job_language("Sobre a vaga\nResponsabilidades\nRequisitos") != "pt-BR":
        raise SystemExit("Expected Portuguese job description detection")

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact = Path(tmp_dir) / "felipe_armel_cv_fixture.docx"
        artifact.write_text("placeholder", encoding="utf-8")
        report = Path(tmp_dir) / "polish_review.json"
        original_docx_text = review_service.legacy_review_output.docx_text
        original_is_portuguese = review_service.legacy_review_output.is_portuguese_cv
        try:
            review_service.legacy_review_output.docx_text = lambda _path: (
                "Resumo\n"
                "Conduzi experimentation e data-driven decision making em operações.\n"
                "Experiência\n"
            )
            review_service.legacy_review_output.is_portuguese_cv = lambda _path: True
            payload = review_service.polish_cv(artifact, report)
            blockers = payload.get("approval_blockers", [])
            if not any("experimentation" in item for item in blockers):
                raise SystemExit(f"Expected experimentation blocker, got {payload}")
            if not report.exists():
                raise SystemExit("Polish report was not written")
        finally:
            review_service.legacy_review_output.docx_text = original_docx_text
            review_service.legacy_review_output.is_portuguese_cv = original_is_portuguese


def phase_18() -> None:
    if not hasattr(applications_service, "run_heartbeat"):
        raise SystemExit("applications_v2 service must expose run_heartbeat")
    if not hasattr(applications_service, "write_default_config"):
        raise SystemExit("applications_v2 service must expose write_default_config")


def phase_19() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "999"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        write_json = lambda path, payload: path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        write_json(
            paths["manifest"],
            {"role": "Gerente", "company": "Empresa", "title": "Gerente", "required_cv_filename_suffix": ""},
        )
        write_json(paths["fit_map"], {"cargo": "Gerente", "empresa": "Empresa", "nota_aderencia": {"final": 7.0}})
        paths["cv_content"].write_text(json.dumps({"summary": "ok", "experiences": []}), encoding="utf-8")
        paths["feras_formal"].write_text("FERAS\n", encoding="utf-8")
        paths["habilidades_gupy"].write_text("Habilidades\n", encoding="utf-8")
        paths["habilidades_mercado_livre"].write_text("Habilidades\n", encoding="utf-8")
        write_json(paths["cv_review_report"], {"approved_for_delivery": True})
        write_json(paths["polish_review"], {"polish_executed": True, "approval_blockers": []})
        original_outputs = applications_service.OUTPUTS
        try:
            applications_service.OUTPUTS = tmp / "outputs"
            if applications_service._is_review_approved(paths):
                raise SystemExit("Review cannot be approved when the expected DOCX file is missing")
        finally:
            applications_service.OUTPUTS = original_outputs


def phase_20() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        original_v2_dir = applications_service.V2_DIR
        original_inbox = applications_service.INBOX
        try:
            applications_service.V2_DIR = tmp / "applications_v2"
            applications_service.INBOX = tmp / "inbox"
            app_dir, paths = applications_service._write_package(
                {
                    "record_id": 501,
                    "title": "Planning & Materials Manager (Finished Goods)",
                    "role": "Planning & Materials Manager (Finished Goods)",
                    "company": "Beckman Coulter Diagnostics (Danaher)",
                    "description": "About the role\nPlanning & Materials Manager (Finished Goods)\n",
                }
            )
            saved_pointer = paths["saved_job_description"].read_text(encoding="utf-8").strip()
            saved_path = Path(saved_pointer)
            if not saved_path.exists():
                raise SystemExit("Expected canonical saved job description to be created during package write")
            if "planning_materials_manager_finished_goods" not in saved_path.name:
                raise SystemExit(f"Canonical saved job description slug is wrong: {saved_path.name}")
            if app_dir != applications_service.V2_DIR / "501":
                raise SystemExit(f"Unexpected application dir: {app_dir}")
        finally:
            applications_service.V2_DIR = original_v2_dir
            applications_service.INBOX = original_inbox


def phase_21() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "777"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["job_description"].write_text("Sobre a vaga\nGerente de Pricing\n", encoding="utf-8")
        paths["fit_map_draft"].write_text("{}", encoding="utf-8")
        paths["manifest"].write_text(
            json.dumps({"role": "Gerente de Pricing", "company": "Empresa", "title": "Gerente de Pricing", "required_cv_filename_suffix": ""}),
            encoding="utf-8",
        )
        state = {"retry_count_analyze": 0, "last_error": None}
        applications_service._set_stage(state, "analyze_running")

        original_run_agent = applications_service._run_agent
        original_postprocess = applications_service._postprocess_analyze
        original_write_state = applications_service._write_state
        original_write_context = applications_service._write_context

        calls = {"postprocess": 0, "write_state": 0}

        def fake_run_agent(stage, application, local_paths, config, options):
            if stage != "analyze":
                raise SystemExit(f"Unexpected stage for fake agent: {stage}")

        def fake_postprocess(local_paths):
            calls["postprocess"] += 1
            if calls["postprocess"] == 1:
                raise ValidationFailure("draft still has placeholders")
            return 7.4

        def fake_write_state(local_paths, payload):
            calls["write_state"] += 1

        def fake_write_context(application, local_paths, payload):
            return None

        try:
            applications_service._run_agent = fake_run_agent
            applications_service._postprocess_analyze = fake_postprocess
            applications_service._write_state = fake_write_state
            applications_service._write_context = fake_write_context
            result = applications_service._run_analyze_with_retry(
                {"record_id": 777, "title": "Gerente de Pricing", "company": "Empresa", "role": "Gerente de Pricing"},
                paths,
                applications_service.DEFAULT_CONFIG,
                applications_service.HeartbeatV2Options(max_per_run=1, run_agent=True, dry_run=False),
                state,
            )
            if result != 7.4:
                raise SystemExit(f"Unexpected retry result: {result}")
            if state.get("retry_count_analyze") != 1:
                raise SystemExit(f"Analyze retry counter did not increment: {state}")
            if state.get("stage") != "analyze_retry_pending":
                raise SystemExit(f"State did not move to analyze_retry_pending before retry: {state}")
            if calls["postprocess"] != 2:
                raise SystemExit(f"Postprocess should run twice with retry, got {calls['postprocess']}")
            if calls["write_state"] != 1:
                raise SystemExit(f"Retry path should persist state once before rerun, got {calls['write_state']}")
        finally:
            applications_service._run_agent = original_run_agent
            applications_service._postprocess_analyze = original_postprocess
            applications_service._write_state = original_write_state
            applications_service._write_context = original_write_context


def phase_22() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "888"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["job_description"].write_text("Sobre a vaga\nGerente\n", encoding="utf-8")
        paths["cv_review_report"].write_text(json.dumps({"approved_for_delivery": False}), encoding="utf-8")
        paths["polish_review"].write_text(json.dumps({"approval_blockers": ["pt_cv_keyword_shotgun_control"]}), encoding="utf-8")
        manifest = {
            "role": "Gerente",
            "company": "Empresa",
            "title": "Gerente",
            "required_cv_filename_suffix": "",
        }
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        paths["fit_map"].write_text(json.dumps({"cargo": "Gerente", "empresa": "Empresa", "nota_aderencia": {"final": 7.2}}), encoding="utf-8")
        original_outputs = applications_service.OUTPUTS
        try:
            applications_service.OUTPUTS = tmp / "outputs"
            expected_docx = applications_service._expected_cv_docx_path(paths)
            expected_docx.parent.mkdir(parents=True, exist_ok=True)
            expected_docx.write_text("fixture", encoding="utf-8")
            stage, score = applications_service._derive_stage(paths, applications_service.DEFAULT_CONFIG)
            if stage != "blocked_review" or score != 7.2:
                raise SystemExit(f"Expected blocked_review stage, got stage={stage} score={score}")
        finally:
            applications_service.OUTPUTS = original_outputs


def phase_23() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "889"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        paths["fit_map"].write_text(
            json.dumps(
                {
                    "cargo": "Coordenador(a) de Operações",
                    "empresa": "Nomad",
                    "keywords_habilidade_ats": [
                        {"keyword": "Liderança de Operações", "prioridade": 1},
                        {"keyword": "Gestão de Incidentes", "prioridade": 2},
                        {"keyword": "SLAs", "prioridade": 3},
                        {"keyword": "Gestão de Times", "prioridade": 4},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["cv_content"].write_text(
            json.dumps(
                {
                    "summary": "ok",
                    "experiences": [
                        {"role": "A", "company": "X", "period": "1", "bullets": [{"text": "b1"}]},
                        {"role": "B", "company": "Y", "period": "2", "bullets": [{"text": "b2"}]},
                        {"role": "C", "company": "Z", "period": "3", "bullets": [{"text": "b3"}]},
                    ],
                    "ats_keyword_coverage": [],
                    "education": [],
                    "languages": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            applications_service._validate_cv_content_contract(paths)
        except ValidationFailure as exc:
            if "between 4 and 8 experiences" not in str(exc):
                raise SystemExit(f"Unexpected validation error for cv_content contract: {exc}")
        else:
            raise SystemExit("cv_content contract should block when experiences < 4")


def phase_24() -> None:
    temp_root = OUTPUTS / "_tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as tmp_dir:
        tmp = Path(tmp_dir)
        app_dir = tmp / "applications_v2" / "890"
        app_dir.mkdir(parents=True)
        paths = applications_service._app_paths(app_dir)
        state = {
            "stage": "blocked_review",
            "score": 6.1,
            "last_error": "review blocked",
            "review_status": "blocked",
            "polish_status": "pending",
        }
        review_report = {
            "blockers": [{"id": "ats_top8_no_missing_unexplained"}],
            "top8_keywords": [
                {
                    "keyword": "Liderança de Operações",
                    "coverage_class": "missing_unexplained",
                    "experience_target": "wehandle - Head de Operações",
                    "coverage_note": None,
                },
                {
                    "keyword": "SLAs",
                    "coverage_class": "covered_exact",
                    "experience_target": "wehandle - Head de Operações",
                    "coverage_note": None,
                },
            ],
        }
        polish_report = {"approval_blockers": []}
        paths["fit_map"].write_text(json.dumps({"cargo": "Coordenador(a) de Operações", "empresa": "Nomad"}), encoding="utf-8")
        paths["cv_content"].write_text(json.dumps({"summary": "ok", "experiences": []}), encoding="utf-8")
        paths["cv_review_report"].write_text(json.dumps(review_report), encoding="utf-8")
        paths["polish_review"].write_text(json.dumps(polish_report), encoding="utf-8")
        paths["feras_formal"].write_text("x", encoding="utf-8")
        paths["habilidades_gupy"].write_text("x", encoding="utf-8")
        paths["habilidades_mercado_livre"].write_text("x", encoding="utf-8")
        applications_service._write_repair_request(paths, state, review_report, polish_report)
        payload = json.loads(paths["repair_request_json"].read_text(encoding="utf-8"))
        missing = payload.get("missing_unexplained_top8", [])
        if not missing or missing[0].get("keyword") != "Liderança de Operações":
            raise SystemExit(f"Repair request should register missing top8 keyword, got {payload}")
        if "4 e 8 experiências" not in " ".join(payload.get("repair_rules", [])):
            raise SystemExit(f"Repair rules should mention experience range, got {payload}")


PHASES = {
    1: phase_1,
    2: phase_2,
    3: phase_3,
    4: phase_4,
    5: phase_5,
    6: phase_6,
    7: phase_7,
    8: phase_8,
    9: phase_9,
    10: phase_10,
    11: phase_11,
    12: phase_12,
    13: phase_13,
    14: phase_14,
    15: phase_15,
    16: phase_16,
    17: phase_17,
    18: phase_18,
    19: phase_19,
    20: phase_20,
    21: phase_21,
    22: phase_22,
    23: phase_23,
    24: phase_24,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, choices=sorted(PHASES), required=True)
    args = parser.parse_args()
    PHASES[args.phase]()
    print(json.dumps({"phase": args.phase, "status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
