from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from career.paths import ROOT
from career.schemas.candidate_evidence import validate_candidate_evidence
from career.utils import read_json, write_json


CANDIDATE_EVIDENCE_PATH = ROOT / ".agents/skills/career-system/references/candidate_evidence.json"
LEGACY_CV_FACTS_PATH = ROOT / ".agents/skills/career-system/references/candidate_cv_facts.json"


def load_candidate_evidence(path: Path | None = None) -> dict[str, Any]:
    source = Path(path or CANDIDATE_EVIDENCE_PATH)
    payload = read_json(source)
    return validate_candidate_evidence(payload)


def build_cv_facts_view(
    evidence: Mapping[str, Any],
    *,
    legacy_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validated = validate_candidate_evidence(evidence)
    base = deepcopy(dict(legacy_facts)) if legacy_facts is not None else read_json(LEGACY_CV_FACTS_PATH)
    if not isinstance(base, dict):
        raise ValueError("legacy candidate CV facts must be an object")
    experiences = base.setdefault("experiences", [])
    if not isinstance(experiences, list):
        raise ValueError("legacy candidate CV facts experiences must be an array")
    by_id = {
        str(item.get("id")): index
        for index, item in enumerate(experiences)
        if isinstance(item, Mapping) and str(item.get("id") or "").strip()
    }
    for story in validated["stories"]:
        cv_facts = story.get("cv_facts")
        if not isinstance(cv_facts, Mapping):
            continue
        experience_id = str(story.get("experience_id") or story["story_id"]).strip()
        if not experience_id:
            continue
        item = {"id": experience_id, **dict(cv_facts)}
        if experience_id in by_id:
            existing = dict(experiences[by_id[experience_id]])
            existing.update(item)
            experiences[by_id[experience_id]] = existing
        else:
            experiences.append(item)
            by_id[experience_id] = len(experiences) - 1
    return base


def rebuild_candidate_facts(
    *,
    evidence_path: Path | None = None,
    legacy_facts_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Path]:
    evidence = load_candidate_evidence(evidence_path)
    legacy_path = Path(legacy_facts_path or LEGACY_CV_FACTS_PATH)
    rebuilt = build_cv_facts_view(evidence, legacy_facts=read_json(legacy_path))
    destination = Path(output_path or legacy_path)
    write_json(destination, rebuilt)
    return {
        "evidence": Path(evidence_path or CANDIDATE_EVIDENCE_PATH),
        "output": destination,
    }
