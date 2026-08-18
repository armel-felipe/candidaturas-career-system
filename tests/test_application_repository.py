from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career.services import application_context
from career.services.database import Database
from career.services.persistence.application_repository import (
    AmbiguousApplicationError,
    ApplicationIdentity,
    ApplicationNotFoundError,
    ApplicationResolutionError,
    ApplicationRepository,
)
from career.utils import write_json


class ApplicationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.db = Database(db_path=self.root / "runtime.db")
        self.addCleanup(self.db.close)
        self.repository = ApplicationRepository(self.db)

    def test_resolve_by_application_id(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-conexa",
            )
        )

        result = self.repository.resolve(application_id="app-conexa")

        self.assertEqual(result.application_id, "app-conexa")
        self.assertEqual(result.company, "Conexa")
        self.assertEqual(result.role, "Diretor de Growth")
        self.assertEqual(result.notion_id, "578")
        self.assertEqual(result.fingerprint, "fp-conexa")

    def test_resolve_by_notion_id(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
            )
        )

        result = self.repository.resolve(notion_id="578")

        self.assertEqual(result.application_id, "app-conexa")
        self.assertEqual(result.notion_id, "578")

    def test_resolve_by_fingerprint(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-people",
                company="People Meet",
                role="Diretor de Operacoes",
                fingerprint="fp-people",
            )
        )

        result = self.repository.resolve(fingerprint="fp-people")

        self.assertEqual(result.application_id, "app-people")
        self.assertEqual(result.fingerprint, "fp-people")

    def test_resolve_by_company_and_role_requires_unambiguous_match(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-a",
                company="Acme",
                role="Director",
                fingerprint="fp-a",
            )
        )
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-b",
                company="Acme",
                role="Director",
                fingerprint="fp-b",
            )
        )

        with self.assertRaisesRegex(
            AmbiguousApplicationError, "company/role matched multiple applications"
        ):
            self.repository.resolve(company="Acme", role="Director")

    def test_resolve_requires_explicit_selector(self) -> None:
        with self.assertRaisesRegex(
            ApplicationNotFoundError, "resolver requires application_id, notion_id, fingerprint, or company and role"
        ):
            self.repository.resolve()

    def test_update_projection_returns_latest_fingerprint(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-original",
            )
        )
        self.db.execute(
            """INSERT INTO application_revisions
               (revision_id, application_id, revision_kind, fingerprint, source_hash, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "rev-latest",
                "app-conexa",
                "intake_identity",
                "fp-latest",
                "fp-latest",
                "{}",
                "2026-08-19T12:00:00+00:00",
            ),
        )

        projection = self.repository.update_projection("app-conexa")

        self.assertEqual(projection.application_id, "app-conexa")
        self.assertEqual(projection.notion_id, "578")
        self.assertEqual(projection.fingerprint, "fp-latest")

    def test_create_application_refresh_preserves_existing_workflow_fields(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                source_type="notion_record",
                source_url="https://old.example/job",
            )
        )
        self.db.execute(
            """UPDATE applications
               SET stage = ?, funil_stage = ?, cv_language = ?, status = ?, source_url = ?
               WHERE id = ?""",
            (
                "core_package_sealed",
                "Aplicacao andamento",
                "en",
                "paused",
                "https://old.example/job",
                "app-conexa",
            ),
        )

        refreshed = self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa Atualizada",
                role="VP Growth",
                notion_id="999",
                source_type="notion_record",
                source_url="https://new.example/job",
            )
        )

        self.assertEqual(refreshed.company, "Conexa Atualizada")
        self.assertEqual(refreshed.role, "VP Growth")
        self.assertEqual(refreshed.notion_id, "999")
        self.assertEqual(refreshed.stage, "core_package_sealed")
        self.assertEqual(refreshed.funil_stage, "Aplicacao andamento")
        self.assertEqual(refreshed.cv_language, "en")
        self.assertEqual(refreshed.status, "paused")
        self.assertEqual(refreshed.source_url, "https://new.example/job")

    def test_create_application_rejects_alias_conflict_from_another_application(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
            )
        )

        with self.assertRaisesRegex(
            ApplicationResolutionError, "alias notion_id=578 already belongs to app-conexa"
        ):
            self.repository.create_application(
                ApplicationIdentity(
                    application_id="app-other",
                    company="Outra",
                    role="Outra vaga",
                    notion_id="578",
                )
            )

        self.assertEqual(
            self.repository.resolve(notion_id="578").application_id, "app-conexa"
        )

    def test_application_context_resolves_from_repository_without_workflow_state(self) -> None:
        self.repository.create_application(
            ApplicationIdentity(
                application_id="notion_578",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-conexa",
            )
        )
        app_paths = application_context.paths_for("notion_578", root=self.applications_dir)
        app_paths.app_dir.mkdir(parents=True, exist_ok=True)
        app_paths.workflow_state.write_text("{invalid json", encoding="utf-8")

        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            result = application_context.resolve_application(
                notion_id="578", database=self.db
            )

        self.assertEqual(result.application_id, "notion_578")
        self.assertEqual(result.fingerprint, "fp-conexa")

    def test_application_context_falls_back_to_explicit_application_identity_during_migration(
        self,
    ) -> None:
        app_paths = application_context.paths_for("notion_578", root=self.applications_dir)
        app_paths.app_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            app_paths.identity,
            {
                "kind": "application_identity",
                "application_id": "notion_578",
                "company": "Conexa",
                "role": "Diretor de Growth",
                "aliases": {"notion_record_id": "578"},
            },
        )
        write_json(
            app_paths.source_metadata,
            {
                "application_id": "notion_578",
                "job_fingerprint": "fp-legacy",
            },
        )
        app_paths.workflow_state.write_text("{invalid json", encoding="utf-8")

        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            result = application_context.resolve_application(
                application_id="notion_578", database=self.db
            )

        self.assertEqual(result.application_id, "notion_578")
        self.assertEqual(result.company, "Conexa")
        self.assertEqual(result.role, "Diretor de Growth")
        self.assertEqual(result.notion_id, "578")
        self.assertEqual(result.fingerprint, "fp-legacy")

    def test_application_context_legacy_fallback_requires_application_id_as_only_selector(
        self,
    ) -> None:
        app_paths = application_context.paths_for("notion_578", root=self.applications_dir)
        app_paths.app_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            app_paths.identity,
            {
                "kind": "application_identity",
                "application_id": "notion_578",
                "company": "Conexa",
                "role": "Diretor de Growth",
                "aliases": {"notion_record_id": "578"},
            },
        )
        write_json(
            app_paths.source_metadata,
            {
                "application_id": "notion_578",
                "job_fingerprint": "fp-legacy",
            },
        )

        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            with self.assertRaisesRegex(
                ApplicationNotFoundError, "no application matched application_id=notion_578"
            ):
                application_context.resolve_application(
                    application_id="notion_578",
                    notion_id="578",
                    database=self.db,
                )

    def test_application_context_legacy_fallback_fails_closed_on_conflicting_selectors(
        self,
    ) -> None:
        app_paths = application_context.paths_for("notion_578", root=self.applications_dir)
        app_paths.app_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            app_paths.identity,
            {
                "kind": "application_identity",
                "application_id": "notion_578",
                "company": "Conexa",
                "role": "Diretor de Growth",
                "aliases": {"notion_record_id": "578"},
            },
        )
        write_json(
            app_paths.source_metadata,
            {
                "application_id": "notion_578",
                "job_fingerprint": "fp-legacy",
            },
        )

        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            with self.assertRaisesRegex(
                ApplicationNotFoundError, "no application matched application_id=notion_578"
            ):
                application_context.resolve_application(
                    application_id="notion_578",
                    fingerprint="fp-legacy",
                    database=self.db,
                )

    def test_ensure_application_persists_sqlite_before_identity_files(self) -> None:
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ):
            first = application_context.ensure_application(
                source_type="notion_record",
                source_id="source-first",
                company="Conexa",
                role="Diretor de Growth",
                record_id="578",
                preferred_id="notion_578",
            )
            conflict_paths = application_context.paths_for(
                "manual_conflict", root=self.applications_dir
            )

            with self.assertRaisesRegex(
                ApplicationResolutionError,
                "alias notion_id=578 already belongs to notion_578",
            ):
                application_context.ensure_application(
                    source_type="notion_record",
                    source_id="source-second",
                    company="Outra",
                    role="Outra vaga",
                    record_id="578",
                    preferred_id="manual_conflict",
                )

        self.assertTrue(first.identity.exists())
        self.assertFalse(conflict_paths.identity.exists())


if __name__ == "__main__":
    unittest.main()
