"""Canonical language detection for persisted job applications."""

from __future__ import annotations


_ENGLISH_MARKERS = (
    " about the role ",
    " about the job ",
    " job summary ",
    " job description ",
    " the role ",
    " responsibilities ",
    " requirements ",
    " qualifications ",
    " what you'll ",
    " you will ",
    " we're looking ",
    " cross-functional ",
    " stakeholders ",
    " business operations ",
    " supply chain ",
    " customer success ",
)

_PORTUGUESE_MARKERS = (
    " sobre a vaga ",
    " responsabilidades ",
    " requisitos ",
    " qualificações ",
    " qualificacoes ",
    " o que buscamos ",
    " buscamos ",
    " você ",
    " voce ",
    " atuação ",
    " atuacao ",
    " experiência ",
    " experiencia ",
)


def detect_job_language(text: str) -> str:
    """Return the CV language for a possibly mixed-language job document."""
    normalized = " " + " ".join((text or "").casefold().split()) + " "
    english_score = sum(normalized.count(marker) for marker in _ENGLISH_MARKERS)
    portuguese_score = sum(normalized.count(marker) for marker in _PORTUGUESE_MARKERS)
    return "en" if english_score > portuguese_score else "pt-BR"
