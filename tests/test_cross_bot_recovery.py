from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)


class CrossBotRecoveryTests(unittest.TestCase):
    def test_same_notion_identity_has_multiple_locations_but_one_application(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            db = Database(db_path=root / "career.db")
            self.addCleanup(db.close)
            repository = ApplicationRepository(db)
            repository.create_application(
                ApplicationIdentity(
                    application_id="notion_578",
                    company="Conexa",
                    role="Diretor de Growth",
                    notion_id="578",
                    fingerprint="fp-conexa",
                )
            )
            for bot_id in ("vagas_bot_01", "vagas_bot_02"):
                app_dir = root / "workspaces" / bot_id / "state" / "applications_v2" / "notion_578"
                (app_dir / "derived").mkdir(parents=True)
                (app_dir / "derived" / "manifest.json").write_text(
                    json.dumps({"application_id": "notion_578", "fingerprint": "fp-conexa"}),
                    encoding="utf-8",
                )

            report = repository.reindex_from_manifests(root)

            self.assertEqual(report.conflicts, ())
            self.assertEqual(len(repository.list_by_bot()), 1)
            self.assertEqual(len(repository.list_by_bot("vagas_bot_01")), 1)
            self.assertEqual(len(repository.list_by_bot("vagas_bot_02")), 1)
            locations = db.fetch_all(
                "SELECT bot_id FROM application_locations WHERE application_id = ? ORDER BY bot_id",
                ("notion_578",),
            )
            self.assertEqual([row["bot_id"] for row in locations], ["vagas_bot_01", "vagas_bot_02"])


if __name__ == "__main__":
    unittest.main()
