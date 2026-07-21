from __future__ import annotations

import json
from copy import deepcopy

import pytest

from career.services import cv_content, provenance
from career.utils import ValidationFailure


def test_canonical_cv_facts_json_is_revisioned_and_drives_values(tmp_path, monkeypatch):
    facts_path = tmp_path / "candidate_cv_facts.json"
    facts = json.loads(cv_content.CV_FACTS_PATH.read_text(encoding="utf-8"))
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    monkeypatch.setattr(cv_content, "CV_FACTS_PATH", facts_path)
    monkeypatch.setattr(provenance, "CV_FACTS_PATH", facts_path)

    original_revision = provenance.candidate_facts_revision()
    original = cv_content.load_canonical_cv_facts()
    changed = deepcopy(facts)
    changed["candidate"]["location"] = "Canonical Test Location"
    facts_path.write_text(json.dumps(changed), encoding="utf-8")

    assert provenance.candidate_facts_revision() != original_revision
    assert cv_content.load_canonical_cv_facts()["candidate"]["location"] == "Canonical Test Location"
    with pytest.raises(ValidationFailure):
        cv_content.validate_canonical_provenance({"metadata": {"candidate_facts_revision": original_revision}})
