from __future__ import annotations

import json

from career.services.database import Database
from career.services.persistence.reference_repository import ReferenceRepository


def test_candidate_evidence_reference_indexes_story_and_claims() -> None:
    database = Database(":memory:")
    repository = ReferenceRepository(database)
    content = json.dumps(
        {
            "schema_version": 1,
            "candidate": {"name": "Felipe Armel"},
            "stories": [
                {
                    "story_id": "story_one",
                    "title": "História um",
                    "context": "Contexto",
                    "actions": ["Ação"],
                    "results": ["Resultado"],
                    "metrics": ["13%"],
                    "capabilities": ["operações"],
                    "allowed_claims": ["Claim autorizado"],
                    "source_refs": [
                        {"path": "autoconhecimento.md", "lines": "1-2"}
                    ],
                    "artifact_guidance": {"cv": "Formulação curta"},
                }
            ],
        },
        ensure_ascii=False,
    )

    reference_id = repository.upsert_version(
        "candidate_evidence", "candidate", content, "source-v1"
    )

    fact_rows = database.fetch_all(
        "SELECT fact_key, fact_value FROM candidate_facts WHERE reference_id = ?",
        (reference_id,),
    )
    evidence_rows = database.fetch_all(
        "SELECT evidence_key, evidence_text FROM candidate_evidence WHERE reference_id = ?",
        (reference_id,),
    )

    assert {row["fact_key"] for row in fact_rows} >= {
        "candidate.name",
        "story.story_one.title",
        "story.story_one.capability.0",
    }
    assert {
        (row["evidence_key"], row["evidence_text"])
        for row in evidence_rows
    } >= {
        ("story.story_one.allowed_claim.0", "Claim autorizado"),
        ("story.story_one.source_ref.0", "autoconhecimento.md:1-2"),
        ("story.story_one.result.0", "Resultado"),
    }
