from __future__ import annotations

import re
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from career import cli
from career.services import application_context, intake, multiagent
from career.services.database import Database
from career.utils import CareerError, read_json, write_json


class Task31FinalScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.root = Path(self.temporary_dir.name)
        self.career_state = self.root / ".career-state"
        self.applications_dir = self.career_state / "applications_v2"
        self.database = Database(self.root / "control-plane" / "career.db")
        self.addCleanup(self.database.close)

    @contextmanager
    def _runtime(self):
        with mock.patch.object(application_context, "ROOT", self.root), mock.patch.object(
            application_context, "CAREER_STATE", self.career_state
        ), mock.patch.object(
            application_context, "APPLICATIONS_DIR", self.applications_dir
        ), mock.patch.object(application_context, "canonical_database", return_value=self.database), mock.patch.object(
            intake, "ROOT", self.root
        ), mock.patch.object(intake, "CAREER_STATE", self.career_state), mock.patch.object(
            intake, "INBOX", self.root / "inbox"
        ), mock.patch.object(multiagent, "ROOT", self.root):
            yield

    def _create_application(self, application_id: str = "notion_578"):
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
        write_json(paths.fit_map, {"cargo": "Diretor de Growth", "empresa": "Conexa"})
        return record, paths

    def test_real_scoped_fit_map_request_contains_no_global_paths_or_unscoped_commands(self):
        with self._runtime():
            record, _paths = self._create_application()
            previous_cwd = Path.cwd()
            try:
                os.chdir(self.root)
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "multiagent",
                            "request",
                            "fit-map",
                            "--application-id",
                            record.application_id,
                        ]
                    )
            finally:
                os.chdir(previous_cwd)
            result = json.loads(stdout.getvalue())
            payload = read_json(self.root / result["request"]["request_json"])

        self.assertEqual(exit_code, 0)
        serialized = "\n".join(self._strings(payload))
        self.assertIn(
            ".career-state/applications_v2/notion_578/fit_map.draft.json",
            serialized,
        )
        self.assertNotIn(".career-state/fit_map.json", serialized)
        self.assertNotIn(".career-state/fit_map.draft.json", serialized)
        self.assertNotIn(".career-state/derived/", serialized)
        for command in self._commands(payload):
            self.assertIn("--application-id notion_578", command, command)

    def test_habilidades_unknown_application_fails_before_reading_fit_map(self):
        with self._runtime(), mock.patch.object(
            cli.habilidades_chave_service,
            "check_environment",
            side_effect=AssertionError("FIT_MAP must not be read for unknown application"),
        ):
            with self.assertRaisesRegex(CareerError, "canonical SQLite"):
                cli.main(
                    [
                        "habilidades-chave",
                        "check",
                        "--application-id",
                        "notion_999",
                    ]
                )

    def test_habilidades_foreign_fit_map_fails_before_reading_artifact(self):
        with self._runtime():
            record, _paths = self._create_application()
            foreign = self.career_state / "fit_map.json"
            write_json(foreign, {"cargo": "wrong"})
            with mock.patch.object(
                cli.habilidades_chave_service,
                "check_environment",
                side_effect=AssertionError("foreign FIT_MAP must not be read"),
            ):
                with self.assertRaisesRegex(CareerError, "application FIT_MAP"):
                    cli.main(
                        [
                            "habilidades-chave",
                            "check",
                            "--application-id",
                            record.application_id,
                            "--fit-map",
                            str(foreign),
                        ]
                    )

    @staticmethod
    def _strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from Task31FinalScopeTests._strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from Task31FinalScopeTests._strings(item)

    @staticmethod
    def _commands(payload: dict):
        for value in Task31FinalScopeTests._strings(payload):
            if re.search(r"(?:npm run|scripts/career_cli\.py|career )", value):
                yield value


if __name__ == "__main__":
    unittest.main()
