from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from career.services import agent_guard, application_context, intake, multiagent
from career.services import harness_supervisor as harness_supervisor_module
from career.services.context_materializer import ContextMaterializer
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor, SpecialistContract
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import ApplicationRepository
from career.services.persistence.gate_repository import GateRepository
from career.services.persistence.reference_repository import ReferenceRepository
from career.utils import read_json, sha256_file, sha256_text, write_json
from career.workflow import state_store as state_store_module
from career.workflow.state_store import WorkflowStateStore


def _score_item(label: str) -> dict:
    return {
        "item": label,
        "tipo": "DIRETO",
        "evidencia": "Experiencia comprovada em operacoes",
        "resultado": "Reducao de custo em 13%",
        "nota": 1.0,
        "prova_literal": True,
        "fonte_base": "candidate_reference:operations",
    }


def _valid_draft(company: str, role: str, marker: str) -> dict:
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
            "secundaria": {**story, "empresa": "WeHandle"},
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


class Phase3IntegrationE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.database = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)
        self.application_id = "notion_578"
        self.company = "Conexa"
        self.role = "Diretor de Growth"

    def test_real_intake_persists_pinnable_source_snapshot(self) -> None:
        source_text = "DESCRICAO V1 CONEXA " * 80
        with self._runtime():
            record = self._intake(source_text)

        applications = ApplicationRepository(self.database)
        revision_id = applications.get_current_revision_id(record.application_id)
        self.assertIsNotNone(revision_id)
        revision = applications.get_application_revision(
            record.application_id, str(revision_id)
        )
        description = applications.get_job_description_for_application_revision(
            record.application_id, revision.revision_id
        )
        self.assertEqual(description.content, source_text)
        self.assertEqual(description.content_hash, record.fingerprint)
        self.assertEqual(revision.fingerprint, record.fingerprint)
        self.assertEqual(revision.source_hash, record.fingerprint)
        self.assertEqual(revision.payload["job_description_id"], description.description_id)
        self.assertEqual(revision.payload["job_source_id"], description.source_id)
        self.assertEqual(revision.payload["job_description_hash"], record.fingerprint)
        self.assertTrue(revision.payload["job_description_path"])
        self.assertTrue(revision.payload["source_metadata_hash"])

    def test_real_intake_and_supervisor_finalizer_persist_revision_bound_gates(self) -> None:
        with self._runtime():
            record = self._intake("DESCRICAO V1 CONEXA " * 80)
            self._seed_reference()
            paths = application_context.paths_for(record.application_id)
            write_json(paths.fit_map_draft, _valid_draft(self.company, self.role, "growth"))

            supervisor = HarnessSupervisor(self.root)
            self.addCleanup(supervisor.db.close)
            with mock.patch.object(
                harness_supervisor_module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "registered", ""),
            ):
                result = supervisor._finalize_fit_map_pipeline(
                    application_id=record.application_id
                )

        self.assertEqual(result["status"], "completed")
        revision = AnalysisRepository(self.database).get_current(record.application_id)
        current_application_revision = ApplicationRepository(
            self.database
        ).get_application_revision(
            record.application_id,
            ApplicationRepository(self.database).get_current_revision_id(
                record.application_id
            ),
        )
        self.assertEqual(revision.application_revision_id, current_application_revision.revision_id)
        self.assertEqual(revision.fingerprint, record.fingerprint)
        self.assertEqual(revision.source_hash, sha256_file(paths.fit_map))
        self.assertIsNotNone(revision.score_final)
        gates = GateRepository(self.database)
        for gate in ("fit_map_built", "fit_map_scored", "fit_map_validated"):
            self.assertTrue(
                gates.is_satisfied(
                    record.application_id, gate, revision_id=revision.revision_id
                )
            )
        linked_receipts = self.database.fetch_all(
            """SELECT vr.gate, gd.dependency_id
                 FROM validation_receipts AS vr
                 JOIN gate_dependencies AS gd ON gd.receipt_id = vr.receipt_id
                WHERE vr.application_id = ?
                  AND vr.gate IN ('fit_map_built', 'fit_map_scored', 'fit_map_validated')
                ORDER BY vr.gate""",
            (record.application_id,),
        )
        self.assertEqual({row["dependency_id"] for row in linked_receipts}, {revision.revision_id})

    def test_reintake_blocks_stale_analysis_and_keeps_explicit_old_revision_recoverable(self) -> None:
        with self._runtime():
            first = self._intake("DESCRICAO V1 CONEXA " * 80)
            self._seed_reference()
            first_paths = application_context.paths_for(first.application_id)
            write_json(
                first_paths.fit_map_draft,
                _valid_draft(self.company, self.role, "growth-v1"),
            )
            supervisor = HarnessSupervisor(self.root)
            self.addCleanup(supervisor.db.close)
            with mock.patch.object(
                harness_supervisor_module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "registered", ""),
            ):
                finalized = supervisor._finalize_fit_map_pipeline(
                    application_id=first.application_id
                )
            self.assertEqual(finalized["status"], "completed")
            old_revision = AnalysisRepository(self.database).get_current(
                first.application_id
            )

            second = intake.start_intake(
                intake.JobSource(
                    source_type="notion_record",
                    source_id="578",
                    company=self.company,
                    role=self.role,
                    text="DESCRICAO V2 CONEXA NOVA " * 80,
                    record_id="578",
                    preferred_id=self.application_id,
                ),
                database=self.database,
            )

            materializer = ContextMaterializer(self.database)
            with self.assertRaisesRegex(ValueError, "stale.*analysis|current.*revision"):
                materializer.build(second.application_id, "cv_input")
            pinned = materializer.build(
                second.application_id,
                "cv_input",
                revision_id=old_revision.revision_id,
            )
            contract_result = supervisor.execute_specialist(
                second.application_id,
                SpecialistContract(
                    step="fit-map", required_gates=("fit_map_validated",)
                ),
                run_id="run-after-reintake",
            )

        self.assertIn("DESCRICAO V1 CONEXA", pinned["context"]["job_description"]["content"])
        self.assertNotIn("DESCRICAO V2 CONEXA", json.dumps(pinned, ensure_ascii=False))
        self.assertEqual(contract_result.status, "blocked")
        self.assertEqual(
            contract_result.blocker_reason,
            "stale_analysis_for_current_application_revision",
        )
        gates = GateRepository(self.database)
        self.assertFalse(
            gates.is_satisfied(second.application_id, "fit_map_draft_valid")
        )
        self.assertEqual(gates.next_required_step(second.application_id), "fill_fit_map_draft")
        self.assertTrue(
            self.database.fetch_one(
                "SELECT revision_id FROM fit_map_revisions WHERE revision_id = ?",
                (old_revision.revision_id,),
            )
        )

    def test_emitted_local_map_request_and_guard_have_only_scoped_fit_map_instructions(self) -> None:
        with self._runtime():
            record = self._intake("DESCRICAO MAPA LOCAL CONEXA " * 80)
            self._seed_reference()
            local_map_result = multiagent.write_local_model_map()
            local_map = read_json(self.root / local_map_result["map_json"])
            request_result = multiagent.write_request(
                "fit-map",
                application_id=record.application_id,
                fingerprint=record.fingerprint,
                database=self.database,
            )
            request = read_json(self.root / request_result["request_json"])
            state_store = WorkflowStateStore.for_application(
                record.application_id,
                database=self.database,
                root=self.applications_dir,
            )
            guard = agent_guard.guard(
                state_store=state_store,
                application_id=record.application_id,
                fingerprint=record.fingerprint,
                database=self.database,
            )

        for payload in (local_map, request, guard):
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn(".career-state/fit_map.draft.json", serialized)
            self.assertNotIn(".career-state/fit_map.json", serialized)
            self.assertNotIn(".career-state/agent_requests/fit-map_request.md", serialized)
            self._assert_job_commands_are_scoped(payload)
        self.assertIn(
            ".career-state/applications_v2/<application_id>/",
            json.dumps(local_map, ensure_ascii=False),
        )
        self.assertIn(
            f".career-state/applications_v2/{record.application_id}/",
            json.dumps(request, ensure_ascii=False),
        )

    def _intake(self, text: str):
        result = intake.from_paste(
            company=self.company,
            role=self.role,
            text=text,
            application_id=self.application_id,
            database=self.database,
        )
        self.assertEqual(result["status"], "ready_for_model_analysis")
        return ApplicationRepository(self.database).resolve(
            application_id=self.application_id
        )

    def _seed_reference(self) -> str:
        return ReferenceRepository(self.database).upsert_version(
            "candidate_facts",
            "felipe",
            json.dumps({"facts": ["Escalou operacoes"]}, ensure_ascii=False),
            "candidate-source-v1",
        )

    def _assert_job_commands_are_scoped(self, payload) -> None:
        for text in self._strings(payload):
            if any(
                marker in text
                for marker in (
                    "npm run agent:guard",
                    "npm run multiagent:request -- fit-map",
                    "npm run fit-map:",
                )
            ):
                self.assertIn("--application-id", text, text)

    def _strings(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from self._strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from self._strings(item)

    @contextmanager
    def _runtime(self):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(
            application_context, "ALIAS_INDEX", self.career_state / "application_alias_index.json"
        ), mock.patch.object(
            application_context, "SESSION_REGISTRY", self.career_state / "session_registry.json"
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", self.career_state
        ), mock.patch.object(intake, "INBOX", self.root / "inbox"), mock.patch.object(
            multiagent, "ROOT", self.root
        ), mock.patch.object(
            multiagent, "REQUEST_DIR", self.career_state / "agent_requests"
        ), mock.patch.object(
            multiagent,
            "LOCAL_MODEL_MAP_PATH",
            self.career_state / "agent_requests" / "local_model_map.json",
        ), mock.patch.object(agent_guard, "ROOT", self.root), mock.patch.object(
            agent_guard, "CAREER_STATE", self.career_state
        ), mock.patch.object(state_store_module, "CAREER_STATE", self.career_state):
            yield


if __name__ == "__main__":
    unittest.main()
