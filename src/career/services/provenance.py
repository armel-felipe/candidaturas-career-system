from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from career.paths import ROOT
from career.services.application_context import ApplicationPaths
from career.utils import ValidationFailure, sha256_file

CV_FACTS_PATH = ROOT / ".agents/skills/career-system/references/candidate_cv_facts.json"
CANDIDATE_EVIDENCE_PATH = ROOT / ".agents/skills/career-system/references/candidate_evidence.json"

CANDIDATE_FACT_SOURCES: tuple[Path, ...] = (
    ROOT / ".agents/skills/career-system/references/dicionario_palavras_chave_mercado.md",
    ROOT / ".agents/skills/career-system/references/palavras_chave_carreira.md",
    ROOT / ".agents/skills/career-system/references/autoconhecimento.md",
    ROOT / ".agents/skills/career-system/references/perfil_restricoes.md",
    CV_FACTS_PATH,
    CANDIDATE_EVIDENCE_PATH,
)


def candidate_facts_revision(sources: Iterable[Path] | None = None) -> str:
    """Return a stable revision for the read-only candidate facts used by cells."""
    digest = hashlib.sha256()
    sources = sources or (
        ROOT / ".agents/skills/career-system/references/dicionario_palavras_chave_mercado.md",
        ROOT / ".agents/skills/career-system/references/palavras_chave_carreira.md",
        ROOT / ".agents/skills/career-system/references/autoconhecimento.md",
        ROOT / ".agents/skills/career-system/references/perfil_restricoes.md",
        CV_FACTS_PATH,
        CANDIDATE_EVIDENCE_PATH,
    )
    resolved_sources = sorted((Path(path).resolve() for path in sources), key=str)
    if not resolved_sources:
        raise ValidationFailure("candidate facts sources are empty")
    for path in resolved_sources:
        if not path.is_file():
            raise ValidationFailure(f"candidate facts source is missing: {path}")
        try:
            relative = path.relative_to(ROOT.resolve())
        except ValueError:
            relative = path
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fit_map_provenance(
    application_paths: ApplicationPaths,
    *,
    candidate_revision: str,
    draft_path: Path,
    contract_version: str,
    produced_by_attempt: int,
) -> dict[str, Any]:
    _assert_application_path(application_paths, draft_path, "FIT_MAP draft")
    if not application_paths.job_description.is_file():
        raise ValidationFailure(
            f"application job description is missing: {application_paths.job_description}"
        )
    if not draft_path.is_file():
        raise ValidationFailure(f"FIT_MAP draft is missing: {draft_path}")
    if not _is_sha256(candidate_revision):
        raise ValidationFailure("candidate facts revision must be a SHA-256 digest")
    if not str(contract_version).strip():
        raise ValidationFailure("FIT_MAP contract version is required")
    if not isinstance(produced_by_attempt, int) or produced_by_attempt < 1:
        raise ValidationFailure("FIT_MAP produced_by_attempt must be a positive integer")
    return {
        "job_fingerprint": sha256_file(application_paths.job_description),
        "candidate_facts_revision": candidate_revision,
        "draft_sha256": sha256_file(draft_path),
        "contract_version": str(contract_version),
        "produced_by_attempt": produced_by_attempt,
    }


def validate_fit_map_provenance(
    payload: Mapping[str, Any],
    *,
    application_paths: ApplicationPaths,
    expected_candidate_facts_revision: str | None = None,
    expected_draft_sha256: str | None = None,
    expected_contract_version: str | None = None,
    expected_produced_by_attempt: int | None = None,
) -> dict[str, Any]:
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValidationFailure("FIT_MAP provenance is missing")
    required = {
        "job_fingerprint",
        "candidate_facts_revision",
        "draft_sha256",
        "contract_version",
        "produced_by_attempt",
    }
    missing = sorted(required - set(provenance))
    if missing:
        raise ValidationFailure(
            "FIT_MAP provenance fields are missing: " + ", ".join(missing)
        )
    if not application_paths.job_description.is_file():
        raise ValidationFailure("application job description is missing")
    actual_job_fingerprint = sha256_file(application_paths.job_description)
    if provenance.get("job_fingerprint") != actual_job_fingerprint:
        raise ValidationFailure("FIT_MAP job fingerprint mismatch")
    candidate_revision = str(provenance.get("candidate_facts_revision") or "")
    if not _is_sha256(candidate_revision):
        raise ValidationFailure("FIT_MAP candidate facts revision is invalid")
    if (
        expected_candidate_facts_revision is not None
        and candidate_revision != expected_candidate_facts_revision
    ):
        raise ValidationFailure("FIT_MAP candidate facts revision mismatch")
    draft_sha256 = str(provenance.get("draft_sha256") or "")
    if not _is_sha256(draft_sha256):
        raise ValidationFailure("FIT_MAP draft SHA-256 is invalid")
    if expected_draft_sha256 is None and application_paths.fit_map_draft.is_file():
        expected_draft_sha256 = sha256_file(application_paths.fit_map_draft)
    if expected_draft_sha256 is not None and draft_sha256 != expected_draft_sha256:
        raise ValidationFailure("FIT_MAP draft SHA-256 mismatch")
    contract_version = str(provenance.get("contract_version") or "").strip()
    if not contract_version:
        raise ValidationFailure("FIT_MAP contract version is missing")
    if (
        expected_contract_version is not None
        and contract_version != str(expected_contract_version)
    ):
        raise ValidationFailure("FIT_MAP contract version mismatch")
    attempt = provenance.get("produced_by_attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise ValidationFailure("FIT_MAP produced_by_attempt is invalid")
    if expected_produced_by_attempt is not None and attempt != expected_produced_by_attempt:
        raise ValidationFailure("FIT_MAP produced_by_attempt mismatch")
    return dict(provenance)


def _assert_application_path(
    application_paths: ApplicationPaths, path: Path, label: str
) -> Path:
    target = Path(path).resolve()
    try:
        target.relative_to(application_paths.app_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must stay within its application directory") from exc
    return target


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
