from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from career.paths import CAREER_STATE, OUTPUTS
from career.services import application_context as application_context_service
from career.services.agent_runner import AgentRunRequest, SubprocessAgentRunner
from career.services.approvals import ApprovalStore
from career.services.approved_actions import ApprovedActionExecutor
from career.services.harness_runs import HarnessRunStore, begin_specialist_run
from career.services.pipeline_intent import PipelineIntentStore
from career.utils import ValidationFailure, read_json, utc_now_iso, write_json

from career.services.classifier import Classifier
from career.services.router import Router
from career.services.menu import MenuBuilder
from career.services.executor import Executor
from career.services.database import Database
from career.services.persistence.analysis_repository import (
    AnalysisRepository,
    StaleAnalysisError,
)
from career.services.persistence.application_repository import (
    ApplicationNotFoundError,
    ApplicationRepository,
)
from career.services.persistence.artifact_repository import ArtifactRepository
from career.services.persistence.gate_repository import (
    REVISION_BOUND_GATES,
    GateRepository,
)
from career.services.workflow import WorkflowService
from career.workflow.state_store import WorkflowStateStore
from career.utils import sha256_text


LINKEDIN_JOB_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:jobs(?:/view)?|job)/[^\s]+", re.IGNORECASE)
LINKEDIN_POST_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/(?:feed/update|posts|pulse)/[^\s]+",
    re.IGNORECASE,
)
GENERIC_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
NOTION_ID_RE = re.compile(r"\b(?:notion|vaga|id)\s*#?\s*(\d+)\b", re.IGNORECASE)
APPLICATION_ID_RE = re.compile(
    r"\bapplication_id\s*[:=]?\s*([A-Za-z0-9][A-Za-z0-9_-]*)\b",
    re.IGNORECASE,
)
RUN_ID_RE = re.compile(
    r"\brun_id\s*[:=]?\s*(run_[A-Za-z0-9][A-Za-z0-9_-]*)\b",
    re.IGNORECASE,
)
CELL_REPAIR_NODE_RE = re.compile(
    r"\b(?:repare|reparar|repair|corrija|corrigir|conserte|consertar|ajuste|ajustar)"
    r"(?:\s+(?:primeiro|antes))?\s+(?:(?:o|a|no|na)\s+)?"
    r"(compose_cv|render_cv|review_cv|deliver_cv|normalize_job|analyze_fit)\b",
    re.IGNORECASE,
)

SPECIALIST_OUTPUT_PATTERNS = {
    "fit-map": [
        ".career-state/fit_map.draft.json",
        ".career-state/workflow_state.json",
        ".career-state/applications_v2/*/fit_map.draft.json",
        ".career-state/applications_v2/*/workflow_state.json",
    ],
    "cv": [
        ".career-state/cv_content.json",
        ".career-state/applications_v2/*/cv_content.json",
        ".career-state/applications_v2/*/cv_review_report.json",
        ".career-state/applications_v2/*/polish_review.json",
        "outputs/*.docx",
        "outputs/_tmp/output_review_report.json",
        "outputs/_tmp/polish_review.json",
        "outputs/_tmp/delivery_report.json",
    ],
    "cover-letter": ["outputs/*.md", "outputs/*.pdf", "outputs/_tmp/delivery_report.json"],
    "feras": ["outputs/*.md"],
    "habilidades": ["outputs/*.md"],
    "notion-update": [
        ".career-state/pending_actions/*.json",
        ".career-state/applications_v2/*/notion_update_payload.json",
        ".career-state/derived/active_context.json",
        ".career-state/derived/job_extract.json",
        ".career-state/derived/manifest.json",
        ".career-state/derived/keyword_ats_registry.json",
        ".career-state/derived/keyword_translation_candidates.json",
        "inbox/job_descriptions/*.md",
    ],
    "email-draft": [".career-state/pending_actions/*.json"],
    "linkedin": [
        ".career-state/linkedin_job_extract.json",
        ".career-state/linkedin_post_extract.json",
        ".career-state/workflow_state.json",
        ".career-state/applications_v2/*/workflow_state.json",
        ".career-state/applications_v2/*/job_description.md",
        "inbox/job_descriptions/*.md",
        "inbox/linkedin_posts/*.md",
    ],
}


def _mirror_application_outputs(
    root: Path, step: str, request_payload: dict[str, Any]
) -> list[dict[str, str]]:
    """Mirror scoped text artifacts into ``outputs/`` for human discovery.

    The application directory remains the source of truth.  The mirror is
    deliberately namespaced by application ID so a later vacancy cannot
    overwrite an earlier FERAS or habilidades artifact.
    """
    application_id = str(request_payload.get("application_id") or "").strip()
    if not application_id or step not in {"feras", "habilidades", "cover-letter"}:
        return []
    application_dir = (
        root / ".career-state" / "applications_v2" / application_id
    ).resolve()
    mirrored: list[dict[str, str]] = []
    manifest_path = application_dir / "artifacts_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.setdefault("kind", "application_artifacts_manifest")
    manifest["application_id"] = application_id
    manifest["source_of_truth"] = str(application_dir.relative_to(root))
    artifacts = manifest.setdefault("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
        manifest["artifacts"] = artifacts
    for raw_path in request_payload.get("expected_outputs") or []:
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        source = (root / raw_path).resolve()
        try:
            source.relative_to(application_dir)
        except ValueError:
            continue
        if not source.is_file():
            continue
        destination = OUTPUTS / f"{application_id}_{source.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        artifact_key = {
            "feras_formal.md": "feras",
            "habilidades_gupy.md": "habilidades_gupy",
            "cover_letter.md": "cover_letter",
        }.get(source.name, source.stem)
        artifacts[artifact_key] = str(source.relative_to(root))
        artifacts[f"{artifact_key}_discoverable_copy"] = str(
            destination.relative_to(root)
        )
        mirrored.append(
            {
                "source": str(source.relative_to(root)),
                "path": str(destination.relative_to(root)),
            }
        )
    if mirrored:
        write_json(manifest_path, manifest)
    return mirrored

ACTIVE_INTAKE_STALE_AFTER = timedelta(hours=24)
DEFAULT_HARNESS_AUTOMATION = {
    "fit_map": {"auto_finalize": True},
    "approvals": {"notion_write": "explicit_request", "email_draft": "manual"},
}
PREVIEW_HINTS = (
    "dry-run", "dry run", "prévia", "previa", "preview",
    "sem escrever", "sem atualizar", "nao atualizar", "não atualizar",
    "so mostrar", "só mostrar",
)


@dataclass(frozen=True)
class DispatchDecision:
    workflow: str
    stage: str
    confidence: str
    reason: str
    requires_approval: bool = False
    parameters: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parameters"] = self.parameters or {}
        return payload


@dataclass(frozen=True)
class SpecialistContract:
    """Immutable proof requirements for one completed specialist step.

    Files produced by an agent are only candidates.  Completion is granted
    exclusively when this declared SQLite-backed contract can be proven.
    """

    step: str
    required_artifacts: tuple[str, ...] = ()
    required_gates: tuple[str, ...] = ()
    validator: str = "harness_supervisor.contract"


@dataclass(frozen=True)
class SpecialistResult:
    status: str
    application_id: str | None
    run_id: str
    step: str
    source_revision_id: str | None
    positioning_revision_id: str | None
    artifact_ids: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    missing_gates: tuple[str, ...] = ()
    blocker_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "application_id": self.application_id,
            "run_id": self.run_id,
            "step": self.step,
            "source_revision_id": self.source_revision_id,
            "positioning_revision_id": self.positioning_revision_id,
            "artifact_ids": list(self.artifact_ids),
            "missing_artifacts": list(self.missing_artifacts),
            "missing_gates": list(self.missing_gates),
            "blocker_reason": self.blocker_reason,
        }


DEFAULT_SPECIALIST_CONTRACTS: dict[str, SpecialistContract] = {
    "fit-map": SpecialistContract(
        step="fit-map",
        required_gates=("fit_map_validated",),
    ),
    "cv": SpecialistContract(
        step="cv",
        required_artifacts=("cv",),
        required_gates=("cv_review_passed",),
    ),
    "cover-letter": SpecialistContract(
        step="cover-letter",
        required_artifacts=("cover_letter",),
    ),
    "feras": SpecialistContract(
        step="feras",
        required_artifacts=("feras",),
    ),
    "habilidades": SpecialistContract(
        step="habilidades",
        required_artifacts=("gupy_skills",),
    ),
}


