from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import notion_sync


class NotionRecordIntakeMetadataTests(unittest.TestCase):
    def test_prepare_analysis_prefers_explicit_company_and_role_properties(self) -> None:
        payload = {
            "page_id": "page-578",
            "properties": {
                "Vaga": {"text": "Diretor de Growth (Penetração & Engajamento)"},
                "empresa_int": {"text": "Conexa"},
                "Cargo": {"text": "Diretor de Growth"},
            },
            "description": "Descrição completa da vaga de Growth.",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(notion_sync, "extract_page_payload", return_value=payload):
                result = notion_sync.prepare_analysis_from_page(
                    "token",
                    "page-578",
                    root / "payloads",
                    root / "descriptions",
                    record_id=578,
                )

        self.assertEqual(result["company"], "Conexa")
        self.assertEqual(result["role"], "Diretor de Growth")
        self.assertEqual(result["job_description_path"], str(root / "descriptions" / "notion_record_578.md"))


if __name__ == "__main__":
    unittest.main()
