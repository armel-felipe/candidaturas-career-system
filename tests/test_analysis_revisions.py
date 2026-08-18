from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career.services.database import Database
from career.services.persistence.analysis_repository import AnalysisRepository
from career.services.persistence.application_repository import (
    ApplicationIdentity,
    ApplicationRepository,
)
from career.services.persistence.reference_repository import ReferenceRepository
from career.utils import sha256_text


class AnalysisRevisionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db = Database(db_path=Path(self.tempdir.name) / "runtime.db")
        self.addCleanup(self.db.close)
        self.applications = ApplicationRepository(self.db)
        self.analysis = AnalysisRepository(self.db)
        self.references = ReferenceRepository(self.db)
        self.applications.create_application(
            ApplicationIdentity(
                application_id="app-conexa",
                company="Conexa",
                role="Diretor de Growth",
                notion_id="578",
                fingerprint="fp-conexa",
            )
        )

    def test_create_revision_keeps_prior_fit_map_story_snapshot_immutable(self) -> None:
        revision_one_payload = {
            "metadata": {"job_fingerprint": "fp-conexa", "source": "notion_578"},
            "scores": {
                "final": 7.4,
                "aderencia": {
                    "score": 7.4,
                    "rationale": "Boa aderencia com growth e operacoes.",
                },
            },
            "dimensions": {
                "escopo": {
                    "score": 8.2,
                    "evidence_summary": "Liderou operacoes complexas.",
                    "gap_summary": "",
                }
            },
            "keywords": [
                {
                    "keyword": "growth",
                    "coverage": "covered_exact",
                    "importance": 0.95,
                    "evidence": "Expansao de 400 para 800 cidades.",
                },
                {
                    "keyword": "operacoes",
                    "coverage": "covered_exact",
                    "importance": 0.89,
                    "evidence": "Budget de R$300MM/ano.",
                },
            ],
            "evidence": [
                {
                    "evidence_key": "expansao_geografica",
                    "evidence_text": "Expansao de 400 para 800 cidades.",
                    "metric": "400-800 cidades",
                }
            ],
            "objections": [
                {
                    "objection_key": "startup_gap",
                    "objection_text": "Nao veio de startup pequena recente.",
                    "response_text": "Atuou em ambiente de construcao na WeHandle.",
                }
            ],
            "stories": [
                {
                    "story_key": "ifood_growth",
                    "title": "Escala operacional",
                    "narrative": "Conduzi a expansao de 400 para 800 cidades.",
                }
            ],
        }
        revision_two_payload = {
            "metadata": {"job_fingerprint": "fp-conexa", "source": "notion_578"},
            "scores": {
                "final": 8.1,
                "aderencia": {
                    "score": 8.1,
                    "rationale": "Ajuste final mais forte para growth.",
                },
            },
            "dimensions": {
                "escopo": {
                    "score": 8.7,
                    "evidence_summary": "Escopo reforcado.",
                    "gap_summary": "",
                }
            },
            "keywords": [
                {
                    "keyword": "growth",
                    "coverage": "covered_exact",
                    "importance": 0.99,
                    "evidence": "Expansao de 400 para 800 cidades e CX.",
                },
                {
                    "keyword": "governanca",
                    "coverage": "covered_similar",
                    "importance": 0.77,
                    "evidence": "Ritos executivos mensais.",
                },
            ],
            "evidence": [
                {
                    "evidence_key": "expansao_geografica",
                    "evidence_text": "Expansao de 400 para 800 cidades e consolidacao de CX.",
                    "metric": "400-800 cidades",
                }
            ],
            "objections": [
                {
                    "objection_key": "startup_gap",
                    "objection_text": "Nao veio de startup pequena recente.",
                    "response_text": "Atuou em ambiente de construcao na WeHandle.",
                }
            ],
            "stories": [
                {
                    "story_key": "ifood_growth",
                    "title": "Escala operacional revisada",
                    "narrative": "Reforcei a narrativa com growth, CX e margem.",
                }
            ],
        }

        revision_one = self.analysis.create_revision(
            "app-conexa", revision_one_payload, source_hash="fit-source-v1"
        )
        revision_two = self.analysis.create_revision(
            "app-conexa", revision_two_payload, source_hash="fit-source-v2"
        )

        current = self.analysis.get_current("app-conexa")

        self.assertEqual(current.revision_id, revision_two)
        self.assertEqual(current.source_hash, "fit-source-v2")
        self.assertEqual(current.score_final, 8.1)
        self.assertEqual(current.stories[0].narrative, revision_two_payload["stories"][0]["narrative"])
        self.assertEqual(current.keywords[0].keyword, "growth")
        self.assertEqual(current.keywords[0].importance, 0.99)
        self.assertEqual(current.dimensions[0].dimension_key, "escopo")
        self.assertEqual(current.dimensions[0].score, 8.7)
        self.assertEqual(current.objections[0].objection_key, "startup_gap")
        self.assertEqual(
            current.objections[0].response_text,
            "Atuou em ambiente de construcao na WeHandle.",
        )

        prior_revision = self.db.fetch_one(
            """SELECT payload_json, score_final, payload_hash FROM fit_map_revisions
               WHERE revision_id = ?""",
            (revision_one,),
        )
        self.assertIsNotNone(prior_revision)
        self.assertEqual(prior_revision["score_final"], 7.4)
        self.assertEqual(
            prior_revision["payload_hash"],
            sha256_text(str(prior_revision["payload_json"])),
        )
        self.assertEqual(
            json.loads(str(prior_revision["payload_json"]))["stories"][0]["narrative"],
            revision_one_payload["stories"][0]["narrative"],
        )

        prior_story = self.db.fetch_one(
            """SELECT narrative FROM fit_map_stories
               WHERE revision_id = ? AND story_key = ?""",
            (revision_one, "ifood_growth"),
        )
        self.assertIsNotNone(prior_story)
        self.assertEqual(
            prior_story["narrative"],
            revision_one_payload["stories"][0]["narrative"],
        )

    def test_create_revision_rejects_stale_payload_hash_and_preserves_source_hash(self) -> None:
        with self.assertRaisesRegex(ValueError, "payload_hash does not match canonical payload"):
            self.analysis.create_revision(
                "app-conexa",
                {
                    "metadata": {
                        "job_fingerprint": "fp-conexa",
                        "payload_hash": "stale-hash",
                    },
                    "scores": {"final": 7.1},
                    "stories": [
                        {
                            "story_key": "base_story",
                            "title": "Base",
                            "narrative": "Narrativa base.",
                        }
                    ],
                },
                source_hash="fit-source-v1",
            )

        revision_id = self.analysis.create_revision(
            "app-conexa",
            {
                "metadata": {"job_fingerprint": "fp-conexa"},
                "scores": {"final": 7.1},
                "stories": [
                    {
                        "story_key": "base_story",
                        "title": "Base",
                        "narrative": "Narrativa base.",
                    }
                ],
            },
            source_hash="fit-source-v1",
        )

        row = self.db.fetch_one(
            """SELECT source_hash, payload_hash, payload_json
               FROM fit_map_revisions WHERE revision_id = ?""",
            (revision_id,),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["source_hash"], "fit-source-v1")
        self.assertEqual(row["payload_hash"], sha256_text(str(row["payload_json"])))

    def test_create_positioning_revision_attaches_snapshot_to_current_analysis(self) -> None:
        analysis_revision_id = self.analysis.create_revision(
            "app-conexa",
            {
                "metadata": {"job_fingerprint": "fp-conexa"},
                "scores": {"final": 7.8},
                "stories": [
                    {
                        "story_key": "base_story",
                        "title": "Base",
                        "narrative": "Narrativa base.",
                    }
                ],
            },
            source_hash="fit-source-v1",
        )

        positioning_snapshot = {
            "headline": "Executivo de growth com disciplina operacional.",
            "stories": [
                {
                    "story_key": "feras",
                    "title": "FERAS",
                    "narrative": "Eu conecto crescimento, margem e execucao.",
                }
            ],
            "principles": [
                {
                    "principle_key": "opening",
                    "content": "Comecar pela tese de impacto mensuravel.",
                }
            ],
        }

        positioning_revision_id = self.analysis.create_positioning_revision(
            "app-conexa",
            source_revision_id=analysis_revision_id,
            snapshot=positioning_snapshot,
        )

        current = self.analysis.get_current("app-conexa")

        self.assertIsNotNone(current.positioning)
        assert current.positioning is not None
        self.assertEqual(current.positioning.revision_id, positioning_revision_id)
        self.assertEqual(current.positioning.source_revision_id, analysis_revision_id)
        self.assertEqual(current.positioning.snapshot["headline"], positioning_snapshot["headline"])
        self.assertEqual(current.positioning.stories[0].story_key, "feras")
        self.assertEqual(
            current.positioning.principles[0].content,
            "Comecar pela tese de impacto mensuravel.",
        )
        self.assertEqual(
            current.positioning.payload_hash,
            sha256_text(json.dumps(positioning_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        )

    def test_create_positioning_revision_rejects_stale_payload_hash(self) -> None:
        analysis_revision_id = self.analysis.create_revision(
            "app-conexa",
            {
                "metadata": {"job_fingerprint": "fp-conexa"},
                "scores": {"final": 7.8},
                "stories": [
                    {
                        "story_key": "base_story",
                        "title": "Base",
                        "narrative": "Narrativa base.",
                    }
                ],
            },
            source_hash="fit-source-v1",
        )

        with self.assertRaisesRegex(ValueError, "payload_hash does not match canonical payload"):
            self.analysis.create_positioning_revision(
                "app-conexa",
                source_revision_id=analysis_revision_id,
                snapshot={
                    "payload_hash": "stale-positioning-hash",
                    "headline": "Executivo de growth com disciplina operacional.",
                    "stories": [
                        {
                            "story_key": "feras",
                            "title": "FERAS",
                            "narrative": "Eu conecto crescimento, margem e execucao.",
                        }
                    ],
                },
            )

    def test_reference_repository_versions_json_and_preserves_content(self) -> None:
        candidate_reference_v1 = json.dumps(
            {
                "candidate": {"name": "Felipe Armel", "email": "armelfelipe@gmail.com"},
                "stack": "SQL · Python · Tableau",
                "experiences": [
                    {
                        "id": "ifood_director",
                        "company": "iFood",
                        "role": "Diretor de Operacoes",
                        "scope_bullet": "Liderei operacoes de grande porte.",
                        "result_bullet": "Expansao de 400 para 800 cidades.",
                        "leverage": {
                            "default": "Conduzi S&OP executivo e budget de R$300MM/ano."
                        },
                    }
                ],
            },
            ensure_ascii=False,
        )
        candidate_reference_v2 = json.dumps(
            {
                "candidate": {"name": "Felipe Armel", "email": "armelfelipe@gmail.com"},
                "stack": "SQL · Python · Tableau",
                "experiences": [
                    {
                        "id": "ifood_director",
                        "company": "iFood",
                        "role": "Diretor de Operacoes",
                        "scope_bullet": "Liderei operacoes de grande porte e CX.",
                        "result_bullet": "Expansao de 400 para 800 cidades.",
                        "leverage": {
                            "default": "Conduzi S&OP executivo, CX e budget de R$300MM/ano."
                        },
                    }
                ],
            },
            ensure_ascii=False,
        )

        first_reference = self.references.upsert_version(
            kind="candidate_facts",
            key="candidate_cv_facts",
            content=candidate_reference_v1,
            source_hash="candidate-source-v1",
        )
        first_reference_again = self.references.upsert_version(
            kind="candidate_facts",
            key="candidate_cv_facts",
            content=candidate_reference_v1,
            source_hash="candidate-source-v1",
        )
        second_reference = self.references.upsert_version(
            kind="candidate_facts",
            key="candidate_cv_facts",
            content=candidate_reference_v2,
            source_hash="candidate-source-v2",
        )

        self.assertEqual(first_reference_again, first_reference)
        self.assertNotEqual(second_reference, first_reference)

        current_reference = self.references.get_current("candidate_facts", "candidate_cv_facts")
        first_version = self.references.get_version(first_reference)
        versions = self.references.list_versions("candidate_facts", "candidate_cv_facts")

        self.assertEqual(current_reference.reference_id, second_reference)
        self.assertEqual(current_reference.logical_key, "candidate_cv_facts")
        self.assertEqual(first_version.reference_id, first_reference)
        self.assertEqual(first_version.content, candidate_reference_v1)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].reference_id, second_reference)
        self.assertEqual(versions[1].reference_id, first_reference)
        self.assertEqual(versions[0].content_hash, sha256_text(candidate_reference_v2))
        self.assertEqual(versions[1].content_hash, sha256_text(candidate_reference_v1))

        fact_rows = self.db.fetch_all(
            """SELECT fact_key, fact_value FROM candidate_facts
               WHERE reference_id = ?
               ORDER BY fact_key""",
            (first_reference,),
        )
        self.assertIn(
            {"fact_key": "candidate.name", "fact_value": "Felipe Armel"},
            fact_rows,
        )
        self.assertIn(
            {"fact_key": "stack", "fact_value": "SQL · Python · Tableau"},
            fact_rows,
        )

        evidence_rows = self.db.fetch_all(
            """SELECT evidence_key, evidence_text FROM candidate_evidence
               WHERE reference_id = ?
               ORDER BY evidence_key""",
            (first_reference,),
        )
        self.assertIn(
            {
                "evidence_key": "experience.ifood_director.scope_bullet",
                "evidence_text": "Liderei operacoes de grande porte.",
            },
            evidence_rows,
        )
        self.assertIn(
            {
                "evidence_key": "experience.ifood_director.leverage.default",
                "evidence_text": "Conduzi S&OP executivo e budget de R$300MM/ano.",
            },
            evidence_rows,
        )

        translation_reference = self.references.upsert_version(
            kind="keyword_translation_registry",
            key="keyword_translation_registry",
            content=json.dumps(
                {
                    "entries": {
                        "budget_management": {
                            "canonical_keyword": "Budget Management",
                            "pt_br_preferred": "gestão orçamentária",
                            "accepted_variants": ["budget"],
                        }
                    }
                },
                ensure_ascii=False,
            ),
            source_hash="translations-v1",
        )

        translation_rows = self.db.fetch_all(
            """SELECT keyword, locale, translation, source_hash
               FROM keyword_translations
               WHERE keyword = ?
               ORDER BY keyword, locale""",
            ("Budget Management",),
        )
        self.assertEqual(len(translation_rows), 2)
        self.assertIn(
            {
                "keyword": "Budget Management",
                "locale": "canonical",
                "translation": "Budget Management",
                "source_hash": "translations-v1",
            },
            translation_rows,
        )
        self.assertIn(
            {
                "keyword": "Budget Management",
                "locale": "pt-BR",
                "translation": "gestão orçamentária",
                "source_hash": "translations-v1",
            },
            translation_rows,
        )
        translation_history = self.db.fetch_all(
            """SELECT reference_id, keyword, locale, translation, source_hash, content_hash
               FROM keyword_translation_versions
               WHERE keyword = ?
               ORDER BY locale""",
            ("Budget Management",),
        )
        self.assertEqual(len(translation_history), 2)
        self.assertTrue(all(row["reference_id"] == translation_reference for row in translation_history))
        self.assertTrue(
            all(row["content_hash"] == sha256_text(json.dumps(
                {
                    "entries": {
                        "budget_management": {
                            "canonical_keyword": "Budget Management",
                            "pt_br_preferred": "gestão orçamentária",
                            "accepted_variants": ["budget"],
                        }
                    }
                },
                ensure_ascii=False,
            )) for row in translation_history)
        )

    def test_create_revision_rejects_malformed_story_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "stories\\[0\\] requires text field"):
            self.analysis.create_revision(
                "app-conexa",
                {
                    "metadata": {"job_fingerprint": "fp-conexa"},
                    "scores": {"final": 7.4},
                    "stories": [
                        {
                            "story_key": "broken_story",
                            "title": "Quebrada",
                            "narrative": {"unexpected": "object"},
                        }
                    ],
                },
                source_hash="fit-source-v1",
            )


if __name__ == "__main__":
    unittest.main()