class HarnessSupervisor:
    def __init__(self, root: Path | None = None, runner: SubprocessAgentRunner | None = None):
        self.root = root
        self.runner = runner or (SubprocessAgentRunner(root) if root else None)
        self.db = application_context_service.canonical_database(root=root)
        self.classifier = Classifier()
        self.router = Router()
        self.menu = MenuBuilder()
        self.executor = Executor(self.db)

    def process(self, message: str) -> dict:
        intent = self.classifier.classify(message)
        route = self.router.route(intent)
        if route["specialist"] is None:
            return {"intent": intent, "action": "clarify", "message": "Could not determine intent"}
        result = self.executor.run(str(route["specialist"]), {"message": message})
        return {"intent": intent, "action": route["next_step"], **result}

    def classify(self, message: str) -> DispatchDecision:
        raw_text = str(message or "").strip()
        text = " ".join(raw_text.split())
        lowered = text.casefold()
        if not text:
            return self._decision("help", "route", "high", "empty_message")

        pipeline_steps = self._requested_pipeline_steps(text)
        application_match = APPLICATION_ID_RE.search(text)
        run_match = RUN_ID_RE.search(text)
        if application_match and run_match and self._is_explicit_resume_request(text):
            parameters = {
                "application_id": application_match.group(1),
                "run_id": run_match.group(1),
            }
            repair_node = self._requested_cell_repair_node(text)
            if repair_node:
                parameters["repair_node"] = repair_node
            return self._decision(
                "resume",
                "resume",
                "high",
                "explicit_application_run_resume_request",
                parameters=parameters,
            )
        if (
            len(pipeline_steps) >= 2
            and self._is_pipeline_request(text)
            and (application_match or not GENERIC_URL_RE.search(text))
        ):
            parameters: dict[str, Any] = {"requested_steps": pipeline_steps}
            if application_match:
                parameters["application_id"] = application_match.group(1)
            return self._decision(
                "pipeline",
                "pipeline",
                "high",
                "composite_application_request",
                parameters=parameters,
            )

        # A continuation can deliberately omit the internal application ID.
        # The session binding and the persisted pipeline intent are the source
        # of truth for that ID and for the remaining requested stages.
        if "processe-a-vaga" in lowered or "processe a vaga" in lowered:
            return self._decision(
                "pipeline",
                "pipeline",
                "high",
                "bound_application_pipeline_continuation",
                parameters={"requested_steps": pipeline_steps},
            )

        if self._is_menu_request(lowered):
            return self._decision("menu", "menu", "high", "session_menu_request")

        selection = self._resolve_menu_selection(text)
        if selection:
            return self.classify(selection["prompt"])
        invalid_selection = self._invalid_menu_selection(text)
        if invalid_selection:
            return self._decision("invalid_menu_selection", "conversation", "high", invalid_selection)

        if self._is_runtime_introspection(lowered):
            return self._decision("runtime_introspection", "status", "high", "runtime_introspection_request")

        analysis_requested = any(
            token in lowered for token in ("avali", "analis", "aderencia", "aderência", "fit_map", "fit map")
        )

        job_match = LINKEDIN_JOB_RE.search(text)
        if job_match:
            return self._decision(
                "linkedin_job_intake", "intake", "high", "linkedin_job_url",
                parameters={"url": job_match.group(0)},
            )

        post_match = LINKEDIN_POST_RE.search(text)
        if post_match:
            company, role = self._company_role(raw_text)
            return self._decision(
                "linkedin_post_intake", "intake", "high", "linkedin_post_url",
                parameters={"url": post_match.group(0), "company": company, "role": role},
            )

        generic_url_match = GENERIC_URL_RE.search(text)
        if generic_url_match:
            company, role = self._company_role(raw_text)
            return self._decision(
                "external_url_intake", "intake",
                "high" if analysis_requested or text == generic_url_match.group(0) else "medium",
                "generic_job_url",
                parameters={"url": generic_url_match.group(0), "company": company, "role": role},
            )

        if any(token in lowered for token in ("vagas salvas", "saved jobs", "rastreador de vagas")):
            return self._decision("linkedin_saved_jobs", "intake", "high", "linkedin_saved_jobs_request")

        if any(
            phrase in lowered
            for phrase in (
                "continue o trabalho em andamento", "retomar trabalho em andamento",
                "retome o trabalho em andamento", "continue de onde parou",
            )
        ):
            return self._decision("resume", "resume", "high", "resume_active_workflow_request")

        if "heartbeat" in lowered or any(
            phrase in lowered for phrase in ("processar fila", "rodar fila", "executar fila", "processar candidaturas")
        ):
            return self._decision("applications_heartbeat", "orchestrate", "high", "queue_processing_request")

        if any(phrase in lowered for phrase in ("status das candidaturas", "status da fila", "applications status")):
            return self._decision("applications_status", "status", "high", "applications_status_request")

        notion_filter = self._notion_application_filter_request(text)
        if notion_filter:
            return self._decision(
                "notion_application_list", "query", "high", "notion_live_filtered_list_request",
                parameters={"filter_text": notion_filter},
            )

        if self._is_generic_application_list_request(lowered):
            return self._decision("notion_application_filter_guidance", "query", "high", "notion_filter_required")

        notion_match = NOTION_ID_RE.search(text)
        if notion_match and any(token in lowered for token in ("avali", "analis", "fit", "aderencia", "aderência")):
            return self._decision(
                "notion_job_analysis", "intake", "high", "notion_record_analysis",
                parameters={"record_id": int(notion_match.group(1))},
            )

        if "notion" in lowered and any(token in lowered for token in ("avali", "analis", "fit")):
            return self._decision("collect_notion_id", "conversation", "high", "notion_analysis_requires_record_id")

        if "notion" in lowered and (
            any(phrase in lowered for phrase in ("já existe", "ja existe", "registro prévio", "registro previo", "antes da escrita", "antes de escrever"))
            or "duplic" in lowered
        ):
            return self._decision(
                "notion_preflight",
                "notion-query",
                "high",
                "notion_duplicate_preflight_request",
                requires_approval=True,
            )

        if "linkedin" in lowered and any(token in lowered for token in ("avali", "analis", "vaga")):
            return self._decision("collect_linkedin_url", "conversation", "high", "linkedin_analysis_requires_url")

        if any(phrase in lowered for phrase in ("colar vaga", "colar uma vaga", "enviar vaga em texto")):
            return self._decision("collect_pasted_job", "conversation", "high", "pasted_job_requires_content")

        if len(raw_text) >= 500 and analysis_requested:
            company, role = self._company_role(raw_text)
            if company and role:
                return self._decision(
                    "pasted_job_intake", "intake", "high", "long_job_text_with_metadata",
                    parameters={"company": company, "role": role, "text": raw_text},
                )
            return self._decision(
                "pasted_job_missing_metadata", "intake", "high", "long_job_text_requires_company_and_role",
            )

        if any(token in lowered for token in ("email", "gmail")):
            return self._decision("email_draft", "email-draft", "high", "email_request", requires_approval=True)

        if "notion" in lowered and any(token in lowered for token in ("atualiz", "registre", "salve", "crie")):
            parameters: dict[str, Any] = {}
            if notion_match:
                parameters["record_id"] = int(notion_match.group(1))
            return self._decision(
                "notion_update", "notion-update", "high", "notion_write_request",
                requires_approval=True, parameters=parameters,
            )

        if application_match and self._is_delivery_status_question(lowered):
            return self._decision(
                "application_status",
                "status",
                "high",
                "scoped_delivery_status_request",
                parameters={"application_id": application_match.group(1)},
            )

        if self._is_meta_question_about_generated_outputs(lowered):
            return self._decision("generic_assistant", "chat", "high", "meta_question_about_previous_output")

        if any(token in lowered for token in ("curriculo", "currículo", "gerar cv", "adaptar cv")) or re.search(r"\bcv\b", lowered):
            return self._decision("cv", "cv", "high", "cv_request")

        if any(token in lowered for token in ("carta de apresentacao", "carta de apresentação", "cover letter")):
            return self._decision("cover_letter", "cover-letter", "high", "cover_letter_request")

        if any(token in lowered for token in ("feras", "me fale sobre voce", "me fale sobre você", "pitch")):
            return self._decision("feras", "feras", "high", "feras_request")

        if any(token in lowered for token in ("gupy", "mercado livre", "habilidades", "resumo ats")):
            return self._decision("habilidades", "habilidades", "high", "skills_request")

        if analysis_requested:
            return self._decision("fit_map", "fit-map", "medium", "job_analysis_request")

        return self._decision("generic_assistant", "chat", "low", "no_deterministic_route")

    @staticmethod
    def _notion_application_filter_request(text: str) -> str | None:
        match = re.search(
            r"\b(?:traga|liste|listar|listagem)\b.*?\b(?:vagas|registros|candidaturas)?\s*com\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        filter_text = match.group(1).strip()
        return filter_text or None

    @staticmethod
    def _is_generic_application_list_request(lowered: str) -> bool:
        return bool(re.search(r"\b(?:traga|liste|listar|listagem)\b.*\b(?:vagas|registros|candidaturas)\b", lowered))

    @staticmethod
    def _company_role(message: str) -> tuple[str | None, str | None]:
        company_match = re.search(r"(?im)^\s*empresa\s*:\s*(.+?)\s*$", message)
        role_match = re.search(r"(?im)^\s*(?:cargo|vaga)\s*:\s*(.+?)\s*$", message)
        company = company_match.group(1).strip() if company_match else None
        role = role_match.group(1).strip() if role_match else None
        return company, role

    @staticmethod
    def _is_meta_question_about_generated_outputs(lowered: str) -> bool:
        if not lowered:
            return False
        output_terms = (" cv ", "curriculo", "currículo", "docx", "arquivo", "arquivos", "versao", "versão", "versoes", "versões")
        diagnostic_terms = (
            "por que", "porque", "duvida", "dúvida", "como assim", "o que aconteceu",
            "acontecendo", "esta gerando", "está gerando", "gerando 2", "gerando duas",
            "duplic", "bug", "erro", "problema",
        )
        explicit_action_terms = (
            "faça", "faca", "gere", "gerar", "crie", "criar", "refaça", "refaca",
            "corrija", "corrigir", "ajuste", "ajustar", "atualize", "atualizar", "adapte", "adaptar",
        )
        padded = f" {lowered} "
        mentions_outputs = any(term in padded for term in output_terms)
        is_diagnostic = any(term in lowered for term in diagnostic_terms) or "?" in lowered
        requests_action = any(term in lowered for term in explicit_action_terms)
        return mentions_outputs and is_diagnostic and not requests_action

    def prepare_specialist(self, step: str, *, objective: str | None = None, extras: dict[str, Any] | None = None) -> dict[str, Any]:
        from career.services import multiagent as multiagent_service
        request_extras = dict(extras or {})
        application_id = str(request_extras.get("application_id") or "").strip()
        if not application_id:
            return {
                "status": "blocked",
                "step": step,
                "blocker_reason": "explicit_application_scope_required",
            }
        request = multiagent_service.write_request(
            step,
            application_id=application_id,
            objective=objective,
            extras=request_extras,
            database=self.db,
        )
        validation = multiagent_service.validate_request(step, request_path=self.root / request["request_json"] if self.root else None)
        result: dict[str, Any] = {
            "status": "prepared" if validation.get("status") == "ok" else "blocked",
            "step": step, "request": request, "validation": validation,
        }
        if step in {"notion-update", "email-draft"} and self.root:
            request_payload = read_json(self.root / request["versioned_request_json"])
            pending_action_path = (request_payload.get("extras") or {}).get("pending_action_path")
            approval = ApprovalStore(self.root).create(
                action=step,
                payload={
                    "request_id": request.get("request_id"),
                    "request_json": request.get("versioned_request_json"),
                    "request_md": request.get("versioned_request_md"),
                    "pending_action_path": pending_action_path,
                },
            )
            result["approval"] = {"approval_id": approval["approval_id"], "status": approval["status"]}
        return result

    def execute_approved_action(self, approval_id: str) -> dict[str, Any]:
        if not self.root:
            raise ValueError("HarnessSupervisor requires root to execute approved actions.")
        approvals = ApprovalStore(self.root)
        approval = approvals.get(approval_id)
        if approval.get("status") != "approved":
            return {"status": "blocked", "blocker_reason": "approval_not_approved", "approval": approval}
        if approval.get("action") == "storage-handoff":
            payload = approval.get("payload") or {}
            control_db_id = str(payload.get("control_db_id") or "").strip()
            owner = str(payload.get("owner") or "").strip()
            if not control_db_id or not owner:
                return {"status": "blocked", "blocker_reason": "storage_handoff_payload_missing", "approval": approval}
            self.db.prepare_authority_ledger_provisioning()
            storage_identity = self.db.authorize_storage_handoff(
                expected_control_db_id=control_db_id,
                new_owner=owner,
            )
            consumed = approvals.consume(approval_id)
            resumed = self.handle_message(
                str(payload.get("resume_message") or "processar fila de candidaturas"),
                channel="system",
                execute=True,
                max_per_run=payload.get("max_per_run"),
            )
            return {
                "status": "blocked",
                "approval": consumed,
                "storage_identity": storage_identity,
                "resumed": resumed,
            }
        pending_path = str((approval.get("payload") or {}).get("pending_action_path") or "")
        if not pending_path:
            return {"status": "blocked", "blocker_reason": "pending_action_path_missing", "approval": approval}
        result = ApprovedActionExecutor(self.root).execute(self.root / pending_path)
        consumed = approvals.consume(approval_id)
        return {"status": "completed", "approval": consumed, "result": result}

    def prepare_all_specialists(self, *, extras: dict[str, Any] | None = None) -> dict[str, Any]:
        from career.services import multiagent as multiagent_service
        return {
            "status": "prepared",
            "requests": [
                self.prepare_specialist(step, extras=extras)
                for step in multiagent_service.CONTRACTS
            ],
        }

    def execute_specialist(
        self,
        application_id: str,
        contract: SpecialistContract | None = None,
        *,
        run_id: str | None = None,
        objective: str | None = None,
        extras: dict[str, Any] | None = None,
        model: str | None = None,
        variant: str | None = None,
    ) -> SpecialistResult | dict[str, Any]:
        """Validate a scoped completion contract or execute the legacy runner path.

        The typed form is the authoritative Task 3.3 interface:
        ``execute_specialist(application_id, SpecialistContract(...))``.  The
        string-only form deliberately remains as a compatibility adapter for
        the existing conversation pipeline while it is migrated in later
        phases; it cannot be selected by a global pointer because its caller
        must still provide ``extras.application_id``.
        """
        if isinstance(contract, SpecialistContract):
            return self._execute_scoped_contract(
                application_id,
                contract,
                run_id=run_id,
            )
        return self._execute_pipeline_specialist(
            application_id,
            objective=objective,
            extras=extras,
            model=model,
            variant=variant,
        )

    def _execute_scoped_contract(
        self,
        application_id: str,
        contract: SpecialistContract,
        *,
        run_id: str | None,
    ) -> SpecialistResult:
        scoped_application_id = str(application_id or "").strip()
        resolved_run_id = str(run_id or "").strip() or f"supervisor_contract_{utc_now_iso()}"
        if not scoped_application_id:
            return SpecialistResult(
                status="blocked",
                application_id=None,
                run_id=resolved_run_id,
                step=contract.step,
                source_revision_id=None,
                positioning_revision_id=None,
                blocker_reason="explicit_application_scope_required",
            )

        applications = ApplicationRepository(self.db)
        try:
            application = applications.resolve(application_id=scoped_application_id)
        except (ApplicationNotFoundError, ValueError):
            return SpecialistResult(
                status="blocked",
                application_id=scoped_application_id,
                run_id=resolved_run_id,
                step=contract.step,
                source_revision_id=None,
                positioning_revision_id=None,
                blocker_reason="unknown_application",
            )

        analysis = AnalysisRepository(self.db)
        try:
            current_analysis = analysis.get_current(application.application_id)
        except StaleAnalysisError:
            return self._blocked_contract_result(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint,
                run_id=resolved_run_id,
                contract=contract,
                source_revision_id=None,
                positioning_revision_id=None,
                reason="stale_analysis_for_current_application_revision",
            )
        except ValueError:
            return self._blocked_contract_result(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint,
                run_id=resolved_run_id,
                contract=contract,
                source_revision_id=None,
                positioning_revision_id=None,
                reason="missing_current_fit_map_revision",
            )

        source_revision_id = current_analysis.revision_id
        positioning_revision_id = (
            current_analysis.positioning.revision_id
            if current_analysis.positioning is not None
            else None
        )
        artifacts = ArtifactRepository(self.db)
        artifact_ids: list[str] = []
        missing_artifacts: list[str] = []
        artifact_failure_reason: str | None = None
        for kind in contract.required_artifacts:
            candidates = self._current_artifact_candidates(
                application.application_id,
                kind,
                source_revision_id=source_revision_id,
                positioning_revision_id=positioning_revision_id,
            )
            if not candidates:
                missing_artifacts.append(kind)
                continue
            valid_candidate = None
            invalid_reason = None
            for artifact_id in candidates:
                validation = artifacts.validate_path(artifact_id)
                if validation.valid:
                    valid_candidate = artifact_id
                    break
                invalid_reason = validation.reason
            if valid_candidate is None:
                missing_artifacts.append(kind)
                artifact_failure_reason = artifact_failure_reason or invalid_reason or "invalid_artifact_provenance"
                continue
            artifact_ids.append(valid_candidate)

        gates = GateRepository(self.db)
        missing_gates = [
            gate
            for gate in contract.required_gates
            if not gates.is_satisfied(
                application.application_id,
                gate,
                revision_id=source_revision_id if gate in REVISION_BOUND_GATES else None,
            )
        ]
        if missing_artifacts or missing_gates:
            return self._blocked_contract_result(
                application_id=application.application_id,
                application_fingerprint=application.fingerprint,
                run_id=resolved_run_id,
                contract=contract,
                source_revision_id=source_revision_id,
                positioning_revision_id=positioning_revision_id,
                reason=(
                    artifact_failure_reason
                    if missing_artifacts and artifact_failure_reason
                    else "missing_required_artifact"
                    if missing_artifacts
                    else "missing_required_gate"
                ),
                missing_artifacts=tuple(missing_artifacts),
                missing_gates=tuple(missing_gates),
            )

        result = SpecialistResult(
            status="completed",
            application_id=application.application_id,
            run_id=resolved_run_id,
            step=contract.step,
            source_revision_id=source_revision_id,
            positioning_revision_id=positioning_revision_id,
            artifact_ids=tuple(artifact_ids),
        )
        self._record_contract_event(
            application_id=application.application_id,
            application_fingerprint=application.fingerprint,
            event="specialist_contract_completed",
            result=result,
            validator=contract.validator,
        )
        return result

    def _current_artifact_candidates(
        self,
        application_id: str,
        kind: str,
        *,
        source_revision_id: str,
        positioning_revision_id: str | None,
    ) -> tuple[str, ...]:
        rows = self.db.fetch_all(
            """SELECT version_id
                 FROM artifact_versions
                WHERE application_id = ?
                  AND kind = ?
                  AND source_revision_id = ?
                  AND COALESCE(positioning_revision_id, '') = COALESCE(?, '')
                ORDER BY created_at DESC, version_id DESC""",
            (application_id, kind, source_revision_id, positioning_revision_id),
        )
        return tuple(str(row["version_id"]) for row in rows)

    def _blocked_contract_result(
        self,
        *,
        application_id: str,
        application_fingerprint: str | None,
        run_id: str,
        contract: SpecialistContract,
        source_revision_id: str | None,
        positioning_revision_id: str | None,
        reason: str,
        missing_artifacts: tuple[str, ...] = (),
        missing_gates: tuple[str, ...] = (),
    ) -> SpecialistResult:
        result = SpecialistResult(
            status="blocked",
            application_id=application_id,
            run_id=run_id,
            step=contract.step,
            source_revision_id=source_revision_id,
            positioning_revision_id=positioning_revision_id,
            missing_artifacts=missing_artifacts,
            missing_gates=missing_gates,
            blocker_reason=reason,
        )
        self._record_contract_event(
            application_id=application_id,
            application_fingerprint=application_fingerprint,
            event="specialist_contract_blocked",
            result=result,
            validator=contract.validator,
        )
        return result

    def _record_contract_event(
        self,
        *,
        application_id: str,
        application_fingerprint: str | None,
        event: str,
        result: SpecialistResult,
        validator: str,
    ) -> None:
        result_payload = result.to_dict()
        result_hash = sha256_text(json.dumps(result_payload, sort_keys=True))
        self._record_contract_receipt(
            application_id=application_id,
            application_fingerprint=application_fingerprint,
            result=result,
            validator=validator,
            output_hash=result_hash,
        )
        WorkflowService(self.db).record_event(
            application_id,
            event,
            fingerprint=application_fingerprint,
            metadata={
                "application_id": application_id,
                "run_id": result.run_id,
                "step": result.step,
                "validator": validator,
                "reason": result.blocker_reason,
                "source_revision_id": result.source_revision_id,
                "positioning_revision_id": result.positioning_revision_id,
                "artifact_ids": list(result.artifact_ids),
                "missing_artifacts": list(result.missing_artifacts),
                "missing_gates": list(result.missing_gates),
                "result_hash": result_hash,
            },
        )

    def _record_contract_receipt(
        self,
        *,
        application_id: str,
        application_fingerprint: str | None,
        result: SpecialistResult,
        validator: str,
        output_hash: str,
    ) -> None:
        """Persist a non-gate receipt for contract evidence.

        ``GateRepository.record`` intentionally accepts only successful named
        gates.  A failed supervisor contract must still be durable evidence,
        so this writes a distinct ``specialist_contract`` receipt that cannot
        satisfy a production gate (consumers require ``result = 'passed'`` and
        a declared gate name).
        """
        created_at = utc_now_iso()
        contract_input = {
            "application_id": application_id,
            "step": result.step,
            "source_revision_id": result.source_revision_id,
            "positioning_revision_id": result.positioning_revision_id,
            "missing_artifacts": list(result.missing_artifacts),
            "missing_gates": list(result.missing_gates),
        }
        input_hash = sha256_text(json.dumps(contract_input, sort_keys=True))
        details = {
            **contract_input,
            "validator": validator,
            "reason": result.blocker_reason,
            "artifact_ids": list(result.artifact_ids),
        }
        with self.db.transaction(immediate=True) as conn:
            existing_run = conn.execute(
                "SELECT application_id FROM application_runs WHERE run_id = ?",
                (result.run_id,),
            ).fetchone()
            if existing_run is None:
                conn.execute(
                    """INSERT INTO application_runs
                           (run_id, application_id, graph_json, status,
                            contract_version, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.run_id,
                        application_id,
                        "{}",
                        result.status,
                        "supervisor-contract-v1",
                        created_at,
                        created_at,
                    ),
                )
            elif str(existing_run["application_id"]) != application_id:
                raise ValueError("contract run_id belongs to another application")

            node_id = "specialist_contract"
            node = conn.execute(
                "SELECT latest_attempt FROM cell_nodes WHERE run_id = ? AND node_id = ?",
                (result.run_id, node_id),
            ).fetchone()
            attempt = int(node["latest_attempt"] or 0) + 1 if node else 1
            if node is None:
                conn.execute(
                    """INSERT INTO cell_nodes
                           (run_id, node_id, status, requires_json, latest_attempt,
                            created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.run_id,
                        node_id,
                        result.status,
                        "[]",
                        attempt,
                        created_at,
                        created_at,
                    ),
                )
            else:
                conn.execute(
                    """UPDATE cell_nodes
                           SET latest_attempt = ?, status = ?, updated_at = ?
                         WHERE run_id = ? AND node_id = ?""",
                    (attempt, result.status, created_at, result.run_id, node_id),
                )
            conn.execute(
                """INSERT INTO validation_receipts
                       (receipt_id, application_id, run_id, node_id, attempt,
                        validator, gate, result, report_path, report_sha256,
                        details_json, created_at, input_hash, output_hash,
                        application_fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)""",
                (
                    f"contract_{uuid4().hex}",
                    application_id,
                    result.run_id,
                    node_id,
                    attempt,
                    validator,
                    "specialist_contract",
                    result.status,
                    json.dumps(details, sort_keys=True, separators=(",", ":")),
                    created_at,
                    input_hash,
                    output_hash,
                    application_fingerprint,
                ),
            )

    def _execute_pipeline_specialist(self, step: str, *, objective: str | None = None, extras: dict[str, Any] | None = None, model: str | None = None, variant: str | None = None) -> dict[str, Any]:
        if not self.root or not self.runner:
            raise ValueError("HarnessSupervisor requires root and runner to execute specialists.")
        application_id = str((extras or {}).get("application_id") or "").strip()
        if not application_id:
            return {
                "status": "blocked",
                "blocker_reason": "explicit_application_scope_required",
                "stage": step,
            }
        prepared = self.prepare_specialist(step, objective=objective, extras=extras)
        if prepared.get("validation", {}).get("status") != "ok":
            return prepared
        request = prepared["request"]
        request_json = self.root / request["versioned_request_json"]
        request_md = self.root / request["versioned_request_md"]
        request_payload = read_json(request_json)
        cellular_context = self._cellular_request_context(request_payload)
        if cellular_context:
            self._acquire_cellular_workspace()
        run_dir = request_json.parent
        config_path = self.root / ".career-state" / "applications_v2" / "config.json"
        config = read_json(config_path) if config_path.exists() else {}
        runner_key = "analysis_runner" if step == "fit-map" else "generation_runner"
        runner_config = config.get(runner_key, {"command": "hermes", "agent": "build", "timeout_minutes": 90})
        active_model = model or str(config.get("active_model") or "")
        active_variant = variant or str(config.get("active_variant") or "")
        instruction = "Leia o request anexado, execute somente esta etapa, grave os outputs permitidos e rode os comandos de validacao definidos no request."
        run_request = AgentRunRequest(
            stage=step, record_key=str(request["request_id"]), request_path=request_md,
            instruction=instruction, runner_config=runner_config,
            model=active_model, variant=active_variant,
        )
        output_patterns = SPECIALIST_OUTPUT_PATTERNS.get(step, [])
        if request_payload.get("application_id") and step in {"feras", "habilidades", "cover-letter"} and not cellular_context:
            output_patterns = [
                str(item)
                for item in request_payload.get("expected_outputs", [])
                if isinstance(item, str) and item.strip()
            ]
        if cellular_context:
            output_patterns = []
            for path in cellular_context["write_allowlist"]:
                resolved = Path(path).resolve()
                relative = str(resolved.relative_to(self.root.resolve()))
                output_patterns.append(f"{relative}/**" if resolved.is_dir() else relative)
        specialist_run = begin_specialist_run(self.root, run_dir, output_patterns)
        command = self.runner.build_command(run_request)
        result = self.runner.run(run_request)
        isolation = specialist_run.inspect()
        payload = {
            "stage": step, "request_id": request["request_id"], "command": command,
            "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
            "finished_at": utc_now_iso(), "run_dir": str(run_dir.relative_to(self.root)), "isolation": isolation,
        }
        specialist_run.finish(payload, isolation)
        persisted_outputs = _mirror_application_outputs(
            self.root, step, request_payload
        )
        if persisted_outputs:
            payload["persisted_outputs"] = persisted_outputs
        status = "completed"
        if result.returncode != 0 or isolation.get("status") != "ok":
            status = "blocked"
        elif SPECIALIST_OUTPUT_PATTERNS.get(step) and not isolation.get("allowed_changed_files"):
            status = "blocked"
            payload["blocker_reason"] = "specialist_produced_no_allowed_output"
        elif step in {"notion-update", "email-draft"}:
            status = "awaiting_approval"
        if self.should_auto_finalize_fit_map(
            step=step,
            status=status,
            enabled=self._fit_map_auto_finalize_enabled(),
            cellular=bool(cellular_context),
        ):
            postprocess = self._finalize_fit_map_pipeline(
                application_id=str(request_payload.get("application_id") or "").strip()
            )
            payload["postprocess"] = postprocess
            if postprocess.get("status") != "completed":
                status = "blocked"
                payload["blocker_reason"] = str(postprocess.get("blocker_reason") or "fit_map_finalize_failed")
        if step in {"notion-update", "email-draft"} and status == "awaiting_approval":
            auto_execution = self._maybe_auto_execute_approved_action(step, objective=objective, prepared=prepared)
            if auto_execution:
                payload["approval_execution"] = auto_execution
                status = "completed" if auto_execution.get("status") == "completed" else "blocked"
                if status == "blocked":
                    payload["blocker_reason"] = str(auto_execution.get("blocker_reason") or "approved_action_auto_execution_failed")
        contract = DEFAULT_SPECIALIST_CONTRACTS.get(step)
        if status == "completed" and contract is not None:
            contract_result = self._execute_scoped_contract(
                application_id,
                contract,
                run_id=str(request.get("request_id") or ""),
            )
            payload["contract"] = contract_result.to_dict()
            if contract_result.status != "completed":
                status = "blocked"
                payload["blocker_reason"] = str(
                    contract_result.blocker_reason or "specialist_contract_failed"
                )
        return {**prepared, "status": status, "execution": payload}

    @staticmethod
    def should_auto_finalize_fit_map(
        *, step: str, status: str, enabled: bool, cellular: bool
    ) -> bool:
        return step == "fit-map" and status == "completed" and enabled and not cellular

    def handle_message(self, message: str, *, channel: str = "cli", execute: bool = False, max_per_run: int | None = None, model: str | None = None, variant: str | None = None, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
        user_message = message
        pending_record = self._read_pending_input()
        # Pending requests created before session binding are legacy state. They
        # must never capture a new Telegram/Hermes turn and redirect it to an
        # unrelated question (for example, asking for a Notion ID while the
        # user is listing LinkedIn saved jobs). Session-bound requests remain
        # authoritative and keep the strict unresolved-input behavior below.
        if pending_record and not str(pending_record.get("session_id") or "").strip():
            self._clear_pending_input()
            pending_record = None
        if pending_record:
            pending_session = str(pending_record.get("session_id") or "").strip()
            current_session = str((runtime_context or {}).get("session_id") or "").strip()
            pending_application = str(pending_record.get("application_id") or "").strip()
            current_application = str((runtime_context or {}).get("application_id") or "").strip()
            if (
                (pending_session and pending_session != current_session)
                or (
                    pending_application
                    and current_application
                    and pending_application != current_application
                )
            ):
                # Keep the old session's pending question intact, but do not
                # let it hijack a different Telegram/Hermes session.
                pending_record = None
        pending = (
            self._resolve_pending_input(message, runtime_context=runtime_context)
            if pending_record
            else None
        )
        invalid_pending_selection = self._invalid_pending_record_selection(message)
        if invalid_pending_selection:
            return {
                "status": "awaiting_input",
                "channel": channel,
                "message": user_message,
                "executed": False,
                "result": {
                    "status": "awaiting_input",
                    "kind": "notion_record_selection",
                    "blocker_reason": invalid_pending_selection,
                    "display_text": "Essa ID não estava na última lista. Responda com uma das IDs exibidas.",
                },
            }
        if pending_record and pending is None:
            return {
                "status": "awaiting_input",
                "channel": channel,
                "message": user_message,
                "executed": False,
                "result": {
                    "status": "awaiting_input",
                    "kind": "input_request",
                    "input_kind": pending_record.get("input_kind"),
                    "blocker_reason": "pending_input_unresolved",
                    "display_text": pending_record.get("display_text")
                    or "A resposta não corresponde à pergunta pendente. Responda de acordo com a pergunta exibida.",
                },
            }
        if pending:
            if pending.get("input_kind") == "confirmation":
                self._clear_pending_input()
                return {
                    "status": "completed",
                    "channel": channel,
                    "message": user_message,
                    "executed": True,
                    "decision": self._decision(
                        "confirmation", "conversation", "high", "pending_confirmation"
                    ).to_dict(),
                    "result": {
                        "status": "completed",
                        "kind": "confirmation",
                        "answer": bool(pending.get("answer")),
                        "application_id": pending.get("application_id"),
                        "turn_id": pending.get("turn_id"),
                    },
                }
            message = str(pending["message"])
        selection = self._resolve_menu_selection(message)
        original_message = user_message
        if selection:
            input_request = self._menu_input_request(selection)
            if input_request:
                input_request = self._pending_request_for_context(
                    input_request, runtime_context, channel=channel
                )
                self._write_pending_input(input_request)
                return {
                    "status": "awaiting_input", "channel": channel, "message": original_message,
                    "decision": self._decision("collect_input", "conversation", "high", "menu_selection_requires_input").to_dict(),
                    "menu_selection": selection, "executed": False, "result": input_request,
                }
            message = str(selection["prompt"])
        if execute:
            self._record_session_intent(runtime_context, message, channel=channel)
        decision = self.classify(message)
        envelope: dict[str, Any] = {"status": "routed", "channel": channel, "message": original_message, "decision": decision.to_dict(), "executed": False}
        if selection:
            envelope["menu_selection"] = selection
        if pending:
            envelope["pending_input"] = pending
        if not execute:
            return envelope
        workflow = decision.workflow
        try:
            if workflow == "menu":
                self._clear_pending_input()
                envelope["result"] = self._build_session_menu()
            elif workflow in {"collect_notion_id", "collect_linkedin_url", "collect_pasted_job"}:
                input_kind = {"collect_notion_id": "notion_id", "collect_linkedin_url": "linkedin_job_url", "collect_pasted_job": "pasted_job"}[workflow]
                display_text = {
                    "notion_id": "Qual é o número da vaga no Notion? Pode responder somente com o número.",
                    "linkedin_job_url": "Envie a URL da vaga no LinkedIn.",
                    "pasted_job": "Cole a vaga com duas linhas no início: Empresa: nome e Cargo: nome. Depois inclua a descrição completa.",
                }[input_kind]
                request = {"status": "awaiting_input", "kind": "input_request", "input_kind": input_kind, "display_text": display_text}
                request = self._pending_request_for_context(
                    request, runtime_context, channel=channel
                )
                self._write_pending_input(request)
                envelope["result"] = request
            elif workflow == "resume":
                resume_parameters = decision.parameters or {}
                envelope["result"] = self._resume_and_continue(
                    message,
                    model=model,
                    variant=variant,
                    application_id=str(
                        resume_parameters.get("application_id")
                        or self._session_application_id(runtime_context, channel=channel)
                        or ""
                    ),
                    run_id=str(resume_parameters.get("run_id") or ""),
                    repair_node=str(resume_parameters.get("repair_node") or ""),
                )
            elif workflow == "pipeline":
                parameters = decision.parameters or {}
                pipeline_application_id = str(parameters.get("application_id") or "").strip()
                if pipeline_application_id:
                    self._bind_session_to_application(
                        runtime_context, pipeline_application_id, channel=channel
                    )
                requested_steps = list(parameters.get("requested_steps") or [])
                if not requested_steps:
                    requested_steps = [
                        str(step)
                        for step in (
                            self._session_pipeline_intent(
                                runtime_context, channel=channel
                            ).get("requested_steps")
                            or []
                        )
                        if str(step).strip()
                    ]
                envelope["result"] = self._execute_pipeline_request(
                    message,
                    requested_steps=requested_steps,
                    application_id=pipeline_application_id
                    or self._session_application_id(runtime_context, channel=channel),
                    model=model,
                    variant=variant,
                    runtime_context=runtime_context,
                    channel=channel,
                )
            elif workflow == "applications_status":
                from career.services import applications_v2 as applications_service
                envelope["result"] = applications_service.heartbeat_status()
            elif workflow == "application_status":
                envelope["result"] = self._scoped_delivery_status(
                    str((decision.parameters or {}).get("application_id") or "").strip()
                )
            elif workflow == "notion_application_filter_guidance":
                from career.services import notion as notion_service
                token, database_id = notion_service.notion_config()
                guidance = notion_service.live_application_filter_guidance(token, database_id)
                statuses = ", ".join(guidance.get("available_statuses") or []) or "indisponíveis"
                request = {
                    "status": "awaiting_input",
                    "kind": "notion_application_filter",
                    "input_kind": "notion_application_filter",
                    "display_text": f"Informe pelo menos um filtro. Exemplo: Etapa Funil Fila Agente. Status disponíveis: {statuses}.",
                }
                request = self._pending_request_for_context(
                    request, runtime_context, channel=channel
                )
                self._write_pending_input(request)
                envelope["result"] = request
            elif workflow == "notion_application_list":
                from career.services import notion as notion_service
                token, database_id = notion_service.notion_config()
                result = notion_service.query_live_applications(
                    token,
                    database_id,
                    str((decision.parameters or {}).get("filter_text") or ""),
                )
                record_ids = [int(item["record_id"]) for item in result.get("records") or [] if isinstance(item.get("record_id"), int)]
                self._write_pending_input(
                    self._pending_request_for_context(
                        {"input_kind": "notion_record_selection", "record_ids": record_ids},
                        runtime_context,
                        channel=channel,
                    )
                )
                envelope["result"] = {
                    "status": "completed",
                    "kind": "notion_application_list",
                    "display_text": notion_service.format_application_table(result),
                    "count": result["count"],
                    "filters": result["filters"],
                }
            elif workflow == "applications_heartbeat":
                from career.services import applications_v2 as applications_service
                envelope["result"] = applications_service.run_heartbeat(
                    applications_service.HeartbeatV2Options(max_per_run=max_per_run, run_agent=True, dry_run=False, model=model, variant=variant, cellular=True)
                )
            elif workflow == "notion_job_analysis":
                from career.services import agent_guard as agent_guard_service
                record_id = int((decision.parameters or {})["record_id"])
                intake_result = agent_guard_service.evaluate_notion(record_id)
                self._bind_session_to_intake(runtime_context, intake_result, channel=channel)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist("fit-map", objective=f"Avaliar vaga Notion {record_id}", extras={"application_id": intake_result.get("application_id")}, model=model, variant=variant),
                )
            elif workflow == "notion_preflight":
                application_id = self._session_application_id(runtime_context, channel=channel)
                envelope["result"] = self._notion_duplicate_preflight(application_id)
            elif workflow == "linkedin_job_intake":
                from career.services import intake as intake_service
                linkedin_url = str((decision.parameters or {})["url"])
                hints = self._saved_job_metadata_hints(selection)
                existing_application_id = self._resolve_linkedin_application_id(linkedin_url)
                intake_result = intake_service.from_linkedin_job(
                    linkedin_url,
                    metadata_hints=hints,
                    application_id=existing_application_id,
                    database=self.db,
                )
                self._bind_session_to_intake(runtime_context, intake_result, channel=channel)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist("fit-map", objective=message, extras={"application_id": intake_result.get("application_id")}, model=model, variant=variant),
                )
            elif workflow == "linkedin_post_intake":
                from career.services import intake as intake_service
                parameters = decision.parameters or {}
                if not parameters.get("company") or not parameters.get("role"):
                    envelope["status"] = "blocked"
                    envelope["blocker_reason"] = "linkedin_post_requires_company_and_role"
                    return envelope
                intake_result = intake_service.from_linkedin_post(url=str(parameters["url"]), company=str(parameters["company"]), role=str(parameters["role"]))
                self._bind_session_to_intake(runtime_context, intake_result, channel=channel)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist("fit-map", objective=message, extras={"application_id": intake_result.get("application_id")}, model=model, variant=variant),
                )
            elif workflow == "external_url_intake":
                from career.services import intake as intake_service
                parameters = decision.parameters or {}
                intake_result = intake_service.from_url(url=str(parameters["url"]), company=str(parameters["company"]) if parameters.get("company") else None, role=str(parameters["role"]) if parameters.get("role") else None)
                self._bind_session_to_intake(runtime_context, intake_result, channel=channel)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist("fit-map", objective=message, extras={"application_id": intake_result.get("application_id")}, model=model, variant=variant),
                )
            elif workflow == "pasted_job_intake":
                from career.services import intake as intake_service
                parameters = decision.parameters or {}
                intake_result = intake_service.from_paste(company=str(parameters["company"]), role=str(parameters["role"]), text=str(parameters["text"]))
                self._bind_session_to_intake(runtime_context, intake_result, channel=channel)
                envelope["result"] = self._pipeline_result(
                    intake=intake_result,
                    specialist=self.execute_specialist("fit-map", objective=f"Analisar {parameters['role']} na {parameters['company']}", extras={"application_id": intake_result.get("application_id")}, model=model, variant=variant),
                )
            elif workflow == "pasted_job_missing_metadata":
                envelope["status"] = "blocked"
                envelope["blocker_reason"] = "pasted_job_requires_empresa_and_cargo_headers"
                return envelope
            elif workflow == "linkedin_saved_jobs":
                envelope["result"] = self._extract_linkedin_saved_jobs()
            elif workflow == "runtime_introspection":
                from career.services import project as project_service
                envelope["result"] = project_service.hermes_runtime_snapshot()
                if isinstance(envelope["result"], dict):
                    stale = self._stale_active_intake_summary()
                    if stale:
                        envelope["result"]["stale_active_intake"] = stale
            elif workflow == "invalid_menu_selection":
                stale = self._stale_active_intake_summary()
                display_text = "Esse número não existe no menu atual. Responda com um número listado ou peça `menu` para recarregar."
                if stale:
                    display_text += f"\n\nHá um trabalho anterior salvo ({stale.get('role') or '-'} | {stale.get('company') or '-'}) mas ele parece antigo; se quiser retomá-lo, diga `continue o trabalho em andamento`."
                envelope["result"] = {"status": "blocked", "kind": "invalid_menu_selection", "blocker_reason": "menu_selection_not_found", "display_text": display_text}
            elif workflow in {"fit_map", "cv", "cover_letter", "feras", "habilidades", "notion_update", "email_draft"}:
                step = {"fit_map": "fit-map", "cover_letter": "cover-letter", "notion_update": "notion-update", "email_draft": "email-draft"}.get(workflow, workflow)
                envelope["result"] = self.execute_specialist(step, objective=message, extras=self._specialist_extras(workflow, decision.parameters, runtime_context, channel=channel), model=model, variant=variant)
            elif workflow == "generic_assistant":
                if self._is_operational_message(message):
                    application_id = self._session_application_id(runtime_context, channel=channel)
                    if application_id:
                        intent = self._session_pipeline_intent(runtime_context, channel=channel)
                        requested_steps = [
                            str(step)
                            for step in (intent.get("requested_steps") or [])
                            if str(step).strip()
                        ]
                        requested_steps = requested_steps or self._requested_pipeline_steps(message)
                        if requested_steps:
                            envelope["result"] = self._execute_pipeline_request(
                                message,
                                requested_steps=requested_steps,
                                application_id=application_id,
                                model=model,
                                variant=variant,
                                runtime_context=runtime_context,
                                channel=channel,
                            )
                        else:
                            envelope["result"] = self._resume_and_continue(
                                message,
                                model=model,
                                variant=variant,
                                application_id=application_id,
                            )
                    else:
                        envelope["result"] = {
                            "status": "blocked",
                            "blocker_reason": "application_session_not_bound",
                            "display_text": "Não encontrei uma candidatura vinculada a esta sessão.",
                        }
                else:
                    envelope["result"] = self._run_generic_message(message, model=model)
            else:
                envelope["status"] = "blocked"
                envelope["blocker_reason"] = "no_deterministic_route"
                return envelope
        except ValueError as exc:
            if not self._is_storage_handoff_required(exc):
                raise
            envelope["result"] = self.prepare_authority_handoff(
                application_id=self._session_application_id(runtime_context, channel=channel),
                blocker=str(exc),
                max_per_run=max_per_run,
            )
        except ValidationFailure as exc:
            self._clear_menu_state()
            envelope["result"] = {"status": "blocked", "kind": "validation_failure", "blocker_reason": "workflow_validation_failed", "display_text": str(exc)}
        envelope["result"] = self._decorate_result_payload(envelope.get("result"))
        self._sync_menu_state_for_result(envelope.get("result"))
        result_status = envelope.get("result", {}).get("status") if isinstance(envelope.get("result"), dict) else None
        envelope["executed"] = result_status != "awaiting_input"
        envelope["status"] = result_status if result_status in {"blocked", "awaiting_input", "awaiting_approval"} else "completed"
        return envelope

    @staticmethod
    def _pipeline_result(*, intake: dict[str, Any], specialist: dict[str, Any]) -> dict[str, Any]:
        specialist_status = str(specialist.get("status") or "")
        status = specialist_status if specialist_status in {"blocked", "awaiting_approval"} else "completed"
        return {"status": status, "intake": intake, "specialist": specialist}

    def _execute_pipeline_request(
        self,
        message: str,
        *,
        requested_steps: list[str],
        application_id: str | None,
        model: str | None,
        variant: str | None,
        runtime_context: dict[str, Any] | None,
        channel: str,
    ) -> dict[str, Any]:
        """Advance one scoped package step at a time without changing vacancy identity."""
        from career.services import intake as intake_service

        scoped_id = str(application_id or "").strip()
        if not scoped_id:
            return {
                "status": "blocked",
                "blocker_reason": "explicit_application_scope_required",
                "requested_steps": requested_steps,
            }
        try:
            resume = intake_service.resume(application_id=scoped_id, database=self.db)
        except Exception as exc:
            return {
                "status": "blocked",
                "application_id": scoped_id,
                "blocker_reason": "application_resume_failed",
                "error": str(exc)[:500],
                "requested_steps": requested_steps,
            }
        next_step = str(resume.get("next_required_step") or "")
        stages: list[dict[str, Any]] = []
        if "fill_fit_map" in next_step or "draft" in next_step or next_step in {"fit_map", "analyze_fit"}:
            stages.append(
                self.execute_specialist(
                    "fit-map",
                    objective=message,
                    extras={"application_id": scoped_id},
                    model=model,
                    variant=variant,
                )
            )
        elif next_step in {"build_cv", "cv", "generate_cv"} and "cv" in requested_steps:
            stages.append(
                self.execute_specialist(
                    "cv",
                    objective=message,
                    extras={"application_id": scoped_id},
                    model=model,
                    variant=variant,
                )
            )
        elif next_step in {"deliver_cv_onedrive", "onedrive"} and "onedrive" in requested_steps:
            stages.append(self._deliver_scoped_cv(scoped_id))
        elif next_step in {"sync_notion", "notion"} and "notion" in requested_steps:
            stages.append(
                self.execute_specialist(
                    "notion-update",
                    objective=message,
                    extras=self._specialist_extras(
                        "notion_update",
                        {},
                        runtime_context,
                        channel=channel,
                    )
                    or {"application_id": scoped_id},
                    model=model,
                    variant=variant,
                )
            )
        else:
            return {
                "status": "blocked",
                "application_id": scoped_id,
                "resume": resume,
                "requested_steps": requested_steps,
                "stages": [],
                "blocker_reason": "no_pipeline_stage_executed",
            }
        stage_status = str(stages[-1].get("status") or "blocked") if stages else "blocked"
        return {
            "status": "completed" if stage_status in {"completed", "awaiting_approval"} else "blocked",
            "application_id": scoped_id,
            "resume": resume,
            "requested_steps": requested_steps,
            "stages": stages,
        }

    def _deliver_scoped_cv(self, application_id: str) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        try:
            application = ApplicationRepository(self.db).resolve(application_id=application_id)
        except ApplicationNotFoundError:
            return {"status": "blocked", "blocker_reason": "application_not_found", "application_id": application_id}
        artifact_value = str(application.cv_path or "").strip()
        if not artifact_value:
            return {
                "status": "blocked",
                "application_id": application_id,
                "blocker_reason": "cv_artifact_missing",
            }
        artifact = Path(artifact_value)
        if not artifact.is_absolute():
            artifact = (self.root / artifact).resolve()
        else:
            artifact = artifact.resolve()
        try:
            artifact.relative_to((self.root / "outputs").resolve())
        except ValueError:
            return {
                "status": "blocked",
                "application_id": application_id,
                "blocker_reason": "cv_artifact_outside_outputs",
            }
        command = [
            "npm", "run", "cv:deliver", "--",
            "--application-id", application_id,
            "--artifact", str(artifact.relative_to(self.root)),
        ]
        completed = subprocess.run(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15 * 60,
        )
        return {
            "status": "completed" if completed.returncode == 0 else "blocked",
            "application_id": application_id,
            "artifact": str(artifact.relative_to(self.root)),
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            **({"blocker_reason": "cv_delivery_failed"} if completed.returncode else {}),
        }

    def _notion_duplicate_preflight(self, application_id: str | None) -> dict[str, Any]:
        """Check live Notion for an existing record before any write path."""
        scoped_id = str(application_id or "").strip()
        if not scoped_id:
            return {
                "status": "blocked",
                "blocker_reason": "application_session_not_bound",
                "display_text": "Não encontrei uma candidatura vinculada a esta sessão.",
            }
        try:
            application = ApplicationRepository(self.db).resolve(application_id=scoped_id)
            from career.services import notion as notion_service

            token, database_id = notion_service.notion_config()
            candidates = notion_service.find_duplicate_application_candidates(
                token,
                database_id,
                company=application.company,
                role=application.role,
                source_url=application.source_url or "",
            )
        except Exception as exc:
            return {
                "status": "blocked",
                "application_id": scoped_id,
                "blocker_reason": "notion_duplicate_preflight_failed",
                "error": str(exc)[:500],
            }
        if candidates:
            return {
                "status": "blocked",
                "application_id": scoped_id,
                "blocker_reason": "notion_duplicate_found",
                "candidates": candidates[:5],
                "display_text": "Encontrei registro(s) semelhante(s) no Notion. Nenhuma escrita foi executada; confira os IDs retornados.",
            }
        return {
            "status": "awaiting_approval",
            "application_id": scoped_id,
            "kind": "notion_preflight_clear",
            "display_text": "Não encontrei registro prévio no Notion. A escrita está liberada para confirmação explícita.",
        }

    @staticmethod
    def _is_storage_handoff_required(error: ValueError) -> bool:
        return "physical control database copy is not authoritative" in str(error).casefold()

    @staticmethod
    def _requested_pipeline_steps(message: str) -> list[str]:
        lowered = str(message or "").casefold()
        terms = (
            ("cv", "cv"),
            ("currículo", "cv"),
            ("curriculo", "cv"),
            ("onedrive", "onedrive"),
            ("one drive", "onedrive"),
            ("notion", "notion"),
            ("carta de apresentação", "cover-letter"),
            ("carta de apresentacao", "cover-letter"),
            ("feras", "feras"),
            ("habilidades", "habilidades"),
        )
        steps: list[str] = []
        for term, step in terms:
            if term in lowered and step not in steps:
                steps.append(step)
        return steps

    @staticmethod
    def _is_operational_message(message: str) -> bool:
        lowered = str(message or "").casefold()
        operational_terms = (
            "onedrive", "notion", "entregou cv", "entregou o cv", "delivery",
            "application_id", "application id", "fit_map", "fit map", "vaga",
            "processe-a-vaga", "processe a vaga", "continue o trabalho",
            "retomar o trabalho", "faça isso", "faca isso",
        )
        return any(term in lowered for term in operational_terms)

    @staticmethod
    def _is_delivery_status_question(message: str) -> bool:
        lowered = str(message or "").casefold()
        return (
            "entregou cv" in lowered
            or "entregou o cv" in lowered
            or "onedrive" in lowered and any(term in lowered for term in ("entreg", "arquivo", "está", "esta"))
            or "delivery" in lowered
        )

    def _scoped_delivery_status(self, application_id: str) -> dict[str, Any]:
        if not application_id:
            return {"status": "blocked", "blocker_reason": "explicit_application_scope_required"}
        try:
            ApplicationRepository(self.db).resolve(application_id=application_id)
        except ApplicationNotFoundError:
            return {
                "status": "blocked",
                "application_id": application_id,
                "blocker_reason": "application_not_found",
            }
        row = self.db.fetch_one(
            """SELECT delivery_id, artifact_version_id, channel, status, report_path, delivered_at
                 FROM deliveries
                WHERE application_id = ?
                  AND channel = 'onedrive'
                  AND status IN ('delivered', 'validated')
                ORDER BY delivered_at DESC, delivery_id DESC
                LIMIT 1""",
            (application_id,),
        )
        if row is None:
            return {
                "status": "blocked",
                "application_id": application_id,
                "blocker_reason": "delivery_receipt_missing",
                "display_text": "Não há receipt de entrega do OneDrive para esta candidatura.",
            }
        return {
            "status": "completed",
            "application_id": application_id,
            "delivery": dict(row),
        }

    @staticmethod
    def _is_pipeline_request(message: str) -> bool:
        lowered = str(message or "").casefold()
        action_terms = (
            "crie", "criar", "gere", "gerar", "envie", "enviar", "execute",
            "prossiga", "continue", "retome", "retomar", "faça", "faca",
        )
        return any(term in lowered for term in action_terms) and "?" not in lowered

    @staticmethod
    def _is_explicit_resume_request(message: str) -> bool:
        lowered = str(message or "").casefold()
        return bool(
            re.search(r"\b(?:retom\w*|continu\w*|prossig\w*|repar\w*|repair)\b", lowered)
            or "mesmo run" in lowered
            or "mesmo fluxo" in lowered
        )

    @staticmethod
    def _requested_cell_repair_node(message: str) -> str | None:
        match = CELL_REPAIR_NODE_RE.search(str(message or ""))
        return match.group(1).casefold() if match else None

    def _record_session_intent(
        self,
        runtime_context: dict[str, Any] | None,
        message: str,
        *,
        channel: str,
    ) -> None:
        if not self.root or not runtime_context:
            return
        application_id = self._session_application_id(runtime_context, channel=channel)
        if not application_id:
            return
        runtime = str(runtime_context.get("runtime") or channel or "cli")
        session_id = str(runtime_context.get("session_id") or "").strip()
        if not session_id:
            return
        profile_id = str(runtime_context.get("profile_id") or "").strip() or None
        effective_profile = profile_id or (
            application_context_service.profile_id_from_env()
            if runtime == "hermes"
            else "default"
        )
        PipelineIntentStore(self.root).bind(
            application_id=application_id,
            session_key=application_context_service.session_key(
                runtime=runtime,
                profile_id=effective_profile,
                session_id=session_id,
            ),
            requested_steps=self._requested_pipeline_steps(message),
        )

    def _session_pipeline_intent(
        self, runtime_context: dict[str, Any] | None, *, channel: str
    ) -> dict[str, Any]:
        if not self.root or not runtime_context:
            return {}
        runtime = str(runtime_context.get("runtime") or channel or "cli")
        profile_id = str(runtime_context.get("profile_id") or "").strip() or None
        effective_profile = profile_id or (
            application_context_service.profile_id_from_env()
            if runtime == "hermes"
            else "default"
        )
        session_id = str(runtime_context.get("session_id") or "").strip()
        if not session_id:
            return {}
        return PipelineIntentStore(self.root).resolve(
            application_context_service.session_key(
                runtime=runtime,
                profile_id=effective_profile,
                session_id=session_id,
            )
        ) or {}

    def prepare_authority_handoff(
        self,
        *,
        application_id: str | None,
        blocker: str,
        max_per_run: int | None = None,
    ) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        control_db_id = str(os.environ.get("CAREER_CONTROL_DB_ID") or "").strip()
        owner = application_context_service.workspace_owner_from_env()
        if not control_db_id:
            return {
                "status": "blocked",
                "blocker_reason": "control_database_identity_missing",
                "display_text": "O handoff exige CAREER_CONTROL_DB_ID configurado no runtime.",
            }
        physical_identity = self.db.physical_storage_identity()
        idempotency_key = f"{control_db_id}:{physical_identity}:{owner}"
        approval = ApprovalStore(self.root).create_idempotent(
            action="storage-handoff",
            idempotency_key=idempotency_key,
            payload={
                "kind": "storage_handoff",
                "control_db_id": control_db_id,
                "owner": owner,
                "application_id": application_id,
                "physical_storage_identity": physical_identity,
                "blocker": blocker,
                "resume_message": "processar fila de candidaturas",
                "max_per_run": max_per_run,
            },
        )
        return {
            "status": "awaiting_approval",
            "kind": "storage_handoff",
            "blocker_reason": "storage_handoff_required",
            "display_text": (
                "A cópia física do banco precisa ser reautorizada. "
                "Aprovação única necessária para executar o authorize-handoff "
                f"com owner {owner}; depois o pipeline será retomado."
            ),
            "approval": {
                "approval_id": approval["approval_id"],
                "status": approval["status"],
                "action": approval["action"],
            },
            "application_id": application_id,
        }

    def _bind_session_to_intake(self, runtime_context: dict[str, Any] | None, intake_result: dict[str, Any], *, channel: str) -> None:
        self._bind_session_to_application(
            runtime_context,
            str(intake_result.get("application_id") or "").strip(),
            channel=channel,
        )

    def _bind_session_to_application(
        self,
        runtime_context: dict[str, Any] | None,
        application_id: str,
        *,
        channel: str,
    ) -> None:
        if not self.root or not runtime_context or not application_id:
            return
        runtime = str(runtime_context.get("runtime") or channel or "cli")
        session_id = str(runtime_context.get("session_id") or "").strip()
        if not session_id:
            return
        profile_id = str(runtime_context.get("profile_id") or "").strip() or None
        application_context_service.register_session(runtime=runtime, profile_id=profile_id, session_id=session_id, application_id=application_id, channel=channel, database=self.db)
        effective_profile = profile_id or (application_context_service.profile_id_from_env() if runtime == "hermes" else "default")
        PipelineIntentStore(self.root).bind(
            application_id=application_id,
            session_key=application_context_service.session_key(
                runtime=runtime,
                profile_id=effective_profile,
                session_id=session_id,
            ),
        )

    def _pending_request_for_context(
        self,
        request: dict[str, Any],
        runtime_context: dict[str, Any] | None,
        *,
        channel: str,
    ) -> dict[str, Any]:
        payload = dict(request)
        if not runtime_context:
            return payload
        session_id = str(runtime_context.get("session_id") or "").strip()
        if session_id:
            payload["session_id"] = session_id
        application_id = self._session_application_id(runtime_context, channel=channel)
        if application_id:
            payload["application_id"] = application_id
        turn_id = str(runtime_context.get("turn_id") or "").strip()
        if turn_id:
            payload["turn_id"] = turn_id
        return payload

    def _resume_and_continue(
        self,
        message: str,
        *,
        model: str | None,
        variant: str | None,
        application_id: str | None,
        run_id: str | None = None,
        repair_node: str | None = None,
    ) -> dict[str, Any]:
        from career.services import intake as intake_service
        application_id = str(application_id or "").strip()
        if not application_id:
            return {
                "status": "blocked",
                "blocker_reason": "explicit_application_scope_required",
            }
        run_id = str(run_id or "").strip()
        if run_id:
            return self._resume_cellular_run(
                application_id=application_id,
                run_id=run_id,
                repair_node=str(repair_node or "").strip() or None,
                reason=message,
            )
        resume = intake_service.resume(application_id=application_id, database=self.db)
        next_step = str(resume.get("next_required_step") or "")
        if "fill_fit_map" in next_step or "draft" in next_step:
            specialist = self.execute_specialist(
                "fit-map",
                objective=message,
                extras={"application_id": application_id},
                model=model,
                variant=variant,
            )
            return {"status": "blocked" if specialist.get("status") == "blocked" else "completed", "resume": resume, "specialist": specialist}
        return resume

    def _resume_cellular_run(
        self,
        *,
        application_id: str,
        run_id: str,
        repair_node: str | None,
        reason: str,
    ) -> dict[str, Any]:
        """Resume one explicitly scoped cellular run through the official CLI."""
        run_row = self.db.fetch_one(
            "SELECT application_id FROM application_runs WHERE run_id = ?",
            (run_id,),
        )
        if run_row is None:
            return {
                "status": "blocked",
                "application_id": application_id,
                "run_id": run_id,
                "blocker_reason": "run_not_found",
            }
        if str(run_row["application_id"]) != application_id:
            return {
                "status": "blocked",
                "application_id": application_id,
                "run_id": run_id,
                "blocker_reason": "run_application_mismatch",
            }
        action = "repair" if repair_node else "run"
        command = [
            "npm",
            "run",
            f"applications:{action}",
            "--",
            "--application-id",
            application_id,
            "--run-id",
            run_id,
        ]
        if action == "run":
            # A persisted cellular run can be ready on an external node.  A
            # plain applications:run only executes deterministic handlers and
            # would report readiness forever without invoking the agent.
            command.append("--run-agent")
        if repair_node:
            command.extend(["--node", repair_node, "--reason", reason])
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90 * 60,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "blocked",
                "application_id": application_id,
                "run_id": run_id,
                "blocker_reason": "cellular_resume_timeout",
                "command": command,
            }
        output = (completed.stdout or "").strip()
        error = (completed.stderr or "").strip()
        return {
            "status": "completed" if completed.returncode == 0 else "blocked",
            "application_id": application_id,
            "run_id": run_id,
            "action": action,
            "node": repair_node,
            "command": command,
            "returncode": completed.returncode,
            "stdout": output[-4000:],
            "stderr": error[-4000:],
            **({"blocker_reason": "cellular_resume_failed"} if completed.returncode else {}),
        }

    def _session_application_id(self, runtime_context: dict[str, Any] | None, *, channel: str) -> str | None:
        if not self.root or not runtime_context:
            return None
        session_id = str(runtime_context.get("session_id") or "").strip()
        if not session_id:
            return None
        runtime = str(runtime_context.get("runtime") or channel or "cli")
        profile_id = str(runtime_context.get("profile_id") or "").strip() or None
        application_id = application_context_service.resolve_session(runtime=runtime, session_id=session_id, profile_id=profile_id, database=self.db)
        if application_id:
            return application_id
        effective_profile = profile_id or (application_context_service.profile_id_from_env() if runtime == "hermes" else "default")
        intent = PipelineIntentStore(self.root).resolve(
            application_context_service.session_key(
                runtime=runtime,
                profile_id=effective_profile,
                session_id=session_id,
            )
        )
        return str(intent.get("application_id")) if intent else None

    def _specialist_extras(self, workflow: str, parameters: dict[str, Any] | None, runtime_context: dict[str, Any] | None, *, channel: str) -> dict[str, Any] | None:
        extras = dict(parameters or {})
        application_id = self._session_application_id(runtime_context, channel=channel)
        if application_id:
            extras.setdefault("application_id", application_id)
        if workflow == "notion_update" and application_id and "record_id" not in extras:
            paths = application_context_service.paths_for(application_id)
            if paths.identity.exists():
                identity = read_json(paths.identity)
                aliases = identity.get("aliases") if isinstance(identity.get("aliases"), dict) else {}
                record_id = str(aliases.get("notion_record_id") or "").strip()
                if record_id.isdigit():
                    extras["record_id"] = int(record_id)
        return extras or None

    def _extract_linkedin_saved_jobs(self) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        completed = subprocess.run(["npm", "run", "linkedin:saved-jobs:extract"], cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10 * 60)
        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}"
            reason = "linkedin_auth_required" if "session" in combined.casefold() else "saved_jobs_extraction_failed"
            return {"status": "blocked", "blocker_reason": reason, "display_text": "A sessão do LinkedIn expirou. Preciso que você autentique o LinkedIn para continuar." if reason == "linkedin_auth_required" else "Não consegui atualizar as vagas salvas do LinkedIn. A extração foi interrompida."}
        output_path = self.root / "inbox" / "linkedin_saved_jobs.json"
        if not output_path.exists():
            return {"status": "blocked", "blocker_reason": "saved_jobs_output_missing"}
        payload = read_json(output_path)
        jobs = payload.get("jobs") or []
        self._write_saved_jobs_menu_state(jobs)
        lines = ["Vagas salvas no LinkedIn:"]
        for index, job in enumerate(jobs, start=1):
            lines.append(f"{index}. {job.get('title') or '-'} | {job.get('company') or '-'} | {job.get('location') or '-'}")
            lines.append(f"   {job.get('url') or '-'}")
        lines.extend(["", "Responda com o número ou a URL da vaga que você quer analisar."])
        return {"status": "completed", "kind": "linkedin_saved_jobs", "extracted_at": payload.get("extractedAt"), "total": len(jobs), "jobs": jobs, "display_text": "\n".join(lines)}

    def _finalize_fit_map_pipeline(self, *, application_id: str | None = None) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "harness_root_missing"}
        application_id = str(application_id or "").strip()
        if not application_id:
            return {"status": "blocked", "blocker_reason": "explicit_application_scope_required"}
        from career.services import fit_map as fit_map_service
        from career.tasks.registry import finalize_fit_map
        application_root = self.root / ".career-state" / "applications_v2"
        app_paths = application_context_service.paths_for(
            application_id, root=application_root
        )
        state_store = WorkflowStateStore.for_application(
            application_id,
            database=self.db,
            root=application_root,
        )
        draft_path = app_paths.fit_map_draft
        fit_map_path = app_paths.fit_map
        registry_path = app_paths.derived_dir / "keyword_ats_registry.json"
        try:
            results = finalize_fit_map(
                state_store=state_store,
                draft_path=draft_path,
                output_path=fit_map_path,
            )
            register_command = [
                str(self.root / "scripts" / "python.sh"),
                "scripts/register_keywords.py",
                "--fit-map",
                str(fit_map_path),
                "--registry",
                str(registry_path),
                "--translation-registry",
                str(
                    self.root
                    / ".agents/skills/career-system/references/keyword_translation_registry.json"
                ),
            ]
            registered = subprocess.run(register_command, cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10 * 60)
            if registered.returncode != 0:
                return {"status": "blocked", "blocker_reason": "register_keywords_failed", "command": register_command, "stderr": (registered.stderr or registered.stdout)[-2000:]}
            summary = fit_map_service.payload_summary(fit_map_path)
            quality = fit_map_service.quality_report(fit_map_path)
            registry = fit_map_service.registry_summary(registry_path, fit_map_path)
            return {"status": "completed", "application_id": application_id, "revision_id": results["revision_id"], "commands_executed": ["fit_map.validate_draft", "fit_map.build", "fit_map.score", "fit_map.validate", "scripts/register_keywords.py --fit-map <application>/fit_map.json --registry <application>/derived/keyword_ats_registry.json --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json"], "results": results, "summary": {"cargo": summary.get("cargo"), "empresa": summary.get("empresa"), "nota_final": summary.get("nota_final"), "keyword_registration": registry.get("registered"), "quality_status": quality.get("status")}}
        except Exception as exc:
            return {"status": "blocked", "blocker_reason": "fit_map_finalize_failed", "error": str(exc)}

    def _maybe_auto_execute_approved_action(self, step: str, *, objective: str | None, prepared: dict[str, Any]) -> dict[str, Any] | None:
        if not self.root:
            return None
        if not self._should_auto_execute_approved_action(step, objective=objective):
            return None
        approval_id = str((prepared.get("approval") or {}).get("approval_id") or "").strip()
        if not approval_id:
            return {"status": "blocked", "blocker_reason": "approval_id_missing"}
        try:
            ApprovalStore(self.root).approve(approval_id)
            executed = self.execute_approved_action(approval_id)
        except ValidationFailure as exc:
            return {"status": "blocked", "blocker_reason": "approved_action_validation_failed", "error": str(exc), "approval_id": approval_id}
        executed["auto_approved"] = True
        executed["approval_policy"] = self._approval_policy(step)
        return executed

    def _should_auto_execute_approved_action(self, step: str, *, objective: str | None) -> bool:
        policy = self._approval_policy(step)
        if step == "email-draft":
            return policy == "always"
        if step != "notion-update":
            return False
        if policy == "always":
            return True
        if policy != "explicit_request":
            return False
        lowered = str(objective or "").casefold()
        return not any(hint in lowered for hint in PREVIEW_HINTS)

    def _approval_policy(self, step: str) -> str:
        config = self._automation_config()
        approvals = config.get("approvals", {}) if isinstance(config.get("approvals"), dict) else {}
        if step == "notion-update":
            return str(approvals.get("notion_write") or "manual")
        if step == "email-draft":
            return str(approvals.get("email_draft") or "manual")
        return "manual"

    def _fit_map_auto_finalize_enabled(self) -> bool:
        config = self._automation_config()
        fit_map = config.get("fit_map", {}) if isinstance(config.get("fit_map"), dict) else {}
        return bool(fit_map.get("auto_finalize", True))

    def _automation_config(self) -> dict[str, Any]:
        config_path = self.root / ".career-state" / "applications_v2" / "config.json" if self.root else None
        payload = read_json(config_path) if config_path and config_path.exists() else {}
        merged = {"fit_map": {**DEFAULT_HARNESS_AUTOMATION["fit_map"]}, "approvals": {**DEFAULT_HARNESS_AUTOMATION["approvals"]}}
        harness = payload.get("harness", {}) if isinstance(payload.get("harness"), dict) else {}
        if isinstance(harness.get("fit_map"), dict):
            merged["fit_map"].update(harness["fit_map"])
        if isinstance(harness.get("approvals"), dict):
            merged["approvals"].update(harness["approvals"])
        return merged

    def _write_saved_jobs_menu_state(self, jobs: list[dict[str, Any]]) -> None:
        if not self.root:
            return
        from career.utils import write_json
        numbered_items = []
        for index, job in enumerate(jobs, start=1):
            numbered_items.append({"number": index, "section_id": "linkedin_saved_jobs", "section_title": "Vagas salvas no LinkedIn", "id": f"linkedin_saved_job_{job.get('jobId') or index}", "title": job.get("title"), "description": f"{job.get('company') or '-'} | {job.get('location') or '-'}", "prompt": job.get("url"), "recommended": False})
        write_json(self.root / ".career-state" / "harness" / "menu_state.json", {"kind": "session_menu_state", "updated_at": utc_now_iso(), "menu_context": "linkedin_saved_jobs", "headline": "Vagas salvas no LinkedIn", "numbered_items": numbered_items})

    def _build_session_menu(self) -> dict[str, Any]:
        active = self._active_intake_summary()
        stale = self._stale_active_intake_summary()
        if active:
            payload = {
                "status": "completed", "kind": "session_menu", "menu_context": "active_job",
                "headline": "Ha uma vaga ativa. Posso continuar daqui.", "active_intake": active,
                "sections": [
                    {"id": "continue_active_job", "title": "Continuar vaga ativa", "items": [
                        self._menu_item("resume", "Retomar trabalho em andamento", "Continuar exatamente do proximo passo salvo no estado local.", "continue o trabalho em andamento", recommended=True),
                        self._menu_item("fit_map", "Continuar analise da vaga ativa", "Seguir o pipeline da analise/FIT_MAP da vaga atual.", "continue a analise da vaga ativa"),
                    ]},
                    {"id": "generate_outputs", "title": "Gerar entregaveis da vaga ativa", "items": [
                        self._menu_item("cv", "Gerar CV", "Produzir o curriculo orientado pela vaga ativa.", "gere um CV para a vaga ativa"),
                        self._menu_item("feras", "Gerar pitch / FERAS", "Produzir o pitch executivo e o texto FERAS.", "gere um pitch FERAS para a vaga ativa"),
                        self._menu_item("cover_letter", "Gerar carta", "Produzir a carta de apresentacao da vaga ativa.", "gere uma carta de apresentacao para a vaga ativa"),
                        self._menu_item("habilidades", "Gerar habilidades ATS/Gupy", "Montar habilidades-chave e resumo ATS da vaga ativa.", "gere habilidades ATS para a vaga ativa"),
                    ]},
                    {"id": "capture_new_job", "title": "Trocar para outra vaga", "items": [
                        self._menu_item("linkedin_saved_jobs", "Ver vagas salvas no LinkedIn", "Abrir o rastreador salvo e escolher uma nova vaga.", "listar minhas vagas salvas"),
                        self._menu_item("notion_job_analysis", "Avaliar vaga do Notion por ID", "Iniciar analise de uma vaga ja cadastrada no Notion.", "quero avaliar uma vaga do Notion"),
                        self._menu_item("linkedin_job_intake", "Avaliar vaga do LinkedIn por URL", "Extrair a descricao da vaga e iniciar nova analise.", "quero avaliar uma vaga do LinkedIn"),
                        self._menu_item("pasted_job_intake", "Colar nova vaga para analise", "Salvar uma descricao colada e abrir novo intake.", "quero colar uma vaga para analise"),
                    ]},
                    {"id": "notion_actions", "title": "Notion", "items": [
                        self._menu_item("notion_update", "Atualizar ou criar vaga no Notion", "Preparar o dry-run de escrita no Notion a partir do estado atual.", "atualize a vaga no Notion"),
                    ]},
                ],
            }
            return self._finalize_menu_payload(payload)
        payload = {
            "status": "completed", "kind": "session_menu", "menu_context": "no_active_job",
            "headline": "Nao ha vaga ativa recente. Estas sao as entradas mais uteis para comecar." if not stale else "Nao ha vaga ativa. Estas sao as entradas mais uteis para comecar.",
            "sections": [
                {"id": "new_job_sources", "title": "Entradas de vaga", "items": [
                    self._menu_item("linkedin_saved_jobs", "Ver vagas salvas no LinkedIn", "Listar as vagas salvas no Jobs Tracker para escolher uma.", "listar minhas vagas salvas", recommended=True),
                    self._menu_item("notion_job_analysis", "Avaliar vaga do Notion por ID", "Avaliar rapidamente uma vaga ja registrada no Notion.", "quero avaliar uma vaga do Notion", recommended=True),
                    self._menu_item("linkedin_job_intake", "Avaliar vaga do LinkedIn por URL", "Extrair e persistir uma vaga do LinkedIn antes da analise.", "quero avaliar uma vaga do LinkedIn"),
                    self._menu_item("pasted_job_intake", "Colar nova vaga para analise", "Usar texto colado quando a vaga nao vier do LinkedIn nem do Notion.", "quero colar uma vaga para analise"),
                ]},
            ],
        }
        if stale:
            payload["stale_active_intake"] = stale
            payload["sections"].append({"id": "resume_previous_job", "title": "Retomar Trabalho Antigo", "items": [self._menu_item("resume", f"Retomar {stale.get('role') or 'vaga anterior'}", "Continuar manualmente o trabalho salvo anteriormente, mesmo ele parecendo antigo.", "continue o trabalho em andamento")]})
        return self._finalize_menu_payload(payload)

    def run_application_stage(self, *, stage: str, record_key: str, application_dir: Path, request_json: Path, request_md: Path, runner_config: dict[str, Any], model: str = "", variant: str = "", on_start: Callable | None = None, workspace_owner: str = "", control_db_id: str = "") -> dict[str, Any]:
        if not self.root or not self.runner:
            raise ValueError("HarnessSupervisor requires root and runner to execute stages.")
        request_payload = read_json(request_json)
        cellular_context = self._cellular_request_context(request_payload)
        if cellular_context:
            if cellular_context["application_id"] != record_key:
                raise ValidationFailure("cellular harness record key does not match application_id")
            expected_dir = (
                self.root / ".career-state" / "applications_v2" / record_key
            ).resolve()
            if Path(application_dir).resolve() != expected_dir:
                raise ValidationFailure("cellular harness application directory mismatch")
            self._acquire_cellular_workspace(workspace_owner, control_db_id)
        instruction = self._stage_instruction(stage)
        if cellular_context:
            instruction += (
                " Preserve application_id, run_id, node_id and manifest_path; "
                "read and write only the explicit allowlists."
            )
        run_request = AgentRunRequest(stage=stage, record_key=record_key, request_path=request_md, instruction=instruction, runner_config=runner_config, model=model, variant=variant)
        harness_run = HarnessRunStore(self.root, application_dir).begin(stage, request_json, request_md)
        command = self.runner.build_command(run_request)
        if on_start:
            on_start(command)
        result = self.runner.run(run_request)
        isolation = harness_run.inspect()
        payload = {"stage": stage, "command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "finished_at": utc_now_iso(), "run_dir": str(harness_run.run_dir.relative_to(self.root)), "isolation": isolation}
        harness_run.finish(payload, isolation)
        return payload

    def _cellular_request_context(
        self, request_payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if request_payload.get("cellular") is not True:
            return None
        if not self.root:
            raise ValidationFailure("cellular harness requires a workspace root")
        from career.services import multiagent as multiagent_service

        return multiagent_service.validate_cellular_request_context(
            {
                "cellular": True,
                "application_id": request_payload.get("application_id"),
                "run_id": request_payload.get("run_id"),
                "node_id": request_payload.get("node_id"),
                "manifest_path": request_payload.get("manifest_path"),
                "read_allowlist": request_payload.get("read_allowlist"),
                "write_allowlist": request_payload.get("write_allowlist"),
            },
            root=self.root,
        )

    def _acquire_cellular_workspace(
        self, workspace_owner: str = "", control_db_id: str = ""
    ) -> None:
        if not self.root:
            raise ValidationFailure("cellular harness requires a workspace root")
        database = application_context_service.canonical_database(root=self.root)
        database.init_schema()
        try:
            lease = application_context_service.WorkspaceLease(
                database,
                expected_control_db_id=control_db_id,
                require_authority=True,
            )
            owner = (
                str(workspace_owner).strip()
                or application_context_service.workspace_owner_from_env()
            )
            if not lease.acquire(owner, ttl_seconds=300) or not lease.heartbeat(owner):
                current = lease.inspect() or {}
                raise ValidationFailure(
                    "workspace lease blocked by another authoritative copy: "
                    f"{current.get('owner') or 'unknown'}"
                )
        finally:
            database.close()

    @staticmethod
    def _stage_instruction(stage: str) -> str:
        if stage == "analyze":
            return "Leia o request anexado e grave apenas o fit_map.draft.json."
        if stage == "repair":
            return "Leia o request anexado e repare somente os artefatos textuais permitidos."
        if stage == "generate":
            return "Leia o request anexado e grave somente os artefatos textuais pedidos."
        raise ValueError(f"Unsupported application stage: {stage}")

    def _run_generic_message(self, message: str, *, model: str | None = None) -> dict[str, Any]:
        if not self.root:
            return {"status": "blocked", "blocker_reason": "generic_runner_root_missing"}
        hermes = shutil.which("hermes")
        if not hermes:
            return {"status": "blocked", "blocker_reason": "generic_runner_unavailable"}
        command = [hermes, "--accept-hooks"]
        if model:
            command.extend(["--model", model])
        command.extend(["-z", message])
        env = os.environ.copy()
        env["CAREER_HARNESS_SUBAGENT"] = "1"
        completed = subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15 * 60)
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        return {"status": "completed" if completed.returncode == 0 else "blocked", "mode": "generic_hermes_fallback", **({"display_text": stdout} if completed.returncode == 0 and stdout else {}), "command": command, "stdout": stdout, "stderr": stderr, "returncode": completed.returncode, **({"blocker_reason": "generic_runner_failed"} if completed.returncode != 0 else {})}

    @staticmethod
    def _decision(workflow: str, stage: str, confidence: str, reason: str, *, requires_approval: bool = False, parameters: dict[str, Any] | None = None) -> DispatchDecision:
        return DispatchDecision(workflow=workflow, stage=stage, confidence=confidence, reason=reason, requires_approval=requires_approval, parameters=parameters)

    @staticmethod
    def _menu_item(item_id: str, title: str, description: str, prompt: str, *, recommended: bool = False) -> dict[str, Any]:
        return {"id": item_id, "title": title, "description": description, "prompt": prompt, "recommended": recommended}

    def _finalize_menu_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        numbered_items = self._numbered_menu_items(payload.get("sections") or [])
        payload["numbered_items"] = numbered_items
        payload["display_text"] = self._render_menu_text(payload)
        if self.root:
            self._write_menu_state(payload)
        return payload

    @staticmethod
    def _numbered_menu_items(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        numbered: list[dict[str, Any]] = []
        index = 1
        for section in sections:
            section_id = str(section.get("id") or "")
            section_title = str(section.get("title") or "")
            for item in section.get("items") or []:
                numbered.append({"number": index, "section_id": section_id, "section_title": section_title, "id": item.get("id"), "title": item.get("title"), "description": item.get("description"), "prompt": item.get("prompt"), "recommended": bool(item.get("recommended"))})
                index += 1
        return numbered

    def _write_menu_state(self, payload: dict[str, Any]) -> None:
        from career.utils import write_json
        write_json(self.root / ".career-state" / "harness" / "menu_state.json", {"kind": "session_menu_state", "updated_at": utc_now_iso(), "menu_context": payload.get("menu_context"), "headline": payload.get("headline"), "numbered_items": payload.get("numbered_items") or []})

    def _clear_menu_state(self) -> None:
        if not self.root:
            return
        (self.root / ".career-state" / "harness" / "menu_state.json").unlink(missing_ok=True)

    def _decorate_result_payload(self, result: Any) -> Any:
        if not isinstance(result, dict):
            return result
        if str(result.get("kind") or "") in {"session_menu", "linkedin_saved_jobs", "agent_menu"}:
            return result
        agent_menu = self._build_agent_menu_for_result(result)
        if not agent_menu:
            return result
        return {**result, **agent_menu}

    def _build_agent_menu_for_result(self, result: dict[str, Any]) -> dict[str, Any] | None:
        if not self._result_has_completed_fit_map(result):
            return None
        application_id = self._result_application_id(result)
        if not application_id:
            return self._blocked_summary_result(
                result, "explicit_application_scope_required"
            )
        try:
            summary = self._materialized_fit_map_summary(application_id)
        except (ApplicationNotFoundError, ValueError):
            return self._blocked_summary_result(
                result, "fit_map_summary_context_unavailable", application_id
            )
        nota_final = summary.get("nota_final")
        nota_text = f"{float(nota_final):.1f}/10" if isinstance(nota_final, (int, float)) else "n/d"
        keyword_registration = summary.get("keyword_registration") or {}
        keyword_line = "Keywords ATS registradas: sim." if keyword_registration.get("registered") else "Keywords ATS pendentes de registro."
        payload = {
            "status": result.get("status") or "completed", "kind": "agent_menu", "menu_context": "active_job",
            "application_id": application_id,
            "headline": "A analise da vaga foi concluida. Posso seguir para a proxima entrega.",
            "summary_lines": [
                f"Resumo: {summary.get('cargo') or '-'} | {summary.get('empresa') or '-'}",
                f"Nota de aderencia: {nota_text}",
                f"Gaps mapeados: {summary.get('gaps_count') or 0} | Objecoes mapeadas: {summary.get('objecoes_count') or 0}",
                keyword_line,
            ],
            "sections": [{"id": "post_fit_map_actions", "title": "Proximos passos possiveis", "items": [
                self._menu_item("cv", "Gerar CV", "Produzir o curriculo orientado pela vaga ativa.", "gere um CV para a vaga ativa", recommended=True),
                self._menu_item("feras", "Pitch/FERAS", "Produzir o pitch executivo e o texto FERAS.", "gere um pitch FERAS para a vaga ativa"),
                self._menu_item("cover_letter", "Carta de apresentacao", "Produzir a carta de apresentacao da vaga ativa.", "gere uma carta de apresentacao para a vaga ativa"),
                self._menu_item("habilidades", "Habilidades ATS/Gupy", "Montar habilidades-chave e resumo ATS da vaga ativa.", "gere habilidades ATS para a vaga ativa"),
                self._menu_item("notion_update", "Criar no Notion", "Criar ou atualizar o registro da vaga no Notion a partir do estado atual.", "crie registro no Notion para a vaga ativa"),
            ]}],
        }
        return self._finalize_menu_payload(payload)

    @staticmethod
    def _result_application_id(result: dict[str, Any]) -> str | None:
        direct = str(result.get("application_id") or "").strip()
        if direct:
            return direct
        specialist = result.get("specialist")
        if isinstance(specialist, dict):
            nested = str(specialist.get("application_id") or "").strip()
            if nested:
                return nested
        intake = result.get("intake")
        if isinstance(intake, dict):
            nested = str(intake.get("application_id") or "").strip()
            if nested:
                return nested
        return None

    def _materialized_fit_map_summary(self, application_id: str) -> dict[str, Any]:
        """Build menu fields from the application's canonical SQLite snapshot.

        Compatibility FIT_MAP JSON is intentionally not read here: a final
        scoped response must describe the same application that completed the
        specialist run.
        """
        from career.services.context_materializer import ContextMaterializer

        payload = ContextMaterializer(self.db).build(application_id, "fit_map_seed")
        context = payload.get("context")
        if not isinstance(context, dict):
            raise ValueError("materialized fit_map context is missing")
        application = context.get("application")
        analysis = context.get("analysis")
        if not isinstance(application, dict) or not isinstance(analysis, dict):
            raise ValueError("materialized fit_map context is incomplete")
        dimensions = analysis.get("dimensions")
        objections = analysis.get("objections")
        keyword_count = self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM keyword_registry WHERE application_id = ?",
            (application_id,),
        )
        registered_count = int(keyword_count["count"]) if keyword_count else 0
        return {
            "cargo": application.get("role"),
            "empresa": application.get("company"),
            "nota_final": analysis.get("score_final"),
            "gaps_count": sum(
                1
                for item in dimensions or ()
                if isinstance(item, dict) and str(item.get("gap_summary") or "").strip()
            ),
            "objecoes_count": len(objections) if isinstance(objections, list) else 0,
            "keyword_registration": {
                "registered": registered_count > 0,
                "count": registered_count,
            },
        }

    @staticmethod
    def _blocked_summary_result(
        result: dict[str, Any], reason: str, application_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "status": "blocked",
            "kind": "fit_map_summary_blocked",
            "step": result.get("step") or "fit-map",
            "application_id": application_id,
            "blocker_reason": reason,
        }

    @staticmethod
    def _result_has_completed_fit_map(result: dict[str, Any]) -> bool:
        if str(result.get("status") or "") != "completed":
            return False
        if str(result.get("step") or "") == "fit-map":
            return True
        specialist = result.get("specialist")
        return isinstance(specialist, dict) and str(specialist.get("status") or "") == "completed" and str(specialist.get("step") or "") == "fit-map"

    def _sync_menu_state_for_result(self, result: Any) -> None:
        if not self.root or not isinstance(result, dict):
            return
        if str(result.get("kind") or "") in {"session_menu", "linkedin_saved_jobs", "agent_menu"}:
            return
        self._clear_menu_state()

    def _resolve_menu_selection(self, message: str) -> dict[str, Any] | None:
        text = " ".join(str(message or "").strip().split())
        payload = self._menu_state_payload()
        if not payload:
            return None
        if re.fullmatch(r"\d{1,2}", text):
            selection_number = int(text)
        elif str(payload.get("menu_context") or "") == "linkedin_saved_jobs":
            # Users commonly answer a saved-jobs menu with a natural phrase
            # such as "analise a vaga 2".  Treat that as the menu selection
            # before NOTION_ID_RE gets a chance to interpret the number as a
            # Notion record.  Keep the grammar deliberately narrow so an
            # explicit "vaga no Notion 2" is not redirected here.
            selection_match = re.search(
                r"\bvaga\s+(?:n[úu]mero\s*)?#?\s*(\d{1,2})\b",
                text,
                re.IGNORECASE,
            )
            if not selection_match:
                return None
            selection_number = int(selection_match.group(1))
        else:
            return None
        items = payload.get("numbered_items") or []
        selected = next(
            (item for item in items if int(item.get("number") or 0) == selection_number),
            None,
        )
        if not selected:
            return None
        return {"number": selection_number, "id": selected.get("id"), "title": selected.get("title"), "description": selected.get("description"), "prompt": selected.get("prompt"), "menu_context": payload.get("menu_context")}

    def _invalid_menu_selection(self, message: str) -> str | None:
        text = " ".join(str(message or "").strip().split())
        if not re.fullmatch(r"\d{1,2}", text):
            return None
        payload = self._menu_state_payload()
        if not payload:
            return None
        items = payload.get("numbered_items") or []
        if any(int(item.get("number") or 0) == int(text) for item in items):
            return None
        return "numeric_menu_selection_not_found"

    def _menu_state_payload(self) -> dict[str, Any] | None:
        if not self.root:
            return None
        state_path = self.root / ".career-state" / "harness" / "menu_state.json"
        if not state_path.exists():
            return None
        try:
            return read_json(state_path)
        except Exception:
            return None

    @staticmethod
    def _menu_input_request(selection: dict[str, Any]) -> dict[str, Any] | None:
        item_id = str(selection.get("id") or "")
        requests = {
            "notion_job_analysis": ("notion_id", "Qual é o número da vaga no Notion? Pode responder somente com o número."),
            "linkedin_job_intake": ("linkedin_job_url", "Envie a URL da vaga no LinkedIn."),
            "pasted_job_intake": ("pasted_job", "Cole a vaga com duas linhas no início: Empresa: nome e Cargo: nome. Depois inclua a descrição completa."),
        }
        request = requests.get(item_id)
        if not request:
            return None
        return {"status": "awaiting_input", "kind": "input_request", "input_kind": request[0], "display_text": request[1]}

    @staticmethod
    def _saved_job_metadata_hints(selection: dict[str, Any] | None) -> dict[str, str]:
        if not isinstance(selection, dict) or selection.get("menu_context") != "linkedin_saved_jobs":
            return {}
        company = ""
        location = ""
        description = str(selection.get("description") or "")
        if " | " in description:
            company, location = [part.strip() for part in description.split(" | ", 1)]
        return {"role": str(selection.get("title") or "").strip(), "company": company, "location": location}

    def _resolve_linkedin_application_id(self, url: str) -> str | None:
        """Reuse an existing SQLite application when a LinkedIn URL is retried."""
        raw_url = str(url or "").strip().rstrip(".,);]")
        if not raw_url:
            return None
        candidates = [raw_url]
        normalized_url = raw_url.split("#", 1)[0].split("?", 1)[0].rstrip("/") + "/"
        if normalized_url not in candidates:
            candidates.append(normalized_url)
        repository = ApplicationRepository(self.db)
        for candidate in candidates:
            try:
                application = repository.resolve_by_alias(
                    alias_type="linkedin_job_source_id",
                    alias_value=candidate,
                )
            except ApplicationNotFoundError:
                continue
            return application.application_id
        return None

    def _write_pending_input(self, request: dict[str, Any]) -> None:
        if not self.root:
            return
        created_at = str(request.get("created_at") or utc_now_iso())
        expires_at = str(
            request.get("expires_at")
            or (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        )
        write_json(
            self.root / ".career-state" / "harness" / "pending_input.json",
            {**request, "created_at": created_at, "expires_at": expires_at, "updated_at": utc_now_iso()},
        )

    def _clear_pending_input(self) -> None:
        if not self.root:
            return
        (self.root / ".career-state" / "harness" / "pending_input.json").unlink(missing_ok=True)

    def _read_pending_input(self) -> dict[str, Any] | None:
        if not self.root:
            return None
        path = self.root / ".career-state" / "harness" / "pending_input.json"
        if not path.exists():
            return None
        pending = read_json(path)
        return pending if isinstance(pending, dict) else None

    def _resolve_pending_input(
        self, message: str, *, runtime_context: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        if not self.root:
            return None
        path = self.root / ".career-state" / "harness" / "pending_input.json"
        if not path.exists():
            return None
        pending = read_json(path)
        expires_at = str(pending.get("expires_at") or "").strip()
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                    path.unlink(missing_ok=True)
                    return None
            except ValueError:
                path.unlink(missing_ok=True)
                return None
        runtime_context = runtime_context or {}
        pending_session = str(pending.get("session_id") or "").strip()
        current_session = str(runtime_context.get("session_id") or "").strip()
        if pending_session and current_session and pending_session != current_session:
            return None
        pending_application = str(pending.get("application_id") or "").strip()
        current_application = str(runtime_context.get("application_id") or "").strip()
        if pending_application and current_application and pending_application != current_application:
            return None
        input_kind = str(pending.get("input_kind") or "")
        text = str(message or "").strip()
        resolved: str | None = None
        normalized = text.casefold()
        if input_kind == "confirmation" and normalized in {"sim", "s", "yes", "y", "confirmo", "pode"}:
            path.unlink(missing_ok=True)
            return {"input_kind": input_kind, "answer": True, "application_id": pending.get("application_id"), "turn_id": pending.get("turn_id")}
        if input_kind == "confirmation" and normalized in {"não", "nao", "n", "no", "cancele", "cancelar"}:
            path.unlink(missing_ok=True)
            return {"input_kind": input_kind, "answer": False, "application_id": pending.get("application_id"), "turn_id": pending.get("turn_id")}
        if input_kind == "notion_id" and re.fullmatch(r"\d+", text):
            resolved = f"avalie vaga Notion {text}"
        elif input_kind == "notion_record_selection" and re.fullmatch(r"\d+", text):
            record_ids = {int(item) for item in pending.get("record_ids") or []}
            if int(text) in record_ids:
                resolved = f"avalie vaga Notion {text}"
        elif input_kind == "notion_application_filter" and text:
            resolved = f"traga vagas com {text}"
        elif input_kind == "linkedin_job_url" and LINKEDIN_JOB_RE.search(text):
            resolved = text
        elif input_kind == "pasted_job" and len(text) >= 200:
            resolved = "Analise esta vaga\n" + text
        if not resolved:
            return None
        path.unlink(missing_ok=True)
        return {"input_kind": input_kind, "message": resolved}

    def _invalid_pending_record_selection(self, message: str) -> str | None:
        if not self.root or not re.fullmatch(r"\d+", str(message or "").strip()):
            return None
        path = self.root / ".career-state" / "harness" / "pending_input.json"
        if not path.exists():
            return None
        pending = read_json(path)
        if str(pending.get("input_kind") or "") != "notion_record_selection":
            return None
        record_ids = {int(item) for item in pending.get("record_ids") or []}
        return "notion_record_selection_not_found" if int(message) not in record_ids else None

    def _render_menu_text(self, payload: dict[str, Any]) -> str:
        lines = [str(payload.get("headline") or "Menu")]
        active = payload.get("active_intake") if isinstance(payload.get("active_intake"), dict) else None
        stale = payload.get("stale_active_intake") if isinstance(payload.get("stale_active_intake"), dict) else None
        if active:
            lines.append(f"Vaga ativa: {active.get('role') or '-'} | {active.get('company') or '-'}")
            lines.append(f"Próximo passo salvo: {active.get('next_required_step') or '-'}")
        elif stale:
            lines.append(f"Trabalho antigo detectado: {stale.get('role') or '-'} | {stale.get('company') or '-'}")
            lines.append(f"Última atualização salva: {stale.get('updated_at') or '-'}")
        for summary_line in payload.get("summary_lines") or []:
            if isinstance(summary_line, str) and summary_line.strip():
                lines.append(summary_line)
        for section in payload.get("sections") or []:
            lines.append("")
            lines.append(f"{section.get('title')}:")
            for item in payload.get("numbered_items") or []:
                if item.get("section_id") != section.get("id"):
                    continue
                suffix = " [recomendado]" if item.get("recommended") else ""
                lines.append(f"{item.get('number')}. {item.get('title')}{suffix}")
                lines.append(f"   {item.get('description')}")
        lines.append("")
        if str(payload.get("kind") or "") == "agent_menu":
            lines.append("Qual voce quer? Responda com o numero da opcao ou diga o que voce quer fazer.")
        else:
            lines.append("Responda com o número da opção ou diga o que você quer fazer.")
        return "\n".join(lines)

    def _active_intake_summary(self) -> dict[str, Any] | None:
        active = self._raw_active_intake()
        if not active or self._is_stale_active_intake(active):
            return None
        return self._normalize_active_intake(active)

    def _stale_active_intake_summary(self) -> dict[str, Any] | None:
        active = self._raw_active_intake()
        if not active or not self._is_stale_active_intake(active):
            return None
        normalized = self._normalize_active_intake(active)
        normalized["stale"] = True
        return normalized

    def _raw_active_intake(self) -> dict[str, Any] | None:
        if not self.root:
            return None
        state_path = self.root / ".career-state" / "workflow_state.json"
        if not state_path.exists():
            return None
        payload = read_json(state_path)
        active = payload.get("active_intake")
        if not isinstance(active, dict) or not active.get("job_description_path"):
            return None
        return active

    @staticmethod
    def _normalize_active_intake(active: dict[str, Any]) -> dict[str, Any]:
        return {"source_type": active.get("source_type"), "source_id": active.get("source_id"), "company": active.get("company"), "role": active.get("role"), "job_description_path": active.get("job_description_path"), "next_required_step": active.get("next_required_step"), "status": active.get("status"), "updated_at": active.get("updated_at")}

    @staticmethod
    def _is_stale_active_intake(active: dict[str, Any]) -> bool:
        updated_at = str(active.get("updated_at") or "").strip()
        if not updated_at:
            return False
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - parsed > ACTIVE_INTAKE_STALE_AFTER

    @staticmethod
    def _is_runtime_introspection(lowered: str) -> bool:
        triggers = ("temperatura", "temperature", "config do hermes", "configuração do hermes", "configuracao do hermes", "hermes config", "qual modelo", "que modelo", "model you are using", "modelo que vc está usando", "modelo que vc esta usando", "runtime do hermes", "runtime local")
        return any(trigger in lowered for trigger in triggers)

    @staticmethod
    def _is_menu_request(lowered: str) -> bool:
        if lowered.strip(" !.,?") in {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"}:
            return True
        triggers = ("menu", "opcoes", "opções", "nova sessao", "nova sessão", "o que posso fazer", "atalhos", "acoes comuns", "ações comuns")
        return any(trigger in lowered for trigger in triggers)
