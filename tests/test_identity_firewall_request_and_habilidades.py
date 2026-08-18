from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest import mock

from career import cli
from career.services import application_context, intake, multiagent
from career.services.database import Database
from career.utils import CareerError, ValidationFailure, read_json, write_json


class IdentityFirewallRequestAndHabilidadesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.database = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)

    @contextmanager
    def _application_runtime(self):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(intake, "ROOT", self.root), mock.patch.object(
            intake, "CAREER_STATE", self.career_state
        ), mock.patch.object(intake, "INBOX", self.root / "inbox"), mock.patch.object(
            multiagent, "ROOT", self.root
        ):
            yield

    def _application(self, application_id: str = "notion_578"):
        source = intake.JobSource(
            source_type="notion_record",
            source_id="578",
            company="Conexa",
            role="Diretor de Growth",
            text="Descricao Conexa " * 80,
            record_id="578",
            preferred_id=application_id,
        )
        record = intake.start_intake(source, database=self.database)
        paths = application_context.paths_for(record.application_id)
        write_json(
            paths.fit_map,
            {
                "cargo": "Diretor de Growth scoped",
                "empresa": "Conexa scoped",
            },
        )
        return record, paths

    def test_explicit_multiagent_request_uses_only_its_application_paths(self):
        """Changing the root FIT_MAP must not change an explicitly scoped request."""
        with self._application_runtime():
            record, paths = self._application()
            write_json(
                self.career_state / "fit_map.json",
                {"cargo": "GLOBAL WRONG VACANCY", "empresa": "Wrong"},
            )
            with mock.patch.object(
                multiagent, "_prepare_scoped_compact_inputs"
            ) as prepare, mock.patch.object(
                multiagent.derived_context_service,
                "configure_derived_dir",
                side_effect=AssertionError("global derived adapter must not run"),
            ), mock.patch.object(
                multiagent.derived_context_service,
                "configure_state_store_path",
                side_effect=AssertionError("global state adapter must not run"),
            ):
                result = multiagent.write_request(
                    "feras",
                    application_id=record.application_id,
                    database=self.database,
                )

        prepare.assert_called_once_with("feras", paths)
        payload = read_json(self.root / result["request_json"])
        self.assertEqual(payload["application_id"], record.application_id)
        self.assertEqual(payload["fit_map"]["cargo"], "Diretor de Growth scoped")
        self.assertTrue(
            all(
                ".career-state/fit_map.json" not in item
                and ".career-state/derived/" not in item
                for item in payload["allowed_files"]
            )
        )
        self.assertIn(
            ".career-state/applications_v2/notion_578/fit_map.json",
            payload["allowed_files"],
        )
        self.assertTrue((self.root / result["request_json"]).is_file())

    def test_multiagent_request_rejects_missing_application_scope_before_writing(self):
        with self._application_runtime():
            with self.assertRaisesRegex(ValidationFailure, "explicit application_id"):
                multiagent.write_request("feras", database=self.database)
        self.assertFalse((self.career_state / "agent_requests" / "feras_request.json").exists())

    def test_habilidades_cli_requires_scope_before_invoking_fit_map_reader(self):
        with mock.patch.object(
            cli.habilidades_chave_service,
            "check_environment",
            side_effect=AssertionError("global FIT_MAP must not be read"),
        ):
            with self.assertRaises(SystemExit) as raised, mock.patch("sys.stderr", new=StringIO()):
                cli.main(["habilidades-chave", "check"])

        self.assertEqual(raised.exception.code, 2)

    def test_habilidades_cli_uses_application_fit_map_and_rejects_foreign_override(self):
        with self._application_runtime():
            paths = application_context.paths_for("notion_578")
            foreign_fit_map = self.career_state / "fit_map.json"
            with mock.patch.object(
                cli.habilidades_chave_service,
                "check_environment",
                return_value={"status": "ok"},
            ) as check_environment, mock.patch("sys.stdout", new=StringIO()):
                exit_code = cli.main(
                    [
                        "habilidades-chave",
                        "check",
                        "--application-id",
                        "notion_578",
                    ]
                )

            self.assertEqual(exit_code, 0)
            check_environment.assert_called_once_with(paths.fit_map)

            with self.assertRaisesRegex(CareerError, "application FIT_MAP"), mock.patch.object(
                cli.habilidades_chave_service,
                "check_environment",
                side_effect=AssertionError("foreign FIT_MAP must not be read"),
            ):
                cli.main(
                    [
                        "habilidades-chave",
                        "check",
                        "--application-id",
                        "notion_578",
                        "--fit-map",
                        str(foreign_fit_map),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
