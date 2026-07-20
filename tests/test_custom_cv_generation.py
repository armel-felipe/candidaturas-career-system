import json
import os
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parent.parent
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _experience(role: str, period: str) -> dict:
    return {"role": role, "company": "Example Co.", "period": period, "bullets": ["Scope", "Action", "Result"]}


def english_payload() -> dict:
    return {
        "metadata": {"language": "en"},
        "output_name": "fixture_en.docx",
        "summary": "Operations leader with proven results.",
        "experiences": [
            _experience("Head of Operations", "May 2024 — Present"),
            _experience("Operations Director", "Apr 2022 — Mar 2024"),
            _experience("Operations Manager", "Jan 2018 — Mar 2022"),
            _experience("Planning Manager", "Jan 2015 — Dec 2017"),
        ],
        "education": ["Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)"],
        "stack": "SQL · Python",
        "languages": ["Portuguese — Native", "English — Advanced"],
    }


def portuguese_payload() -> dict:
    return {
        "metadata": {"language": "pt-BR"},
        "output_name": "fixture.docx",
        "resumo": "Líder de operações com resultados comprovados.",
        "experiencias": [
            {"cargo": "Head de Operações", "empresa": "Empresa Exemplo", "periodo": "maio/2024 — Atual", "bullets": ["Escopo", "Ação", "Resultado"]},
            {"cargo": "Diretor de Operações", "empresa": "Empresa Exemplo", "periodo": "abr/2022 — mar/2024", "bullets": ["Escopo", "Ação", "Resultado"]},
            {"cargo": "Gerente de Operações", "empresa": "Empresa Exemplo", "periodo": "jan/2018 — mar/2022", "bullets": ["Escopo", "Ação", "Resultado"]},
            {"cargo": "Gerente de Planejamento", "empresa": "Empresa Exemplo", "periodo": "jan/2015 — dez/2017", "bullets": ["Escopo", "Ação", "Resultado"]},
        ],
        "formacao": ["Engenheiro Químico — Faculdades Oswaldo Cruz (2014)"],
        "stack": "SQL · Python",
        "idiomas": ["Português — Nativo", "Inglês — Avançado"],
    }


def render_cv(payload: dict, tmp_path: Path) -> str:
    content_path = tmp_path / "cv_content.json"
    content_path.write_text(json.dumps(payload), encoding="utf-8")
    env = {**os.environ, "CAREER_CV_CONTENT": str(content_path), "CAREER_OUTPUTS": str(tmp_path)}
    subprocess.run(["node", "scripts/docx/generate_custom_cv.js"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    with zipfile.ZipFile(tmp_path / payload["output_name"]) as docx:
        root = ElementTree.fromstring(docx.read("word/document.xml"))
    return "\n".join(node.text or "" for node in root.findall(".//w:t", NS))


def test_english_cv_has_only_english_labels_and_canonical_degree(tmp_path):
    text = render_cv(english_payload(), tmp_path)
    assert "Education" in text
    assert "Technical Stack" in text
    assert "Languages" in text
    assert "Formação" not in text
    assert "Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)" in text
    assert "B.Sc." not in text


def test_portuguese_cv_is_not_misclassified_as_english(tmp_path):
    text = render_cv(portuguese_payload(), tmp_path)
    assert "Formação" in text
    assert "Stack técnica" in text
    assert "Idiomas" in text
    assert "Education" not in text


@pytest.mark.parametrize("field,value", [("education", []), ("stack", "  "), ("languages", [])])
def test_renderer_rejects_blank_english_mandatory_sections(tmp_path, field, value):
    payload = english_payload()
    payload[field] = value
    with pytest.raises(subprocess.CalledProcessError):
        render_cv(payload, tmp_path)


def test_renderer_rejects_ascending_experience_order(tmp_path):
    payload = english_payload()
    payload["experiences"] = list(reversed(payload["experiences"]))
    with pytest.raises(subprocess.CalledProcessError):
        render_cv(payload, tmp_path)
