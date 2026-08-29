from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from career.services import review
from career.cells import capabilities
import review_output


def test_polish_uses_declared_english_language_for_cellular_staging(monkeypatch, tmp_path):
    artifact = tmp_path / "cv.docx"
    artifact.write_bytes(b"placeholder")
    monkeypatch.setattr(
        review.legacy_review_output,
        "compact_lines",
        lambda _text: ["Summary", "Experience"],
    )
    monkeypatch.setattr(
        review.legacy_review_output,
        "docx_text",
        lambda _artifact: "Operations executive with operational excellence.",
    )
    monkeypatch.setattr(review.legacy_review_output, "is_portuguese_cv", lambda _artifact: True)

    report = review.polish_cv(artifact, tmp_path / "polish.json", language="en")

    assert report["language"] == "non-pt-BR"
    assert report["approval_blockers"] == []


def test_objective_review_uses_declared_english_language_for_cellular_staging(monkeypatch, tmp_path):
    artifact = tmp_path / "cv.docx"
    artifact.write_bytes(b"placeholder")
    monkeypatch.setattr(review_output, "docx_text", lambda _artifact: "English CV")
    monkeypatch.setattr(review_output, "compact_lines", lambda _text: ["Summary", "Experience"])
    monkeypatch.setattr(review_output, "run_docx_validator", lambda _artifact: (True, "ok"))
    monkeypatch.setattr(review_output, "find_application", lambda *_args: None)
    monkeypatch.setattr(review_output, "load_translation_registry", lambda _path: {})
    monkeypatch.setattr(review_output, "top_keyword_results", lambda *_args, **_kwargs: ([], []))
    monkeypatch.setattr(review_output, "ats_score_summary", lambda *_args, **_kwargs: {
        "score": 0.0,
        "score_max": 8,
        "minimum_score": 5.2,
        "optimal_score": 6.2,
        "level": "blocked",
        "covered_exact": 0,
        "covered_similar": 0,
        "declared_gap": 0,
        "missing_unexplained": 0,
        "missing_unexplained_keywords": [],
        "declared_gap_keywords": [],
    })
    monkeypatch.setattr(review_output, "summary_supported_by_experiences", lambda *_args: (True, "ok"))
    monkeypatch.setattr(review_output, "experience_format_check", lambda _artifact: (True, True, "ok"))
    monkeypatch.setattr(review_output, "dash_punctuation_check", lambda _artifact: (True, "ok"))
    monkeypatch.setattr(review_output, "is_portuguese_cv", lambda _artifact: True)

    report = review_output.build_cv_review(
        artifact,
        {"empresa": "X", "cargo": "Y", "keywords_habilidade_ats": []},
        {"applications": []},
        tmp_path / "translation.json",
        language="en",
    )

    assert next(item for item in report["minor_checks"] if item["id"] == "pt_cv_natural_keyword_mix")["evidence"] == "english_cv"


def test_canonical_subprocess_environment_forwards_rclone_configuration(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG", "/opt/data/.config/rclone/rclone.conf")
    monkeypatch.setenv("RCLONE_ONEDRIVE_REMOTE", "onedrive")
    monkeypatch.setenv("RCLONE_ONEDRIVE_DELIVERY_DIR", "01_armel/Curriculos/personalizados")

    environment = capabilities.canonical_subprocess_environment()

    assert environment["RCLONE_CONFIG"] == "/opt/data/.config/rclone/rclone.conf"
    assert environment["RCLONE_ONEDRIVE_REMOTE"] == "onedrive"
    assert environment["RCLONE_ONEDRIVE_DELIVERY_DIR"] == "01_armel/Curriculos/personalizados"

    legacy_environment = review_output._canonical_subprocess_environment()
    assert legacy_environment["RCLONE_CONFIG"] == "/opt/data/.config/rclone/rclone.conf"
