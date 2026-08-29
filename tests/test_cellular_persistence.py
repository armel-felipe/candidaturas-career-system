from __future__ import annotations

import unittest

from career.services.cellular_persistence import (
    intake_texts_equivalent,
    build_delivery_binding,
    build_notion_binding,
    registry_entry_matches_application,
    reconciliation_cv_language,
)


class CellularPersistenceTests(unittest.TestCase):
    def test_reconciliation_uses_persisted_job_language_not_an_english_default(self) -> None:
        self.assertEqual(
            reconciliation_cv_language(
                current_language="en",
                job_description="Sobre a vaga\n\nBuscamos um gerente com experiência em operações.",
            ),
            "pt-BR",
        )

    def test_registry_matching_uses_fit_map_role_when_intake_role_has_suffix(self) -> None:
        self.assertTrue(
            registry_entry_matches_application(
                {
                    "application_id": None,
                    "company": "Tempo",
                    "role": "Gerente de Planejamento Estratégico",
                },
                application_id="local_tempo",
                application_company="Tempo",
                application_role="Gerente de Planejamento EstratégicoBarueri - SPFull-time employee",
                fit_map={
                    "empresa": "Tempo",
                    "cargo": "Gerente de Planejamento Estratégico",
                },
            )
        )

    def test_intake_equivalence_ignores_only_extraction_timestamp(self) -> None:
        original = "# Role\n\nExtraído em: 2026-08-25T23:54:04.429Z\n\nBody"
        refreshed = "# Role\n\nExtraído em: 2026-08-26T00:21:36.318Z\n\nBody"

        self.assertTrue(intake_texts_equivalent(original, refreshed))
        self.assertFalse(intake_texts_equivalent(original, original + "\nchanged"))

    def test_delivery_binding_contains_projection_semantics_and_external_evidence(self) -> None:
        payload = build_delivery_binding(
            application_id="app-1",
            artifact_version_id="artv-1",
            artifact_hash="a" * 64,
            source_revision_id="fit-1",
            positioning_revision_id=None,
            run_id="run-cv-1",
            external_report_path="/tmp/delivery.json",
            external_report_hash="b" * 64,
            destination="onedrive:01_armel/Curriculos/personalizados/cv_en.docx",
            filename="cv_en.docx",
        )

        self.assertEqual(payload["status"], "delivered")
        self.assertEqual(payload["application_id"], "app-1")
        self.assertEqual(payload["artifact_version_id"], "artv-1")
        self.assertEqual(payload["source_revision_id"], "fit-1")
        self.assertEqual(payload["run_id"], "run-cv-1")
        self.assertEqual(payload["external_report_hash"], "b" * 64)

    def test_notion_binding_preserves_page_identity_and_cv_lineage(self) -> None:
        payload = build_notion_binding(
            application_id="app-1",
            record_id="notion:page-1",
            page_id="page-1",
            url="https://app.notion.com/p/page-1",
            artifact_version_id="artv-1",
            artifact_hash="a" * 64,
            source_revision_id="fit-1",
            positioning_revision_id=None,
            run_id="run-cv-1",
            external_receipt_path="/tmp/notion.json",
            external_receipt_hash="c" * 64,
        )

        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["record_id"], "notion:page-1")
        self.assertEqual(payload["page_id"], "page-1")
        self.assertEqual(payload["artifact_version_id"], "artv-1")
        self.assertEqual(payload["external_receipt_hash"], "c" * 64)


if __name__ == "__main__":
    unittest.main()
