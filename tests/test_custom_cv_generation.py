import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from review_output import dash_punctuation_check, experience_format_check
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _experience(role: str, period: str) -> dict:
    return {"role": role, "company": "Example Co.", "period": period, "bullets": ["Scope", "Action", "Result"]}


def english_payload() -> dict:
    return {
        "metadata": {"language": "en", "application_id": "english-fixture"},
        "output_name": "fixture_en.docx",
        "candidate": {
            "name": "Fixture English Name",
            "location": "London, United Kingdom",
            "linkedin": "linkedin.com/in/fixture-english",
            "phone": "+44 20 0000 0000",
            "email": "fixture.english@example.test",
        },
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
        "metadata": {"language": "pt-BR", "application_id": "portuguese-fixture"},
        "output_name": "fixture.docx",
        "candidate": {
            "name": "Nome de Teste",
            "location": "Curitiba, PR",
            "linkedin": "linkedin.com/in/fixture-portugues",
            "phone": "+55 41 0000-0000",
            "email": "fixture.portugues@example.test",
        },
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


def render_document_xml(payload: dict, tmp_path: Path):
    content_path = tmp_path / "cv_content.json"
    content_path.write_text(json.dumps(payload), encoding="utf-8")
    env = {**os.environ, "CAREER_CV_CONTENT": str(content_path), "CAREER_OUTPUTS": str(tmp_path)}
    subprocess.run(["node", "scripts/docx/generate_custom_cv.js"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    with zipfile.ZipFile(tmp_path / payload["output_name"]) as docx:
        return ElementTree.fromstring(docx.read("word/document.xml"))


def test_english_cv_has_only_english_labels_and_canonical_degree(tmp_path):
    text = render_cv(english_payload(), tmp_path)
    assert "Education" in text
    assert "Technical Stack" in text
    assert "Languages" in text
    assert "Formação" not in text
    assert "Bachelor's Degree in Chemical Engineering: Faculdades Oswaldo Cruz (2014)" in text
    assert " — " not in text
    assert "B.Sc." not in text
    assert "May 2024 to Present" in text
    assert "Fixture English Name" in text
    assert "London, United Kingdom" in text
    assert "linkedin.com/in/fixture-english" in text
    assert "fixture.english@example.test" in text
    assert "Felipe Armel Dias da Silva" not in text
    assert experience_format_check(tmp_path / english_payload()["output_name"])[0:2] == (True, True)
    assert dash_punctuation_check(tmp_path / english_payload()["output_name"]) == (True, "dash_paragraphs=0")


def test_portuguese_cv_is_not_misclassified_as_english(tmp_path):
    text = render_cv(portuguese_payload(), tmp_path)
    assert "Formação" in text
    assert "Stack técnica" in text
    assert "Idiomas" in text
    assert "Education" not in text
    assert "Nome de Teste" in text
    assert "Curitiba, PR" in text


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


def test_renderer_requires_explicit_output_filename(tmp_path):
    payload = english_payload()
    payload.pop("output_name")
    content_path = tmp_path / "cv_content.json"
    content_path.write_text(json.dumps(payload), encoding="utf-8")
    env = {**os.environ, "CAREER_CV_CONTENT": str(content_path), "CAREER_OUTPUTS": str(tmp_path)}
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            ["node", "scripts/docx/generate_custom_cv.js"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )


def test_renderer_applies_arial_theme(tmp_path):
    payload = english_payload()
    render_cv(payload, tmp_path)
    with zipfile.ZipFile(tmp_path / payload["output_name"]) as docx:
        theme = docx.read("word/theme/theme1.xml").decode("utf-8")
    assert 'typeface="Arial"' in theme


def test_renderer_separates_period_and_bolds_key_result_metrics(tmp_path):
    payload = portuguese_payload()
    payload["experiencias"][0]["bullets"] = [
        "Escopo",
        "Ação",
        "Elevei a acurácia de estoque de 85% para 98% — o que aumentou a produtividade em 35% e reduziu perdas em 30%.",
    ]
    root = render_document_xml(payload, tmp_path)
    paragraphs = root.findall(".//w:body/w:p", NS)

    def paragraph_text(paragraph):
        return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))

    texts = [paragraph_text(paragraph) for paragraph in paragraphs]
    role_index = texts.index("Head de Operações | Empresa Exemplo")
    assert texts[role_index + 1] == "maio/2024 a Atual"
    assert "\t" not in texts[role_index]
    assert " — " not in "\n".join(texts)
    assert "Engenheiro Químico: Faculdades Oswaldo Cruz (2014)" in "\n".join(texts)
    assert ", o que aumentou" in "\n".join(texts)

    result_text = "Elevei a acurácia de estoque de 85% para 98%, o que aumentou a produtividade em 35% e reduziu perdas em 30%."
    result_index = texts.index(result_text)
    result_paragraph = paragraphs[result_index]
    bold_text = "".join(
        node.text or ""
        for run in result_paragraph.findall("w:r", NS)
        if run.find("w:rPr/w:b", NS) is not None
        for node in run.findall("w:t", NS)
    )
    assert "98%" in bold_text
    assert "35%" in bold_text
    assert "30%" in bold_text
    assert experience_format_check(tmp_path / payload["output_name"])[0:2] == (True, True)
    assert dash_punctuation_check(tmp_path / payload["output_name"]) == (True, "dash_paragraphs=0")


def test_renderer_preserves_explicit_rich_text_runs(tmp_path):
    payload = portuguese_payload()
    payload["experiencias"][0]["bullets"] = [
        {"runs": [{"text": "Resultado: ", "bold": False}, {"text": "98%", "bold": True}]},
        "Ação",
        "Resultado",
    ]
    root = render_document_xml(payload, tmp_path)
    runs = root.findall(".//w:body/w:p/w:r", NS)
    assert any(
        "98%" in "".join(node.text or "" for node in run.findall("w:t", NS))
        and run.find("w:rPr/w:b", NS) is not None
        for run in runs
    )
