from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from career import cli
from career.paths import ROOT
from career.services import application_context, cover_letter, cv_content, derived_context, feras
from career.services.database import Database
from career.services.harness_supervisor import HarnessSupervisor
from career.services.persistence.application_repository import ApplicationIdentity, ApplicationRepository
from career.utils import ValidationFailure


class IdentityFirewallTests(unittest.TestCase):
    def test_default_database_is_the_control_plane_database(self):
        database = Database()
        self.addCleanup(database.close)

        self.assertEqual(database.db_path, ROOT / "control-plane" / "career.db")

    def test_unscoped_derived_producers_fail_closed(self):
        with self.assertRaisesRegex(ValidationFailure, "explicit_application_scope_required"):
            derived_context.resolve_active_job_context()
        with self.assertRaisesRegex(ValidationFailure, "explicit_application_scope_required"):
            derived_context.build_all_for_fit_map()

    def test_explicit_application_paths_are_the_only_derived_context_selector(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            apps_root = Path(temporary_dir) / ".career-state" / "applications_v2"
            paths = application_context.paths_for("conexa_578", root=apps_root)
            paths.app_dir.mkdir(parents=True)
            paths.identity.write_text(
                '{"company":"Conexa","role":"Diretor de Growth","source_type":"notion"}',
                encoding="utf-8",
            )
            paths.job_description.write_text(
                "# Diretor de Growth — Conexa\n\nEmpresa: Conexa\n\n" + "Descricao completa " * 40,
                encoding="utf-8",
            )

            resolved = derived_context.resolve_active_job_context(paths)
            materialized = derived_context.build_all_for_fit_map(paths)

        self.assertEqual(resolved.company, "Conexa")
        self.assertEqual(resolved.role, "Diretor de Growth")
        self.assertEqual(materialized["manifest"]["application_id"], "conexa_578")

    def test_unscoped_post_processing_producers_fail_closed(self):
        with self.assertRaisesRegex(ValidationFailure, "explicit_application_scope_required"):
            feras.build_current_feras()
        with self.assertRaisesRegex(ValidationFailure, "explicit_application_scope_required"):
            cover_letter.build_current_cover_letter()
        with self.assertRaisesRegex(ValidationFailure, "explicit_application_scope_required"):
            cv_content.build_current_cv_content()

    def test_supervisor_finalizer_requires_application_scope(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            supervisor = HarnessSupervisor(Path(temporary_dir))
            self.addCleanup(supervisor.db.close)

            result = supervisor._finalize_fit_map_pipeline()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker_reason"], "explicit_application_scope_required")

    def test_supervisor_finalizer_uses_the_declared_application_paths(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            supervisor = HarnessSupervisor(root)
            self.addCleanup(supervisor.db.close)
            ApplicationRepository(supervisor.db).create_application(
                ApplicationIdentity(
                    application_id="conexa_578",
                    company="Conexa",
                    role="Diretor de Growth",
                    fingerprint="fingerprint-578",
                )
            )
            scoped_draft = root / ".career-state" / "applications_v2" / "conexa_578" / "fit_map.draft.json"
            scoped_draft.parent.mkdir(parents=True)
            scoped_draft.write_text("{}", encoding="utf-8")
            (root / ".career-state").mkdir(exist_ok=True)
            (root / ".career-state" / "fit_map.draft.json").write_text("{not-json", encoding="utf-8")

            result = supervisor._finalize_fit_map_pipeline(application_id="conexa_578")

        self.assertEqual(result["status"], "blocked")
        self.assertNotEqual(result.get("blocker_reason"), "explicit_application_scope_required")
        self.assertIn("cargo must be a non-empty string", str(result))

    def test_cli_fit_map_and_derive_reject_global_scope(self):
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as fit_map_exit:
            cli.main(["fit-map", "status"])
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as derive_exit:
            cli.main(["derive", "all-for-fit-map"])

        self.assertEqual(fit_map_exit.exception.code, 2)
        self.assertEqual(derive_exit.exception.code, 2)

    def test_cli_fit_map_status_uses_the_declared_application_path(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            apps_root = Path(temporary_dir) / ".career-state" / "applications_v2"
            expected = apps_root / "conexa_578" / "fit_map.json"
            output = StringIO()
            with mock.patch.object(application_context, "APPLICATIONS_DIR", apps_root), redirect_stdout(output):
                exit_code = cli.main(
                    ["fit-map", "status", "--application-id", "conexa_578"]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn(str(expected), output.getvalue())


if __name__ == "__main__":
    unittest.main()
