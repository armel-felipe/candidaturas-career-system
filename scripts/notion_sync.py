#!/usr/bin/env python3
import argparse
import json
from collections import Counter
import os
import re
import time
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


NOTION_VERSION = "2022-06-28"
NOTION_TEMPLATE_VERSION = "2026-03-11"
DEFAULT_SWEEP_DIR = Path("inbox/notion/applications_sweep")
DEFAULT_SWEEP_SUMMARY = Path("inbox/notion/applications_sweep_summary.json")
DEFAULT_SWEEP_CACHE = Path("inbox/notion/applications_cache.json")
DEFAULT_GOVERNANCE_BACKFILL_REPORT = Path("outputs/_tmp/notion_governance_backfill_report.json")
MOJIBAKE_MARKERS = ("Ã", "Â", "â€“", "â€”", "â€™", "â€œ", "â€", "ï¿½")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


PROPERTY_ALIASES = {
    "record_id": ["ID", "Record ID", "Unique ID"],
    "title": ["Vaga", "Nome", "Name", "Cargo", "Title"],
    "company": ["empresa_int", "Empresa", "Company"],
    "company_type": ["tipo de empresa_int", "Tipo de Empresa", "Tipo de empresa", "Company Type"],
    "role": ["Cargo", "Vaga", "Role", "Position"],
    "fit": ["avaliação de aderencia claude", "Fit", "Nota", "Nota de aderência", "Aderência", "Fit Score"],
    "status": ["Etapa Funil", "Status", "Etapa"],
    "application_date": ["Data Aplicação", "Data Aplicacao", "Application Date"],
    "description": ["Descrição da Vaga", "Descricao da Vaga", "Job Description", "Descrição", "Description"],
    "keywords": ["Keywords", "Keywords ATS", "ATS Keywords"],
    "gaps": ["Gaps", "Keywords faltantes", "Gaps sem cobertura"],
    "source_url": ["Link", "URL", "Link da vaga", "Job URL"],
    "service_status": ["Status serviço", "Status Serviço", "Status Servico", "Service Status"],
    "final_state": ["Estado final", "Estado Final", "Final State"],
    "required_cv_language": ["Idioma CV requerido", "Idioma CV Requerido", "Required CV Language"],
    "final_cv_language": ["Idioma final do CV", "Idioma Final do CV", "Final CV Language"],
    "review_status": ["Status revisão CV", "Status Revisão CV", "CV Review Status"],
    "review_blockers": ["Blockers revisão CV", "Blockers Revisão CV", "CV Review Blockers"],
    "narrative_decisions": ["Decisões narrativas", "Decisoes narrativas", "Narrative Decisions"],
    "human_feedback": ["Feedback humano", "Human Feedback"],
    "top8_keywords": ["Top 8 keywords", "Top 8 Keywords"],
    "covered_keywords": ["Keywords cobertas no CV", "Keywords Cobertas no CV", "Covered CV Keywords"],
    "declared_gap_keywords": ["Keywords em gap declarado", "Declared Gap Keywords"],
    "persona_angle": ["Persona / Ângulo narrativo", "Persona / Angulo narrativo", "Persona / Narrative Angle"],
    "prioritized_experiences": ["Experiências priorizadas", "Experiencias priorizadas", "Prioritized Experiences"],
    "labels_verified": ["Labels verificadas", "Section Labels Verified"],
    "final_artifact": ["Arquivo final aprovado", "Final Approved Artifact", "cv especifico"],
}

GOVERNANCE_SCHEMA_FIELDS = [
    {
        "name": "Keywords ATS",
        "logical_name": "keywords",
        "schema": {"rich_text": {}},
        "description": "Keywords ATS consolidadas da vaga/FIT_MAP.",
    },
    {
        "name": "Gaps sem cobertura",
        "logical_name": "gaps",
        "schema": {"rich_text": {}},
        "description": "Gaps declarados ou sem cobertura defensável.",
    },
    {
        "name": "Idioma CV requerido",
        "logical_name": "required_cv_language",
        "schema": {
            "select": {
                "options": [
                    {"name": "pt-BR", "color": "blue"},
                    {"name": "en", "color": "green"},
                ]
            }
        },
        "description": "Idioma exigido pela vaga para o CV.",
    },
    {
        "name": "Idioma final do CV",
        "logical_name": "final_cv_language",
        "schema": {
            "select": {
                "options": [
                    {"name": "pt-BR", "color": "blue"},
                    {"name": "en", "color": "green"},
                ]
            }
        },
        "description": "Idioma efetivamente aprovado no CV final.",
    },
    {
        "name": "Status revisão CV",
        "logical_name": "review_status",
        "schema": {
            "select": {
                "options": [
                    {"name": "pending", "color": "yellow"},
                    {"name": "approved", "color": "green"},
                    {"name": "blocked", "color": "red"},
                    {"name": "not_started", "color": "gray"},
                ]
            }
        },
        "description": "Estado consolidado da revisão objetiva/polimento do CV.",
    },
    {
        "name": "Blockers revisão CV",
        "logical_name": "review_blockers",
        "schema": {"rich_text": {}},
        "description": "Lista resumida dos blockers atuais do reviewer.",
    },
    {
        "name": "Decisões narrativas",
        "logical_name": "narrative_decisions",
        "schema": {"rich_text": {}},
        "description": "Decisões de reposicionamento e narrativa usadas na candidatura.",
    },
    {
        "name": "Feedback humano",
        "logical_name": "human_feedback",
        "schema": {"rich_text": {}},
        "description": "Campo livre para feedback manual posterior.",
    },
    {
        "name": "Top 8 keywords",
        "logical_name": "top8_keywords",
        "schema": {"rich_text": {}},
        "description": "Top 8 keywords-habilidade ATS priorizadas.",
    },
    {
        "name": "Keywords cobertas no CV",
        "logical_name": "covered_keywords",
        "schema": {"rich_text": {}},
        "description": "Keywords top 8 cobertas no CV final.",
    },
    {
        "name": "Keywords em gap declarado",
        "logical_name": "declared_gap_keywords",
        "schema": {"rich_text": {}},
        "description": "Keywords mantidas como gap declarado.",
    },
    {
        "name": "Persona / Ângulo narrativo",
        "logical_name": "persona_angle",
        "schema": {"rich_text": {}},
        "description": "Persona e ângulo narrativo consolidado.",
    },
    {
        "name": "Experiências priorizadas",
        "logical_name": "prioritized_experiences",
        "schema": {"rich_text": {}},
        "description": "Experiências/histórias selecionadas para a vaga.",
    },
    {
        "name": "Labels verificadas",
        "logical_name": "labels_verified",
        "schema": {"checkbox": {}},
        "description": "Confirmação de labels/sections coerentes com o idioma final.",
    },
    {
        "name": "Arquivo final aprovado",
        "logical_name": "final_artifact",
        "schema": {"rich_text": {}},
        "description": "Artefato final aprovado no workspace local.",
    },
    {
        "name": "Status serviço",
        "logical_name": "service_status",
        "schema": {
            "select": {
                "options": [
                    {"name": "pending", "color": "yellow"},
                    {"name": "analyze_pending", "color": "yellow"},
                    {"name": "analyze_running", "color": "blue"},
                    {"name": "generate_pending", "color": "yellow"},
                    {"name": "generate_running", "color": "blue"},
                    {"name": "repair_pending", "color": "orange"},
                    {"name": "repair_running", "color": "orange"},
                    {"name": "blocked_review", "color": "red"},
                    {"name": "blocked_review_exhausted", "color": "red"},
                    {"name": "done", "color": "green"},
                    {"name": "low_fit", "color": "gray"},
                    {"name": "no_description", "color": "gray"},
                ]
            }
        },
        "description": "Status operacional do serviço local para a candidatura.",
    },
    {
        "name": "Estado final",
        "logical_name": "final_state",
        "schema": {
            "select": {
                "options": [
                    {"name": "analyze_pending", "color": "yellow"},
                    {"name": "analyze_retry_pending", "color": "orange"},
                    {"name": "generate_pending", "color": "yellow"},
                    {"name": "repair_pending", "color": "orange"},
                    {"name": "blocked_review", "color": "red"},
                    {"name": "blocked_review_exhausted", "color": "red"},
                    {"name": "low_fit", "color": "gray"},
                    {"name": "done", "color": "green"},
                    {"name": "no_description", "color": "gray"},
                ]
            }
        },
        "description": "Estado técnico/final da candidatura no pipeline local.",
    },
]


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request(method: str, url: str, token: str, payload=None, notion_version: str = NOTION_VERSION) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    attempts = 3
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": notion_version,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"Notion API error {exc.code}: {detail}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt >= attempts:
                raise SystemExit(
                    f"Notion request failed after {attempts} attempts: {type(exc).__name__}: {exc}"
                ) from exc
            time.sleep(min(2 * attempt, 5))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mojibake_hits(text: str) -> list[str]:
    return [marker for marker in MOJIBAKE_MARKERS if marker in (text or "")]


def assert_clean_display_text(label: str, text: str) -> None:
    hits = mojibake_hits(text)
    if hits:
        raise SystemExit(
            f"Refusing to write {label} to Notion because the text appears to contain mojibake markers: {', '.join(hits)}. "
            "Keep the source as UTF-8 text, fix the upstream artifact, then retry."
        )


def validate_notion_payload_text(payload: Any, trail: str = "$") -> None:
    if isinstance(payload, str):
        assert_clean_display_text(trail, payload)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            validate_notion_payload_text(item, f"{trail}[{index}]")
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            validate_notion_payload_text(value, f"{trail}.{key}")


def notion_config() -> tuple[str, str]:
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_APPLICATIONS_DATABASE_ID")
    if not token:
        raise SystemExit("Set NOTION_TOKEN in the environment or in .env before using Notion sync.")
    if not database_id:
        raise SystemExit("Set NOTION_APPLICATIONS_DATABASE_ID in the environment or in .env before using Notion sync.")
    return token, database_id


def notion_url(path: str) -> str:
    return f"https://api.notion.com/v1/{path.lstrip('/')}"


def retrieve_database(token: str, database_id: str) -> dict:
    return request("GET", notion_url(f"databases/{database_id}"), token)


def retrieve_database_modern(token: str, database_id: str) -> dict:
    return request("GET", notion_url(f"databases/{database_id}"), token, notion_version=NOTION_TEMPLATE_VERSION)


def discover_data_source_id(token: str, database_id: str) -> str:
    configured = os.environ.get("NOTION_APPLICATIONS_DATA_SOURCE_ID", "").strip()
    if configured:
        return configured

    database = retrieve_database_modern(token, database_id)
    data_sources = database.get("data_sources", [])
    if not data_sources:
        raise SystemExit(
            "Could not discover a data source under the Notion database. "
            "Set NOTION_APPLICATIONS_DATA_SOURCE_ID in .env."
        )
    return data_sources[0]["id"]


def retrieve_data_source(token: str, data_source_id: str) -> dict:
    return request("GET", notion_url(f"data_sources/{data_source_id}"), token, notion_version=NOTION_TEMPLATE_VERSION)


def query_data_source(token: str, data_source_id: str, payload=None) -> dict:
    return request("POST", notion_url(f"data_sources/{data_source_id}/query"), token, payload or {}, notion_version=NOTION_TEMPLATE_VERSION)


def list_templates(token: str, data_source_id: str, name = None) -> dict:
    suffix = f"?name={urllib.parse.quote(name)}" if name else ""
    return request("GET", notion_url(f"data_sources/{data_source_id}/templates{suffix}"), token, notion_version=NOTION_TEMPLATE_VERSION)


def query_database(token: str, database_id: str, payload = None) -> dict:
    return request("POST", notion_url(f"databases/{database_id}/query"), token, payload or {})


def query_all_database_pages(token: str, database_id: str) -> list[dict]:
    pages: list[dict] = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        result = query_database(token, database_id, payload)
        pages.extend(result.get("results", []))
        if not result.get("has_more"):
            return pages
        cursor = result.get("next_cursor")


def retrieve_page(token: str, page_id: str) -> dict:
    return request("GET", notion_url(f"pages/{page_id}"), token)


def update_page(token: str, page_id: str, payload: dict) -> dict:
    return request("PATCH", notion_url(f"pages/{page_id}"), token, payload, notion_version=NOTION_TEMPLATE_VERSION)


def update_data_source(token: str, data_source_id: str, payload: dict) -> dict:
    return request("PATCH", notion_url(f"data_sources/{data_source_id}"), token, payload, notion_version=NOTION_TEMPLATE_VERSION)


def retrieve_blocks(token: str, block_id: str) -> list[dict]:
    blocks: list[dict] = []
    cursor = None
    while True:
        suffix = f"?start_cursor={cursor}" if cursor else ""
        result = request("GET", notion_url(f"blocks/{block_id}/children{suffix}"), token)
        blocks.extend(result.get("results", []))
        if not result.get("has_more"):
            return blocks
        cursor = result.get("next_cursor")


def append_blocks(token: str, block_id: str, children: list[dict], *, after_block_id = None) -> dict:
    position = (
        {"type": "after_block", "after_block": {"id": after_block_id}}
        if after_block_id
        else {"type": "end"}
    )
    return request(
        "PATCH",
        notion_url(f"blocks/{block_id}/children"),
        token,
        {"children": children[:100], "position": position},
        notion_version=NOTION_TEMPLATE_VERSION,
    )


def find_anchor_block_id(blocks, anchor_text: str):
    expected = normalize_text(anchor_text)
    for block in blocks:
        if normalize_text(block_text(block)) == expected:
            return block.get("id")
    return None


def plain_rich_text(items: list[dict]) -> str:
    return "".join(
        item.get("plain_text") or ((item.get("text") or {}).get("content", ""))
        for item in items or []
    )


def retrieve_relation_page_title(token: str, page_id: str, relation_cache: dict[str, str] | None = None) -> str:
    cache = relation_cache if relation_cache is not None else {}
    if page_id in cache:
        return cache[page_id]

    page = retrieve_page(token, page_id)
    title = ""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title = plain_rich_text(prop.get("title", []))
            if title:
                break
    cache[page_id] = title
    return title


def rollup_text(rollup: dict, *, token: str | None = None, relation_cache: dict[str, str] | None = None) -> str:
    kind = rollup.get("type")
    if kind == "array":
        values: list[str] = []
        for item in rollup.get("array", []):
            value = prop_text(item, token=token, relation_cache=relation_cache)
            if value and value not in values:
                values.append(value)
        return ", ".join(values)
    if kind == "number":
        value = rollup.get("number")
        return "" if value is None else str(value)
    if kind == "date":
        date = rollup.get("date") or {}
        return date.get("start", "")
    if kind == "incomplete":
        return ""
    if kind == "unsupported":
        return ""
    return ""


def prop_text(prop: dict, *, token: str | None = None, relation_cache: dict[str, str] | None = None) -> str:
    text = prop.get("text")
    if isinstance(text, str) and text:
        return text
    kind = prop.get("type")
    if kind == "title":
        return plain_rich_text(prop.get("title", []))
    if kind == "rich_text":
        return plain_rich_text(prop.get("rich_text", []))
    if kind == "select":
        return (prop.get("select") or {}).get("name", "")
    if kind == "status":
        return (prop.get("status") or {}).get("name", "")
    if kind == "multi_select":
        return ", ".join(item.get("name", "") for item in prop.get("multi_select", []))
    if kind == "number":
        value = prop.get("number")
        return "" if value is None else str(value)
    if kind == "url":
        return prop.get("url") or ""
    if kind == "date":
        date = prop.get("date") or {}
        return date.get("start", "")
    if kind == "checkbox":
        return str(prop.get("checkbox", False))
    if kind == "formula":
        formula = prop.get("formula") or {}
        formula_kind = formula.get("type")
        if formula_kind == "string":
            return formula.get("string") or ""
        if formula_kind == "number":
            value = formula.get("number")
            return "" if value is None else str(value)
        if formula_kind == "boolean":
            value = formula.get("boolean")
            return "" if value is None else str(value)
        if formula_kind == "date":
            date = formula.get("date") or {}
            return date.get("start", "")
        return ""
    if kind == "unique_id":
        unique_id = prop.get("unique_id") or {}
        number = unique_id.get("number")
        prefix = unique_id.get("prefix")
        if number is None:
            return ""
        return f"{prefix}-{number}" if prefix else str(number)
    if kind == "relation":
        relation_entries = prop.get("relation", [])
        if not relation_entries:
            return ""
        if not token:
            return ", ".join(item.get("id", "") for item in relation_entries if item.get("id"))
        values: list[str] = []
        for item in relation_entries:
            page_id = item.get("id")
            if not page_id:
                continue
            value = retrieve_relation_page_title(token, page_id, relation_cache=relation_cache)
            if value and value not in values:
                values.append(value)
        return ", ".join(values)
    if kind == "rollup":
        return rollup_text(prop.get("rollup") or {}, token=token, relation_cache=relation_cache)
    return ""


def block_text(block: dict) -> str:
    kind = block.get("type")
    data = block.get(kind, {})
    if isinstance(data, dict):
        text = plain_rich_text(data.get("rich_text", []))
        if text:
            return text
    return ""


def find_prop(schema: dict, logical_name: str, required_type = None):
    props = schema.get("properties", {})
    aliases = PROPERTY_ALIASES.get(logical_name, [])
    for alias in aliases:
        prop = props.get(alias)
        if prop and (required_type is None or prop.get("type") == required_type):
            return alias, prop
    if required_type:
        for name, prop in props.items():
            if prop.get("type") == required_type:
                return name, prop
    return None, None


def first_non_empty_property(page: dict, names: list[str]) -> str:
    props = page.get("properties", {})
    for name in names:
        if name in props:
            value = prop_text(props[name])
            if value:
                return value
    return ""


def extract_page_payload(token: str, page_id: str) -> dict:
    page = retrieve_page(token, page_id)
    blocks = retrieve_blocks(token, page_id)
    block_lines = [text for text in (block_text(block) for block in blocks) if text]
    relation_cache: dict[str, str] = {}
    properties = {
        name: {
            "type": prop.get("type"),
            "text": prop_text(prop, token=token, relation_cache=relation_cache),
        }
        for name, prop in page.get("properties", {}).items()
    }
    description = first_non_empty_property(page, PROPERTY_ALIASES["description"]) or "\n".join(block_lines)
    return {
        "page_id": page_id,
        "url": page.get("url"),
        "properties": properties,
        "description": description,
        "body_text": "\n".join(block_lines),
    }


def resolve_page_by_record_id(token: str, database_id: str, record_id: int) -> dict:
    data_source_id = discover_data_source_id(token, database_id)
    result = query_data_source(
        token,
        data_source_id,
        {
            "filter": {"property": "ID", "unique_id": {"equals": int(record_id)}},
            "page_size": 2,
        },
    )
    pages = result.get("results", [])
    if not pages:
        raise SystemExit(f"No Notion application record found for unique ID {record_id}.")
    if len(pages) > 1:
        raise SystemExit(f"Multiple Notion application records found for unique ID {record_id}; aborting.")
    return pages[0]


def sanitize_filename(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").strip())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug[:80] or "notion_page"


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).lower()


def detect_document_language(text: str) -> str:
    normalized = f" {normalize_text(text)} "
    english_markers = [
        " the ",
        " and ",
        " with ",
        " about ",
        " responsibilities ",
        " requirements ",
        " experience ",
        " you ",
    ]
    portuguese_markers = [
        " de ",
        " e ",
        " com ",
        " sobre ",
        " responsabilidades ",
        " requisitos ",
        " experiencia ",
        " você ",
        " voce ",
    ]
    english_score = sum(normalized.count(marker) for marker in english_markers)
    portuguese_score = sum(normalized.count(marker) for marker in portuguese_markers)
    if english_score > portuguese_score:
        return "en"
    return "pt-BR"


def slugify(text: str) -> str:
    return sanitize_filename(text or "")


def expected_job_description_slug(company: str, role: str) -> str:
    company_slug = slugify(company)
    role_slug = slugify(role)
    return f"{company_slug}_{role_slug}".strip("_")


def is_job_description_boilerplate_heading(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    boilerplate_prefixes = (
        "logo da empresa",
        "logo of the company",
        "sobre a vaga",
        "about the job",
        "about the role",
        "promovida por quem esta contratando",
        "promoted by",
        "pessoas que voce pode contatar",
        "people you may contact",
        "conheca a equipe de contratacao",
        "meet the hiring team",
        "salva",
        "saved",
        "candidatar se",
        "apply",
    )
    return normalized.startswith(boilerplate_prefixes)


def job_description_heading(text: str) -> str:
    fallback = ""
    metadata_prefixes = ("empresa:", "fonte:", "extraído em:", "extraido em:")
    candidates = [line.strip().lstrip("#").strip() for line in text.splitlines()]
    candidates = [line for line in candidates if line]
    for index, cleaned in enumerate(candidates):
        if not cleaned:
            continue
        if cleaned.casefold().startswith(metadata_prefixes):
            continue
        if not fallback:
            fallback = cleaned
        if not is_job_description_boilerplate_heading(cleaned):
            if index + 1 < len(candidates):
                next_line = candidates[index + 1]
                if normalize_text(cleaned) == normalize_text(next_line):
                    continue
                if re.fullmatch(r"[\w\s&.,/-]+", cleaned) and len(cleaned.split()) <= 4 and len(next_line.split()) >= 2:
                    if not is_job_description_boilerplate_heading(next_line):
                        return next_line
            return cleaned
    return fallback


    if job_description_path and job_description_path.name.startswith("notion_record_"):
        raise SystemExit("Refusing to create a new Notion record for a vacancy that originated from Notion. Use update-from-fit-map or update-from-fit-map-record instead.")

def ensure_fit_map_matches_job_description(
    fit_map: dict,
    job_description: str,
    job_description_path,
    allow_mismatch: bool,
) -> None:
    company = str(fit_map.get("empresa", "")).strip()
    role = str(fit_map.get("cargo", "")).strip()
    if not company or not role:
        raise SystemExit("FIT_MAP must contain empresa and cargo before creating a Notion application record.")

    if allow_mismatch:
        return

    expected_slug = expected_job_description_slug(company, role)
    blocking_mismatches: list[str] = []
    warnings: list[str] = []

    if job_description_path:
        actual_slug = slugify(job_description_path.stem)
        role_slug = slugify(role)
        company_slug = slugify(company)
        is_application_scoped_description = (
            job_description_path.name == "job_description.md"
            and "applications" in {part.casefold() for part in job_description_path.parts}
        )
        if actual_slug.startswith("notion_record_") or is_application_scoped_description:
            pass
        elif role_slug and role_slug not in actual_slug:
            blocking_mismatches.append(
                f"job description filename '{job_description_path.name}' does not match FIT_MAP cargo slug '{role_slug}'"
            )
        elif company_slug and company_slug not in actual_slug:
            warnings.append(
                f"job description filename '{job_description_path.name}' does not include empresa slug '{company_slug}'"
            )
    else:
        actual_slug = ""
        role_slug = slugify(role)

    heading = job_description_heading(job_description)
    heading_normalized = normalize_text(heading)
    role_normalized = normalize_text(role)
    company_normalized = normalize_text(company)

    if heading:
        if role_normalized and role_normalized not in heading_normalized:
            if role_slug and role_slug in actual_slug:
                warnings.append(
                    f"job description heading does not match FIT_MAP cargo '{role}' in heading '{heading}', but filename matches cargo slug"
                )
            else:
                blocking_mismatches.append(
                    f"job description heading does not match FIT_MAP cargo '{role}' in heading '{heading}'"
                )
        elif company_normalized and company_normalized not in heading_normalized:
            warnings.append(
                f"job description heading does not include empresa '{company}' in heading '{heading}'"
            )

    if blocking_mismatches:
        details = "\n- ".join(blocking_mismatches)
        warning_text = ""
        if warnings:
            warning_text = "\nWarnings:\n- " + "\n- ".join(warnings)
        raise SystemExit(
            "FIT_MAP / job description mismatch detected. Refusing to create Notion record.\n"
            f"- {details}\n"
            "Expected recovery flow:\n"
            "1. Run career-fit-analysis for the target vacancy.\n"
            "2. Canonize with scripts/build_fit_map.py.\n"
            "3. Score with scripts/score_fit_map.py.\n"
            "4. Validate with scripts/validate_fit_map.py.\n"
            "5. Retry create-from-fit-map.\n"
            "Do not bypass this with --allow-mismatch in the agent workflow; fix the saved description, active FIT_MAP or Notion source first."
            f"{warning_text}"
        )


def save_page_payload(payload: dict, output_dir: Path) -> Path:
    title = ""
    for name in PROPERTY_ALIASES["title"]:
        prop = payload["properties"].get(name)
        if prop and prop.get("text"):
            title = prop["text"]
            break
    filename = f"notion_job_{sanitize_filename(title or payload['page_id'])}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def markdown_job_description_path(company: str, role: str, output_dir: Path, record_id = None) -> Path:
    if record_id is not None:
        return output_dir / f"notion_record_{record_id}.md"
    company_slug = sanitize_filename(company or "empresa")
    role_slug = sanitize_filename(role or "cargo")
    return output_dir / f"{company_slug}_{role_slug}.md"


def prepare_analysis_from_page(
    token: str,
    page_id: str,
    payload_output_dir: Path,
    description_output_dir: Path,
    record_id = None,
) -> dict:
    payload = extract_page_payload(token, page_id)
    description = (payload.get("description") or "").strip()
    if not description:
        raise SystemExit("The selected Notion page does not contain a usable job description.")

    payload_path = save_page_payload(payload, payload_output_dir)
    title = ""
    for alias in PROPERTY_ALIASES["title"]:
        prop = payload.get("properties", {}).get(alias)
        if prop and prop.get("text"):
            title = prop["text"].strip()
            break
    company, role = infer_company_and_role(title)
    if not role:
        role = title or "vaga_notion"

    description_output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = markdown_job_description_path(company, role, description_output_dir, record_id=record_id)
    markdown_path.write_text(description.strip() + "\n", encoding="utf-8")

    return {
        "page_id": page_id,
        "title": title,
        "company": company,
        "role": role,
        "record_id": record_id,
        "payload_path": str(payload_path),
        "job_description_path": str(markdown_path),
        "description_chars": len(description),
    }


def prepare_analysis_from_record(
    token: str,
    database_id: str,
    record_id: int,
    payload_output_dir: Path,
    description_output_dir: Path,
) -> dict:
    page = resolve_page_by_record_id(token, database_id, record_id)
    result = prepare_analysis_from_page(
        token,
        page["id"],
        payload_output_dir,
        description_output_dir,
        record_id=record_id,
    )
    result["resolved_from_record_id"] = record_id
    return result


def page_title(page: dict) -> str:
    props = page.get("properties", {})
    for name in PROPERTY_ALIASES["title"]:
        if name in props:
            value = prop_text(props[name])
            if value:
                return value
    for prop in props.values():
        if prop.get("type") == "title":
            value = prop_text(prop)
            if value:
                return value
    return ""


def sweep_filename(title: str, page_id: str) -> str:
    return f"{sanitize_filename(title)}_{page_id}.json"


def save_sweep_payload(payload: dict, output_dir: Path, title: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / sweep_filename(title, payload["page_id"])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_sweep_records(sweep_dir: Path) -> tuple[dict[str, dict], list[str]]:
    records: dict[str, dict] = {}
    invalid_files: list[str] = []
    if not sweep_dir.exists():
        return records, invalid_files

    for path in sorted(sweep_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            invalid_files.append(str(path))
            continue
        page_id = str(payload.get("page_id", "")).strip()
        if not page_id:
            invalid_files.append(str(path))
            continue
        records[page_id] = {"path": path, "payload": payload}
    return records, invalid_files


def extract_saved_property(payload: dict, logical_name: str) -> str:
    properties = payload.get("properties", {})
    for alias in PROPERTY_ALIASES.get(logical_name, []):
        value = properties.get(alias, {}).get("text", "")
        if value:
            return value
    return ""


def split_terms(value: str) -> list[str]:
    if not value:
        return []
    return [term.strip() for term in re.split(r"[,\n;|]+", value) if term.strip()]


def split_numbered_lines(value: str) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for raw_line in str(value).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        if line:
            items.append(line)
    return items


def normalize_search_text(*parts: str) -> str:
    normalized_parts = [normalize_text(part) for part in parts if part]
    return " ".join(part for part in normalized_parts if part).strip()


ROLE_HINT_TOKENS = {
    "analista", "assistente", "consultant", "consultor", "coo", "coordenador", "coordinator",
    "customer", "cx", "delivery", "diretor", "director", "especialista", "expert", "gerencia",
    "gerente", "gestor", "head", "inteligencia", "leader", "lider", "logistica", "manager",
    "operations", "operacao", "operações", "planejamento", "pricing", "processos", "product",
    "program", "projetos", "revenue", "sales", "senior", "specialist", "strategy", "supply",
}


def infer_company_and_role(title: str) -> tuple[str, str]:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        return "", ""

    for separator in (" - ", " | ", " — ", ": "):
        if separator not in cleaned:
            continue
        left, right = cleaned.split(separator, 1)
        left_tokens = set(re.findall(r"[A-Za-zÀ-ÿ]+", normalize_text(left)))
        right_tokens = set(re.findall(r"[A-Za-zÀ-ÿ]+", normalize_text(right)))
        if not right_tokens & ROLE_HINT_TOKENS:
            continue
        if left_tokens & ROLE_HINT_TOKENS:
            continue
        return left.strip(), right.strip()

    return "", cleaned


def build_application_record(payload: dict, source_path: Path) -> dict:
    title = extract_saved_property(payload, "title").replace("\u00a0", " ").strip()
    record_id_raw = extract_saved_property(payload, "record_id").strip()
    record_id = None
    if record_id_raw:
        match = re.search(r"(\d+)$", record_id_raw)
        if match:
            record_id = int(match.group(1))
    description = payload.get("description", "") or ""
    body_text = payload.get("body_text", "") or ""
    company = extract_saved_property(payload, "company")
    company_type = extract_saved_property(payload, "company_type")
    role = extract_saved_property(payload, "role").strip()
    inferred_company, inferred_role = infer_company_and_role(title)
    if not company:
        company = inferred_company
    if role == title and inferred_role:
        role = inferred_role
    if not role:
        role = inferred_role or title
    keywords = split_terms(extract_saved_property(payload, "keywords"))
    gaps = split_terms(extract_saved_property(payload, "gaps"))
    top8_keywords = split_numbered_lines(extract_saved_property(payload, "top8_keywords"))
    covered_keywords = split_terms(extract_saved_property(payload, "covered_keywords"))
    declared_gap_keywords = split_terms(extract_saved_property(payload, "declared_gap_keywords"))
    status = extract_saved_property(payload, "status")
    application_date = extract_saved_property(payload, "application_date")
    fit_raw = extract_saved_property(payload, "fit")
    source_url = extract_saved_property(payload, "source_url")
    required_cv_language = extract_saved_property(payload, "required_cv_language")
    final_cv_language = extract_saved_property(payload, "final_cv_language")
    review_status = extract_saved_property(payload, "review_status")
    review_blockers = extract_saved_property(payload, "review_blockers")
    narrative_decisions = extract_saved_property(payload, "narrative_decisions")
    human_feedback = extract_saved_property(payload, "human_feedback")
    persona_angle = extract_saved_property(payload, "persona_angle")
    prioritized_experiences = extract_saved_property(payload, "prioritized_experiences")
    labels_verified_raw = extract_saved_property(payload, "labels_verified")
    final_artifact = extract_saved_property(payload, "final_artifact")
    service_status = extract_saved_property(payload, "service_status")
    final_state = extract_saved_property(payload, "final_state")
    fit_score = None
    if fit_raw:
        try:
            fit_score = float(fit_raw)
        except ValueError:
            fit_score = None
    if not required_cv_language and (description or body_text):
        required_cv_language = detect_document_language(description or body_text)
    if not final_cv_language and final_artifact:
        final_cv_language = "en" if "_en." in final_artifact.casefold() else "pt-BR"
    if not review_status and not final_artifact:
        review_status = "not_started"

    search_text = normalize_search_text(
        title,
        company,
        company_type,
        role,
        status,
        source_url,
        description,
        body_text,
        " ".join(keywords),
        " ".join(gaps),
        " ".join(top8_keywords),
        " ".join(covered_keywords),
        " ".join(declared_gap_keywords),
        required_cv_language,
        final_cv_language,
        review_status,
        service_status,
        final_state,
        narrative_decisions,
        persona_angle,
        prioritized_experiences,
    )

    return {
        "page_id": payload.get("page_id"),
        "record_id": record_id,
        "title": title,
        "company": company,
        "company_type": company_type,
        "role": role,
        "status": status,
        "is_archived": bool(payload.get("archived") or payload.get("is_archived") or payload.get("in_trash")),
        "application_date": application_date,
        "fit_score": fit_score,
        "notion_url": payload.get("url"),
        "source_url": source_url,
        "keywords": keywords,
        "gaps": gaps,
        "top8_keywords": top8_keywords,
        "covered_keywords": covered_keywords,
        "declared_gap_keywords": declared_gap_keywords,
        "required_cv_language": required_cv_language,
        "final_cv_language": final_cv_language,
        "review_status": review_status,
        "review_blockers": split_terms(review_blockers),
        "narrative_decisions": narrative_decisions,
        "human_feedback": human_feedback,
        "persona_angle": persona_angle,
        "prioritized_experiences": split_numbered_lines(prioritized_experiences) or split_terms(prioritized_experiences),
        "labels_verified": str(labels_verified_raw).strip().casefold() in {"1", "true", "yes", "sim", "checked"},
        "final_artifact": final_artifact,
        "service_status": service_status or None,
        "final_state": final_state or None,
        "description": description,
        "body_text": body_text,
        "description_chars": len(description),
        "body_chars": len(body_text),
        "source_file": str(source_path),
        "search_text": search_text,
    }


def build_sweep_outputs(
    sweep_dir: Path,
    summary_path: Path,
    cache_path: Path,
    remote_pages = None,
    database_id = None,
) -> dict:
    local_records, invalid_files = load_sweep_records(sweep_dir)
    previous_summary = None
    if summary_path.exists():
        try:
            previous_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_summary = None
    applications = [
        build_application_record(record["payload"], record["path"])
        for record in sorted(local_records.values(), key=lambda item: str(item["path"]).lower())
    ]
    applications.sort(key=lambda item: (item["title"] or "", item["page_id"] or ""))

    remote_index = {page.get("id"): page for page in (remote_pages or []) if page.get("id")}
    remote_ids = set(remote_index)
    local_ids = set(local_records)
    previous_coverage = (previous_summary or {}).get("coverage", {})
    if remote_pages is not None:
        missing_ids = sorted(remote_ids - local_ids)
        orphan_ids = sorted(local_ids - remote_ids)
        remote_total_pages = len(remote_pages)
    else:
        missing_ids = previous_coverage.get("missing_page_ids", [])
        orphan_ids = previous_coverage.get("orphan_page_ids", [])
        remote_total_pages = previous_coverage.get("remote_total_pages")

    title_terms = Counter()
    for item in applications:
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", item["title"] or ""):
            title_terms[normalize_text(token)] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_database_id": database_id,
        "sweep_dir": str(sweep_dir),
        "total_pages": len(applications),
        "applications_with_description": sum(1 for item in applications if item["description_chars"] > 0),
        "coverage": {
            "remote_total_pages": remote_total_pages,
            "local_total_files": len(local_records),
            "missing_page_ids": missing_ids,
            "orphan_page_ids": orphan_ids,
            "invalid_files": invalid_files,
            "is_complete": not missing_ids and not invalid_files,
        },
        "top_title_terms": title_terms.most_common(40),
        "pages": [
            {
                "title": item["title"],
                "page_id": item["page_id"],
                "chars": item["description_chars"],
                "source_file": item["source_file"],
            }
            for item in applications
        ],
    }

    cache = {
        "version": 1,
        "generated_at": summary["generated_at"],
        "source": {
            "database_id": database_id,
            "sweep_dir": str(sweep_dir),
            "summary_file": str(summary_path),
        },
        "coverage": summary["coverage"],
        "applications": applications,
    }

    write_json(summary_path, summary)
    write_json(cache_path, cache)
    return {
        "summary": summary,
        "cache": cache,
    }


def sync_applications_sweep(
    token: str,
    database_id: str,
    output_dir: Path,
    refresh: str,
) -> dict:
    remote_pages = query_all_database_pages(token, database_id)
    local_records, invalid_files = load_sweep_records(output_dir)
    remote_by_id = {page.get("id"): page for page in remote_pages if page.get("id")}
    local_ids = set(local_records)
    remote_ids = set(remote_by_id)

    if refresh == "full":
        target_ids = sorted(remote_ids)
    else:
        target_ids = sorted(remote_ids - local_ids)

    saved_paths = []
    for page_id in target_ids:
        page = remote_by_id[page_id]
        payload = extract_page_payload(token, page_id)
        saved_paths.append(str(save_sweep_payload(payload, output_dir, page_title(page) or page_id)))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_id": database_id,
        "sweep_dir": str(output_dir),
        "refresh_mode": refresh,
        "remote_total_pages": len(remote_ids),
        "local_files_before": len(local_ids),
        "synced_pages": len(target_ids),
        "missing_before_sync": sorted(remote_ids - local_ids),
        "orphan_local_files": sorted(local_ids - remote_ids),
        "invalid_local_files": invalid_files,
        "saved_files": saved_paths,
        "remote_pages": remote_pages,
    }


def rich_text_chunks(text: str, chunk_size: int = 1800) -> list[dict]:
    assert_clean_display_text("rich text payload", text)
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)] or [""]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks[:50]]


def paragraph_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text_chunks(text)},
    }


def heading_block(text: str, level: int = 2) -> dict:
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": rich_text_chunks(text)[:1]},
    }


def bullet_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text_chunks(text)[:1]},
    }


def property_value(prop, value: Any):
    kind = prop.get("type")
    if value is None or value == "":
        return None
    if kind == "title":
        return {"title": rich_text_chunks(str(value))[:1]}
    if kind == "rich_text":
        if isinstance(value, list):
            value = "; ".join(str(item).strip() for item in value if str(item).strip())
            if not value:
                return None
        return {"rich_text": rich_text_chunks(str(value))}
    if kind == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return None
    if kind == "select":
        return {"select": {"name": str(value)}}
    if kind == "status":
        return {"status": {"name": str(value)}}
    if kind == "url":
        return {"url": str(value)}
    if kind == "date":
        return {"date": {"start": str(value)}}
    if kind == "multi_select":
        values = value if isinstance(value, list) else [str(value)]
        return {"multi_select": [{"name": str(item)} for item in values if str(item).strip()][:100]}
    if kind == "checkbox":
        if isinstance(value, bool):
            return {"checkbox": value}
        lowered = str(value).strip().casefold()
        return {"checkbox": lowered in {"1", "true", "yes", "sim", "checked"}}
    return None


def top8_keyword_entries(fit_map: dict) -> list[dict]:
    entries = [item for item in fit_map.get("keywords_habilidade_ats", []) if isinstance(item, dict)]
    return sorted(entries, key=lambda item: item.get("prioridade", 999))[:8]


def _string_list(items: list[Any]) -> list[str]:
    result = []
    for item in items or []:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _story_entries(fit_map: dict) -> list[dict]:
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    ordered = []
    for key in ["principal", "secundaria", "terceira"]:
        story = stories.get(key)
        if isinstance(story, dict):
            ordered.append(story)
    return ordered


def narrative_decisions_text(fit_map: dict) -> str:
    lines: list[str] = []
    stories = _story_entries(fit_map)
    if stories:
        first_angle = str(stories[0].get("angulo") or "").strip()
        if first_angle:
            lines.append(f"Angulo principal: {first_angle}")
    adjustments = fit_map.get("mapa_ajuste", []) if isinstance(fit_map.get("mapa_ajuste"), list) else []
    repositioned = []
    for item in adjustments:
        if not isinstance(item, dict):
            continue
        if item.get("tipo_ajuste") != "REPOSICIONAMENTO":
            continue
        term = str(item.get("termo_vaga") or "").strip()
        angle = str(item.get("angulo_sugerido") or "").strip()
        if term and angle:
            repositioned.append(f"{term}: {angle}")
    if repositioned:
        lines.append("Reposicionamentos: " + " | ".join(repositioned[:3]))
    return "\n".join(lines).strip()


def prioritized_experiences_text(fit_map: dict) -> str:
    parts = []
    for story in _story_entries(fit_map):
        company = str(story.get("empresa") or "").strip()
        result = str(story.get("resultado") or "").strip()
        angle = str(story.get("angulo") or "").strip()
        text = company
        if result:
            text += f": {result}"
        if angle:
            text += f" | angulo: {angle}"
        if text.strip():
            parts.append(text)
    return "\n".join(parts).strip()


def governance_field_values(fit_map: dict) -> dict[str, Any]:
    top8 = top8_keyword_entries(fit_map)
    covered_keywords = _string_list(fit_map.get("service_covered_top8_keywords", []))
    declared_gap_keywords = _string_list(fit_map.get("service_declared_gap_keywords", []))
    review_blockers = _string_list(fit_map.get("service_review_blockers", []))
    service_polish_blockers = _string_list(fit_map.get("service_polish_blockers", []))
    if service_polish_blockers:
        review_blockers.extend(item for item in service_polish_blockers if item not in review_blockers)
    persona = str(fit_map.get("persona") or fit_map.get("cv_persona") or "").strip()
    stories = _story_entries(fit_map)
    primary_angle = str(stories[0].get("angulo") or "").strip() if stories else ""
    persona_angle = " | ".join(part for part in [persona, primary_angle] if part)
    return {
        "keywords": "; ".join(_string_list(fit_map.get("keywords_para_ats", []))),
        "gaps": "; ".join(_string_list(fit_map.get("gaps_sem_cobertura", []))),
        "required_cv_language": str(fit_map.get("service_required_cv_language") or "").strip(),
        "final_cv_language": str(fit_map.get("service_final_cv_language") or "").strip(),
        "review_status": str(fit_map.get("service_review_status") or "").strip(),
        "review_blockers": "\n".join(review_blockers),
        "narrative_decisions": narrative_decisions_text(fit_map),
        "human_feedback": str(fit_map.get("human_feedback") or "").strip(),
        "top8_keywords": "\n".join(
            f"{item.get('prioridade')}. {item.get('keyword')}"
            for item in top8
            if str(item.get("keyword") or "").strip()
        ),
        "covered_keywords": "; ".join(covered_keywords),
        "declared_gap_keywords": "; ".join(declared_gap_keywords),
        "persona_angle": persona_angle,
        "prioritized_experiences": prioritized_experiences_text(fit_map),
        "final_artifact": str(fit_map.get("service_final_artifact") or "").strip(),
        "labels_verified": fit_map.get("service_labels_verified"),
        "service_status": str(fit_map.get("service_status") or "").strip(),
        "final_state": str(fit_map.get("service_stage") or "").strip(),
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    return bool(str(value).strip())


def _prefer_value(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if key not in current and _has_value(value):
            current[key] = value
    return current


def _split_nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _extract_section_lines(text: str, heading: str, stop_headings: list[str]) -> list[str]:
    lines = _split_nonempty_lines(text)
    target = normalize_text(heading)
    normalized_stop = {normalize_text(item) for item in stop_headings}
    start_index = None
    for index, line in enumerate(lines):
        if normalize_text(line) == target:
            start_index = index + 1
            break
    if start_index is None:
        return []
    section: list[str] = []
    for line in lines[start_index:]:
        normalized_line = normalize_text(line)
        if normalized_line in normalized_stop:
            break
        section.append(line)
    return section


def _extract_body_derived_values(body_text: str, description: str, cache_keywords: list[str], cache_gaps: list[str]) -> dict[str, Any]:
    text = body_text or ""
    values: dict[str, Any] = {}

    keywords_lines = _extract_section_lines(
        text,
        "Keywords-habilidade para ATS",
        ["Status do serviço", "Pesquisa Inicial", "Análise de aderência"],
    )
    top8_lines = [line for line in keywords_lines if re.match(r"^\d+\.\s+", line)]
    top8_keywords = []
    prioritized_experiences = []
    declared_gap_keywords = []
    for line in top8_lines[:8]:
        match = re.match(r"^\d+\.\s+(.+?)(?:\s+\|\s+experiência alvo:\s+(.+?))?(?:\s+\|.*)?$", line)
        if not match:
            top8_keywords.append(line)
            continue
        keyword = match.group(1).strip()
        target = (match.group(2) or "").strip()
        if keyword:
            top8_keywords.append(keyword)
        if target and target not in prioritized_experiences:
            prioritized_experiences.append(target)
        if "origem: gap sem cobertura" in normalize_text(line) and keyword:
            declared_gap_keywords.append(keyword)
    if top8_keywords:
        values["top8_keywords"] = "\n".join(f"{index}. {keyword}" for index, keyword in enumerate(top8_keywords, start=1))
    if declared_gap_keywords:
        values["declared_gap_keywords"] = "; ".join(declared_gap_keywords)
    if cache_keywords:
        values["keywords"] = "; ".join(cache_keywords)
    elif top8_keywords:
        values["keywords"] = "; ".join(top8_keywords)

    gaps_lines = _extract_section_lines(
        text,
        "Gaps ainda abertos",
        ["Objeções do recrutador e defesa", "Keywords-habilidade para ATS", "Status do serviço"],
    )
    cleaned_gaps = [line.lstrip("- ").strip() for line in gaps_lines if line.strip()]
    if cache_gaps:
        values["gaps"] = "; ".join(cache_gaps)
    elif cleaned_gaps:
        values["gaps"] = "; ".join(cleaned_gaps)

    reposition_lines = _extract_section_lines(
        text,
        "Gaps mitigados por reposicionamento",
        ["Gaps ainda abertos", "Objeções do recrutador e defesa", "Keywords-habilidade para ATS"],
    )
    if reposition_lines:
        values["narrative_decisions"] = "\n".join(reposition_lines[:3])
        if not prioritized_experiences:
            for line in reposition_lines[:3]:
                experience = line.split(":", 1)[0].strip()
                if experience and experience not in prioritized_experiences:
                    prioritized_experiences.append(experience)
    if prioritized_experiences:
        values["prioritized_experiences"] = "\n".join(prioritized_experiences[:8])
        values["persona_angle"] = prioritized_experiences[0]

    service_lines = _extract_section_lines(
        text,
        "Status do serviço",
        ["Pesquisa Inicial", "Análise de aderência"],
    )
    for line in service_lines:
        if line.startswith("Status serviço:"):
            values["service_status"] = line.split(":", 1)[1].strip()
        elif line.startswith("Estado final:"):
            values["final_state"] = line.split(":", 1)[1].strip()
        elif line.startswith("Blockers atuais:"):
            values["review_blockers"] = line.split(":", 1)[1].strip()
        elif line.startswith("Keywords top 8 faltantes:"):
            values["declared_gap_keywords"] = line.split(":", 1)[1].strip()

    if description and not values.get("keywords"):
        existing_keywords = split_terms(description)
        if existing_keywords:
            values["keywords"] = "; ".join(existing_keywords[:15])

    return values


def _local_governance_values(record_id: int | None, app_v2_dir: Path) -> dict[str, Any]:
    if record_id is None:
        return {}
    app_dir = app_v2_dir / str(record_id)
    fit_map_path = app_dir / "fit_map.json"
    if not fit_map_path.exists():
        return {}
    fit_map = read_json(fit_map_path)
    values = governance_field_values(fit_map)
    manifest_path = app_dir / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        values["required_cv_language"] = values.get("required_cv_language") or manifest.get("required_cv_language")
        values["final_cv_language"] = values.get("final_cv_language") or manifest.get("required_cv_language")
    review_path = app_dir / "cv_review_report.json"
    if review_path.exists():
        review = read_json(review_path)
        top8 = review.get("top8_keywords", []) if isinstance(review, dict) else []
        values["review_status"] = "approved" if review.get("approved_for_delivery") else "blocked"
        values["review_blockers"] = "\n".join(item.get("id") for item in review.get("blockers", []) if item.get("id"))
        values["covered_keywords"] = "; ".join(
            str(item.get("keyword")) for item in top8 if item.get("covered")
        )
        values["declared_gap_keywords"] = "; ".join(
            str(item.get("keyword")) for item in top8 if item.get("coverage_class") == "declared_gap"
        )
    polish_path = app_dir / "polish_review.json"
    if polish_path.exists():
        polish = read_json(polish_path)
        blockers = polish.get("approval_blockers", []) if isinstance(polish, dict) else []
        if blockers:
            current = values.get("review_blockers") or ""
            merged = [line for line in current.splitlines() if line]
            for blocker in blockers:
                text = str(blocker).strip()
                if text and text not in merged:
                    merged.append(text)
            values["review_blockers"] = "\n".join(merged)
    return {key: value for key, value in values.items() if _has_value(value)}


def _cache_governance_values(application: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    keywords = _string_list(application.get("keywords", []))
    gaps = _string_list(application.get("gaps", []))
    if keywords:
        values["keywords"] = "; ".join(keywords)
    if gaps:
        values["gaps"] = "; ".join(gaps)
    return values


def _payload_governance_values(payload: dict) -> dict[str, Any]:
    cache_keywords = split_terms(extract_saved_property(payload, "keywords"))
    cache_gaps = split_terms(extract_saved_property(payload, "gaps"))
    description = payload.get("description", "") or ""
    body_text = payload.get("body_text", "") or ""
    values = _extract_body_derived_values(
        body_text,
        description,
        cache_keywords,
        cache_gaps,
    )
    cv_value = extract_saved_property(payload, "final_artifact")
    review_status = extract_saved_property(payload, "review_status")
    if not values.get("required_cv_language") and (description or body_text):
        values["required_cv_language"] = detect_document_language(description or body_text)
    if cv_value:
        values["final_cv_language"] = "en" if "_en." in cv_value.casefold() else "pt-BR"
    if not review_status and not cv_value:
        values["review_status"] = "not_started"
    return {key: value for key, value in values.items() if _has_value(value)}


def _eligible_for_governance_backfill(application: dict, excluded_statuses: set[str]) -> bool:
    if application.get("is_archived"):
        return False
    status = str(application.get("status") or "").strip()
    return normalize_text(status) not in excluded_statuses


def _governance_property_payload(schema: dict, values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    properties: dict[str, Any] = {}
    populated_fields: list[str] = []
    for logical_name, value in values.items():
        prop_name, prop = find_prop(schema, logical_name)
        if not prop_name:
            continue
        converted = property_value(prop, value)
        if converted is None:
            continue
        properties[prop_name] = converted
        populated_fields.append(prop_name)
    return properties, populated_fields


def _filter_mojibake_governance_values(values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    filtered: dict[str, Any] = {}
    skipped: list[str] = []
    for key, value in values.items():
        haystack = ""
        if isinstance(value, list):
            haystack = " ".join(str(item) for item in value)
        elif isinstance(value, str):
            haystack = value
        if haystack and mojibake_hits(haystack):
            skipped.append(key)
            continue
        filtered[key] = value
    return filtered, skipped


def backfill_governance_fields(
    token: str,
    database_id: str,
    *,
    cache_path: Path = DEFAULT_SWEEP_CACHE,
    sweep_dir: Path = DEFAULT_SWEEP_DIR,
    app_v2_dir: Path = Path(".career-state/applications_v2"),
    dry_run: bool = True,
    report_path: Path = DEFAULT_GOVERNANCE_BACKFILL_REPORT,
    excluded_statuses: list[str] | None = None,
) -> dict:
    cache = read_json(cache_path)
    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    sweep_records, invalid_files = load_sweep_records(sweep_dir)
    exclusions = excluded_statuses or ["Desisti da vaga", "Deletada", "Aplicação andamento"]
    normalized_exclusions = {normalize_text(item) for item in exclusions}

    processed = []
    written = 0
    skipped = 0
    populated = 0

    for application in cache.get("applications", []):
        record_id = application.get("record_id")
        page_id = str(application.get("page_id") or "").strip()
        title = str(application.get("title") or "").strip()
        status = str(application.get("status") or "").strip()

        if not _eligible_for_governance_backfill(application, normalized_exclusions):
            skipped += 1
            processed.append({
                "record_id": record_id,
                "page_id": page_id,
                "title": title,
                "status": status,
                "result": "skipped_status",
            })
            continue

        field_values: dict[str, Any] = {}
        field_values = _prefer_value(field_values, _local_governance_values(record_id, app_v2_dir))
        field_values = _prefer_value(field_values, _cache_governance_values(application))

        sweep_payload = (sweep_records.get(page_id) or {}).get("payload")
        if isinstance(sweep_payload, dict):
            field_values = _prefer_value(field_values, _payload_governance_values(sweep_payload))

        field_values, mojibake_skipped_fields = _filter_mojibake_governance_values(field_values)

        properties, populated_fields = _governance_property_payload(schema, field_values)
        if not properties:
            processed.append({
                "record_id": record_id,
                "page_id": page_id,
                "title": title,
                "status": status,
                "result": "no_data",
                "mojibake_skipped_fields": mojibake_skipped_fields,
            })
            continue

        populated += 1
        payload = {"properties": properties}
        validate_notion_payload_text(payload)
        if not dry_run:
            try:
                update_page(token, page_id, payload)
                written += 1
                result_label = "updated"
                error_message = None
            except (SystemExit, Exception) as exc:
                result_label = "write_error"
                error_message = str(exc)
        else:
            result_label = "would_update"
            error_message = None
        processed.append({
            "record_id": record_id,
            "page_id": page_id,
            "title": title,
            "status": status,
            "result": result_label,
            "source_local": bool(_local_governance_values(record_id, app_v2_dir)),
            "source_sweep": bool(sweep_payload),
            "populated_fields": populated_fields,
            "mojibake_skipped_fields": mojibake_skipped_fields,
            "error": error_message,
        })

    report = {
        "database_id": database_id,
        "data_source_id": data_source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "excluded_statuses": exclusions,
        "totals": {
            "applications_seen": len(cache.get("applications", [])),
            "skipped_status": skipped,
            "with_data_to_backfill": populated,
            "written": written,
            "write_errors": sum(1 for item in processed if item.get("result") == "write_error"),
            "invalid_sweep_files": len(invalid_files),
        },
        "processed": processed,
        "invalid_sweep_files": invalid_files,
    }
    write_json(report_path, report)
    return report


def ensure_governance_schema(token: str, database_id: str, *, dry_run: bool = False) -> dict:
    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    current_properties = schema.get("properties", {})
    to_create: dict[str, dict[str, Any]] = {}
    already_present: list[str] = []
    for field in GOVERNANCE_SCHEMA_FIELDS:
        name = field["name"]
        if name in current_properties:
            already_present.append(name)
            continue
        property_payload = {"name": name, **field["schema"]}
        description = field.get("description")
        if description:
            property_payload["description"] = description
        to_create[name] = property_payload
    payload = {"properties": to_create}
    result = {
        "database_id": database_id,
        "data_source_id": data_source_id,
        "requested_fields": [field["name"] for field in GOVERNANCE_SCHEMA_FIELDS],
        "already_present": already_present,
        "to_create": list(to_create.keys()),
        "dry_run": dry_run,
        "payload": payload,
    }
    if dry_run or not to_create:
        return result
    updated = update_data_source(token, data_source_id, payload)
    result["updated_property_count"] = len(to_create)
    result["updated_data_source_id"] = updated.get("id")
    return result


def fit_score_value(fit_map: dict):
    score = fit_map.get("nota_aderencia")
    if isinstance(score, (int, float)):
        return float(score)
    if isinstance(score, dict) and isinstance(score.get("final"), (int, float)):
        return float(score["final"])
    return None


def current_application_date() -> str:
    timezone = os.environ.get("NOTION_APPLICATIONS_DATE_TIMEZONE", "America/Sao_Paulo")
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def fit_map_summary(fit_map: dict) -> str:
    keywords = ", ".join(fit_map.get("keywords_para_ats", [])[:15])
    gaps = "\n".join(f"- {gap}" for gap in fit_map.get("gaps_sem_cobertura", []))
    objections = "\n".join(
        f"- {item.get('objecao')} ({item.get('classificacao')}): {item.get('mitigacao')}"
        for item in fit_map.get("objecoes", [])
    )
    return (
        f"Fit analysis generated locally.\n\n"
        f"Central pain:\n{fit_map.get('dor_central', '')}\n\n"
        f"ATS keywords:\n{keywords}\n\n"
        f"Gaps:\n{gaps or '- none'}\n\n"
        f"Recruiter objections:\n{objections or '- none'}"
    )


def fit_score_breakdown_lines(fit_map: dict) -> list[str]:
    score = fit_map.get("nota_aderencia", {})
    dimensions = score.get("dimensoes", {}) if isinstance(score, dict) else {}
    labels = {
        "requisitos_obrigatorios": "Requisitos obrigatórios",
        "responsabilidades_principais": "Responsabilidades principais",
        "ausencia_gaps_criticos": "Ausência de gaps críticos",
        "diferenciais_desejaveis": "Diferenciais desejáveis",
    }
    lines = []
    for key, label in labels.items():
        dimension = dimensions.get(key, {})
        points = dimension.get("pontos")
        coverage = dimension.get("cobertura_percentual")
        if points is None and coverage is None:
            continue
        line = f"{label}: "
        if coverage is not None:
            line += f"{coverage}% de cobertura"
        if points is not None:
            line += f" | {points} pontos"
        lines.append(line)
    return lines


def repositioned_gap_lines(fit_map: dict) -> list[str]:
    lines = []
    for item in fit_map.get("mapa_ajuste", []):
        if item.get("tipo_ajuste") != "REPOSICIONAMENTO":
            continue
        evidence = item.get("evidencia", "")
        angle = item.get("angulo_sugerido", "")
        adjustments = "; ".join(item.get("ajustes_feitos", []) or [])
        defense = f"{item.get('termo_vaga', '')}: {evidence}"
        if angle:
            defense += f" | defesa: {angle}"
        if adjustments:
            defense += f" | limite/ajuste: {adjustments}"
        lines.append(defense)
    return lines


def recruiter_objection_lines(fit_map: dict) -> list[str]:
    lines = []
    for item in fit_map.get("objecoes", []):
        objection = item.get("objecao", "")
        classification = item.get("classificacao", "")
        mitigation = item.get("mitigacao", "")
        evidence = item.get("evidencia_real", "")
        text = f"{objection} ({classification})"
        if mitigation:
            text += f" | mitigação: {mitigation}"
        if evidence:
            text += f" | evidência: {evidence}"
        lines.append(text)
    return lines


def ats_keyword_lines(fit_map: dict) -> list[str]:
    lines = []
    entries = sorted(
        fit_map.get("keywords_habilidade_ats", []) or [],
        key=lambda item: item.get("prioridade", 999) if isinstance(item, dict) else 999,
    )
    for item in entries:
        if not isinstance(item, dict):
            continue
        priority = item.get("prioridade", "")
        keyword = item.get("keyword", "")
        target = item.get("experiencia_alvo", "")
        bullet = item.get("bullet_sugerido", "")
        origin = item.get("origem", "")
        if not keyword:
            continue
        line = f"{priority}. {keyword}"
        details = []
        if target:
            details.append(f"experiência alvo: {target}")
        if bullet:
            details.append(f"bullet: {bullet}")
        if origin:
            details.append(f"origem: {origin}")
        if details:
            line += " | " + " | ".join(details)
        lines.append(line)
    return lines


def notion_analysis_blocks(fit_map: dict) -> list[dict]:
    score = fit_score_value(fit_map)
    blocks = [
        heading_block("Análise de aderência"),
        paragraph_block(
            f"Nota de aderência: {score:.2f} / 10"
            if isinstance(score, (int, float))
            else "Nota de aderência: não disponível"
        ),
        paragraph_block(f"Dor central: {fit_map.get('dor_central', '')}"),
        heading_block("Resumo das notas", level=3),
    ]
    score_lines = fit_score_breakdown_lines(fit_map)
    blocks.extend(bullet_block(line) for line in (score_lines or ["Sem detalhamento dimensional disponível."]))
    blocks.append(heading_block("Gaps mitigados por reposicionamento", level=3))
    repos_lines = repositioned_gap_lines(fit_map)
    blocks.extend(bullet_block(line) for line in (repos_lines or ["Nenhum reposicionamento registrado."]))
    blocks.append(heading_block("Gaps ainda abertos", level=3))
    gaps = fit_map.get("gaps_sem_cobertura", []) or []
    blocks.extend(bullet_block(gap) for gap in (gaps or ["Nenhum gap sem cobertura registrado."]))
    blocks.append(heading_block("Objeções do recrutador e defesa", level=3))
    objection_lines = recruiter_objection_lines(fit_map)
    blocks.extend(bullet_block(line) for line in (objection_lines or ["Nenhuma objeção registrada."]))
    blocks.append(heading_block("Keywords-habilidade para ATS", level=3))
    keyword_lines = ats_keyword_lines(fit_map)
    blocks.extend(bullet_block(line) for line in (keyword_lines or ["Nenhuma keyword-habilidade registrada."]))
    if fit_map.get("service_status") or fit_map.get("service_stage"):
        blocks.append(heading_block("Status do serviço", level=3))
        service_lines = []
        if fit_map.get("service_status"):
            service_lines.append(f"Status serviço: {fit_map.get('service_status')}")
        if fit_map.get("service_stage"):
            service_lines.append(f"Estado final: {fit_map.get('service_stage')}")
        if fit_map.get("service_stage_status"):
            service_lines.append(f"Estado técnico: {fit_map.get('service_stage_status')}")
        if fit_map.get("service_next_action"):
            service_lines.append(f"Próxima ação: {fit_map.get('service_next_action')}")
        if fit_map.get("service_review_blockers"):
            service_lines.append("Blockers atuais: " + ", ".join(fit_map.get("service_review_blockers", [])))
        if fit_map.get("service_missing_top8"):
            service_lines.append("Keywords top 8 faltantes: " + ", ".join(fit_map.get("service_missing_top8", [])))
        if fit_map.get("service_repair_attempt_count") is not None:
            service_lines.append(f"Tentativas de repair: {fit_map.get('service_repair_attempt_count')}")
        blocks.extend(bullet_block(line) for line in service_lines)
    return blocks[:100]


def read_job_description(path) -> str:
    if not path:
        return ""
    if not path.exists():
        raise SystemExit(f"Job description file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    assert_clean_display_text(f"job description file {path}", text)
    return text


def is_template_job_description(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    template_markers = (
        "pesquisa inicial feedback em caso de reprovacao",
        "feedback em caso de reprovacao",
        "template de vaga",
    )
    return len(normalized) <= 120 and any(marker in normalized for marker in template_markers)


def find_saved_job_description_for_fit_map(fit_map: dict, directory: Path = Path("inbox/job_descriptions")):
    if not directory.exists():
        return None
    company = str(fit_map.get("empresa", "")).strip()
    role = str(fit_map.get("cargo", "")).strip()
    role_slug = slugify(role)
    company_slug = slugify(company)
    role_normalized = normalize_text(role)
    company_normalized = normalize_text(company)
    candidates: list[tuple[int, float, Path]] = []
    for path in directory.glob("*.md"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if is_template_job_description(text):
            continue
        if mojibake_hits(text):
            continue
        stem_slug = slugify(path.stem)
        heading = normalize_text(job_description_heading(text))
        score = 0
        if role_slug and role_slug in stem_slug:
            score += 4
        if company_slug and company_slug in stem_slug:
            score += 2
        if role_normalized and role_normalized in heading:
            score += 4
        if company_normalized and company_normalized in heading:
            score += 2
        if score:
            candidates.append((score, path.stat().st_mtime, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def select_job_description_for_update(
    fit_map: dict,
    explicit_path,
    page_description: str,
    saved_job_dir: Path = Path("inbox/job_descriptions"),
) -> tuple[str, Path, str]:
    if explicit_path:
        return read_job_description(explicit_path), explicit_path, "explicit"

    fit_map_description = str(fit_map.get("descricao_vaga", "")).strip()
    if fit_map_description and not is_template_job_description(fit_map_description):
        assert_clean_display_text("FIT_MAP descricao_vaga", fit_map_description)
        return fit_map_description, None, "fit_map.descricao_vaga"

    inferred_path = find_saved_job_description_for_fit_map(fit_map, saved_job_dir)
    if inferred_path and (not page_description or is_template_job_description(page_description)):
        return read_job_description(inferred_path), inferred_path, "saved_job_description"

    if page_description and not is_template_job_description(page_description):
        if not mojibake_hits(page_description):
            return page_description, None, "notion_page.description"
        if inferred_path:
            return read_job_description(inferred_path), inferred_path, "saved_job_description"
        raise SystemExit(
            "Notion page description contains mojibake and no clean saved job description was found for this FIT_MAP. "
            "Fix the saved description under inbox/job_descriptions/ or pass --job-description <file> with clean UTF-8 text."
        )

    if inferred_path:
        return read_job_description(inferred_path), inferred_path, "saved_job_description"

    return page_description.strip(), None, "notion_page.description"


def resolve_source_url(
    job_description: str,
    job_description_path: Path | None = None,
    *,
    source_url: str | None = None,
    fallback_url: str | None = None,
) -> str:
    metadata = job_description_metadata(
        job_description,
        job_description_path,
        source_url=source_url,
    )
    return (metadata.get("source_url") or fallback_url or "").strip()


def create_from_fit_map(
    token: str,
    database_id: str,
    fit_map_path: Path,
    job_description_path = None,
    dry_run: bool = False,
    template = "default",
    template_id = None,
    allow_mismatch: bool = False,
    append_summary: bool = True,
    status: str = "Aplicação andamento",
) -> dict:
    fit_map = json.loads(fit_map_path.read_text(encoding="utf-8"))
    job_description = read_job_description(job_description_path) or fit_map.get("descricao_vaga", "").strip()
    if not job_description:
        raise SystemExit("Job description is required when creating a Notion application record. Use --job-description <file> or include descricao_vaga in FIT_MAP.")
    if job_description_path and job_description_path.name.startswith("notion_record_"):
        raise SystemExit("Refusing to create a new Notion record for a vacancy that originated from Notion. Use update-from-fit-map or update-from-fit-map-record instead.")

    ensure_fit_map_matches_job_description(fit_map, job_description, job_description_path, allow_mismatch)

    score = fit_score_value(fit_map)
    if score is None:
        raise SystemExit("Fit score is required when creating a Notion application record.")

    template_id = template_id or os.environ.get("NOTION_APPLICATIONS_TEMPLATE_ID", "").strip() or None
    if not template_id and template != "default":
        raise SystemExit("A Notion template is required. Set NOTION_APPLICATIONS_TEMPLATE_ID or pass --template default / --template-id <id>.")

    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    properties: dict[str, Any] = {}

    title_name, title_prop = find_prop(schema, "title", "title")
    if not title_name or not title_prop:
        raise SystemExit("Could not find a title property in the Notion database.")

    role = fit_map.get("cargo", "")
    company = fit_map.get("empresa", "")
    source_url = resolve_source_url(job_description, job_description_path)
    title = f"{company} - {role}".strip(" -")
    properties[title_name] = property_value(title_prop, title)

    mappings = {
        "company": company,
        "role": role,
        "fit": score,
        "status": status,
        "application_date": current_application_date(),
        "description": job_description,
        "source_url": source_url,
        "keywords": fit_map.get("keywords_para_ats", []),
        "gaps": fit_map.get("gaps_sem_cobertura", []),
    }
    mappings.update(governance_field_values(fit_map))
    for logical_name, value in mappings.items():
        prop_name, prop = find_prop(schema, logical_name)
        if not prop_name or prop_name == title_name:
            continue
        converted = property_value(prop, value)
        if converted is not None:
            properties[prop_name] = converted

    payload = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }

    timezone = os.environ.get("NOTION_APPLICATIONS_TEMPLATE_TIMEZONE", "America/Sao_Paulo")
    if template_id:
        payload["template"] = {
            "type": "template_id",
            "template_id": template_id,
            "timezone": timezone,
        }
    else:
        payload["template"] = {
            "type": "default",
            "timezone": timezone,
        }

    blocks = notion_analysis_blocks(fit_map) if append_summary else []
    validate_notion_payload_text(blocks)

    if dry_run:
        validate_notion_payload_text(payload)
        return {
            "page_create": payload,
            "append_blocks": blocks,
            "insert_after_block_text": "Pesquisa Inicial",
        }
    validate_notion_payload_text(payload)
    created_page = request("POST", notion_url("pages"), token, payload, notion_version=NOTION_TEMPLATE_VERSION)
    appended = None
    if blocks:
        page_id = created_page.get("id")
        current_blocks = retrieve_blocks(token, page_id) if page_id else []
        anchor_block_id = find_anchor_block_id(current_blocks, "Pesquisa Inicial")
        appended = append_blocks(token, page_id, blocks, after_block_id=anchor_block_id) if page_id else None
    return {"page": created_page, "blocks": appended}


def update_from_fit_map(
    token: str,
    database_id: str,
    page_id: str,
    fit_map_path: Path,
    job_description_path = None,
    dry_run: bool = False,
    append_summary: bool = True,
    allow_mismatch: bool = False,
    status: str = "Aplicação andamento",
) -> dict:
    fit_map = json.loads(fit_map_path.read_text(encoding="utf-8"))
    current_page = extract_page_payload(token, page_id)
    current_blocks = retrieve_blocks(token, page_id)
    page_description = (current_page.get("description") or "").strip()
    current_source_url = str(current_page.get("source_url") or "").strip()
    job_description, resolved_job_description_path, job_description_source = select_job_description_for_update(
        fit_map,
        job_description_path,
        page_description,
    )
    if not job_description:
        raise SystemExit("A job description is required to update a Notion application page from FIT_MAP.")
    ensure_fit_map_matches_job_description(fit_map, job_description, resolved_job_description_path, allow_mismatch)

    score = fit_score_value(fit_map)
    if score is None:
        raise SystemExit("Fit score is required when updating a Notion application record.")

    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    properties: dict[str, Any] = {}
    title_name, title_prop = find_prop(schema, "title", "title")
    if not title_name or not title_prop:
        raise SystemExit("Could not find a title property in the Notion database.")

    role = fit_map.get("cargo", "")
    company = fit_map.get("empresa", "")
    source_url = resolve_source_url(
        job_description,
        resolved_job_description_path,
        fallback_url=current_source_url,
    )
    title = role.strip()
    if not title:
        title = f"{company} - {role}".strip(" -")
    properties[title_name] = property_value(title_prop, title)
    mappings = {
        "fit": score,
        "status": status,
        "application_date": current_application_date(),
        "description": job_description,
        "source_url": source_url,
        "company": company,
        "role": role,
        "service_status": fit_map.get("service_status", ""),
        "final_state": fit_map.get("service_stage", ""),
    }
    mappings.update(governance_field_values(fit_map))
    for logical_name, value in mappings.items():
        prop_name, prop = find_prop(schema, logical_name)
        if not prop_name or prop_name == title_name:
            continue
        converted = property_value(prop, value)
        if converted is not None:
            properties[prop_name] = converted

    page_payload = {"properties": properties}
    blocks = notion_analysis_blocks(fit_map) if append_summary else []
    validate_notion_payload_text(page_payload)
    validate_notion_payload_text(blocks)
    anchor_block_id = find_anchor_block_id(current_blocks, "Pesquisa Inicial")
    if dry_run:
        return {
            "page_update": page_payload,
            "append_blocks": blocks,
            "insert_after_block_id": anchor_block_id,
            "insert_after_block_text": "Pesquisa Inicial" if anchor_block_id else None,
            "job_description_source": job_description_source,
            "job_description_path": str(resolved_job_description_path) if resolved_job_description_path else None,
        }

    updated_page = update_page(token, page_id, page_payload)
    appended = append_blocks(token, page_id, blocks, after_block_id=anchor_block_id) if blocks else None
    return {
        "page": updated_page,
        "blocks": appended,
        "job_description_source": job_description_source,
        "job_description_path": str(resolved_job_description_path) if resolved_job_description_path else None,
    }


def update_from_fit_map_record(
    token: str,
    database_id: str,
    record_id: int,
    fit_map_path: Path,
    job_description_path = None,
    dry_run: bool = False,
    append_summary: bool = True,
    allow_mismatch: bool = False,
    status: str = "Aplicação andamento",
) -> dict:
    page = resolve_page_by_record_id(token, database_id, record_id)
    result = update_from_fit_map(
        token,
        database_id,
        page["id"],
        fit_map_path,
        job_description_path=job_description_path,
        dry_run=dry_run,
        append_summary=append_summary,
        allow_mismatch=allow_mismatch,
        status=status,
    )
    if isinstance(result, dict):
        result["resolved_page_id"] = page["id"]
        result["resolved_record_id"] = record_id
    return result


def job_description_metadata(text: str, path: Path | None = None, *, company: str | None = None, role: str | None = None, source_url: str | None = None) -> dict:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    inferred_role = ""
    inferred_company = ""
    inferred_source_url = ""
    metadata_prefixes = {
        "empresa:": "company",
        "company:": "company",
        "fonte:": "source_url",
        "source:": "source_url",
    }

    for line in lines:
        cleaned = line.lstrip("#").strip()
        lowered = cleaned.casefold()
        matched_metadata = False
        for prefix, key in metadata_prefixes.items():
            if lowered.startswith(prefix):
                value = cleaned.split(":", 1)[1].strip()
                if key == "company" and value and not inferred_company:
                    inferred_company = value
                if key == "source_url" and value and not inferred_source_url:
                    inferred_source_url = value
                matched_metadata = True
                break
        if matched_metadata:
            continue
        if not inferred_role and not is_job_description_boilerplate_heading(cleaned):
            inferred_role = cleaned

    if path and (not inferred_company or not inferred_role):
        stem = path.stem
        for prefix in ("linkedin_post_", "linkedin_"):
            if stem.startswith(prefix):
                stem = stem[len(prefix):]
                break
        parts = [part for part in stem.split("_") if part and not re.fullmatch(r"\d{8}t?\d*", part)]
        if not inferred_company and len(parts) >= 2:
            inferred_company = parts[0].replace("_", " ").title()
        if not inferred_role and len(parts) >= 2:
            inferred_role = " ".join(parts[1:]).replace("_", " ").title()

    return {
        "company": (company or inferred_company or "").strip(),
        "role": (role or inferred_role or "").strip(),
        "source_url": (source_url or inferred_source_url or "").strip(),
    }


def validate_standalone_job_description(text: str, path: Path | None = None) -> None:
    if not text.strip():
        raise SystemExit("Job description is empty.")
    if len(text.strip()) < 120:
        raise SystemExit("Job description is too short to write to Notion safely.")
    assert_clean_display_text(f"job description {path or ''}".strip(), text)
    if is_template_job_description(text):
        raise SystemExit("Job description appears to be a template/placeholder, not a real vacancy description.")
    if re.search(r"Sign in|Entrar|Join LinkedIn|Cadastre-se|Security verification|verificação de segurança", text[:1200], re.I):
        raise SystemExit("Job description appears to contain login/security text, not a vacancy description.")


def build_description_properties(
    schema: dict,
    *,
    description: str,
    company: str = "",
    role: str = "",
    source_url: str = "",
    status: str = "",
    include_title: bool = False,
    include_company_role: bool = False,
    include_application_date: bool = False,
) -> dict:
    properties: dict[str, Any] = {}

    if include_title:
        title_name, title_prop = find_prop(schema, "title", "title")
        if not title_name or not title_prop:
            raise SystemExit("Could not find a title property in the Notion database.")
        title = role if include_company_role else f"{company} - {role}".strip(" -")
        if not title:
            raise SystemExit("Company and role are required to create a Notion vacancy record.")
        properties[title_name] = property_value(title_prop, title)

    mappings = {
        "description": description,
        "source_url": source_url,
        "status": status,
    }
    if include_company_role:
        mappings["company"] = company
        mappings["role"] = role
    if include_application_date:
        mappings["application_date"] = current_application_date()

    for logical_name, value in mappings.items():
        if not value:
            continue
        prop_name, prop = find_prop(schema, logical_name)
        if not prop_name:
            continue
        converted = property_value(prop, value)
        if converted is not None:
            properties[prop_name] = converted

    if not properties:
        raise SystemExit("No compatible Notion properties were found for the description update.")
    return properties


def update_description_record(
    token: str,
    database_id: str,
    record_id: int,
    job_description_path: Path,
    source_url: str | None = None,
    dry_run: bool = False,
    status: str = "",
) -> dict:
    job_description = read_job_description(job_description_path)
    validate_standalone_job_description(job_description, job_description_path)
    metadata = job_description_metadata(job_description, job_description_path, source_url=source_url)
    page = resolve_page_by_record_id(token, database_id, record_id)
    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    properties = build_description_properties(
        schema,
        description=job_description,
        source_url=metadata["source_url"],
        status=status,
    )
    payload = {"properties": properties}
    validate_notion_payload_text(payload)
    if dry_run:
        return {
            "page_update": payload,
            "resolved_page_id": page["id"],
            "resolved_record_id": record_id,
            "job_description_path": str(job_description_path),
            "description_chars": len(job_description),
            "source_url": metadata["source_url"] or None,
        }
    return {
        "page": update_page(token, page["id"], payload),
        "resolved_page_id": page["id"],
        "resolved_record_id": record_id,
        "job_description_path": str(job_description_path),
        "description_chars": len(job_description),
        "source_url": metadata["source_url"] or None,
    }


def create_description_record(
    token: str,
    database_id: str,
    job_description_path: Path,
    company: str | None = None,
    role: str | None = None,
    source_url: str | None = None,
    dry_run: bool = False,
    template: str = "default",
    template_id = None,
    status: str = "Fila Agente",
) -> dict:
    job_description = read_job_description(job_description_path)
    validate_standalone_job_description(job_description, job_description_path)
    metadata = job_description_metadata(
        job_description,
        job_description_path,
        company=company,
        role=role,
        source_url=source_url,
    )
    if not metadata["company"] or not metadata["role"]:
        raise SystemExit("Company and role are required to create a Notion vacancy record. Pass --company and --role.")

    template_id = template_id or os.environ.get("NOTION_APPLICATIONS_TEMPLATE_ID", "").strip() or None
    if not template_id and template != "default":
        raise SystemExit("A Notion template is required. Set NOTION_APPLICATIONS_TEMPLATE_ID or pass --template default / --template-id <id>.")

    data_source_id = discover_data_source_id(token, database_id)
    schema = retrieve_data_source(token, data_source_id)
    properties = build_description_properties(
        schema,
        description=job_description,
        company=metadata["company"],
        role=metadata["role"],
        source_url=metadata["source_url"],
        status=status,
        include_title=True,
        include_company_role=True,
        include_application_date=True,
    )
    payload = {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    }
    timezone = os.environ.get("NOTION_APPLICATIONS_TEMPLATE_TIMEZONE", "America/Sao_Paulo")
    if template_id:
        payload["template"] = {
            "type": "template_id",
            "template_id": template_id,
            "timezone": timezone,
        }
    else:
        payload["template"] = {
            "type": "default",
            "timezone": timezone,
        }

    validate_notion_payload_text(payload)
    if dry_run:
        return {
            "page_create": payload,
            "job_description_path": str(job_description_path),
            "description_chars": len(job_description),
            "company": metadata["company"],
            "role": metadata["role"],
            "source_url": metadata["source_url"] or None,
        }
    return {
        "page": request("POST", notion_url("pages"), token, payload, notion_version=NOTION_TEMPLATE_VERSION),
        "job_description_path": str(job_description_path),
        "description_chars": len(job_description),
        "company": metadata["company"],
        "role": metadata["role"],
        "source_url": metadata["source_url"] or None,
    }


def list_pages(token: str, database_id: str, limit: int) -> list[dict]:
    result = query_database(token, database_id, {"page_size": min(limit, 100)})
    rows = []
    for page in result.get("results", []):
        props = page.get("properties", {})
        title = ""
        for name, prop in props.items():
            if prop.get("type") == "title":
                title = prop_text(prop)
                break
        rows.append({
            "id": page.get("id"),
            "title": title,
            "url": page.get("url"),
        })
    return rows


def record_link(token: str, database_id: str, record_id: int, *, compact: bool = False) -> dict:
    page = resolve_page_by_record_id(token, database_id, record_id)
    props = page.get("properties", {})
    title = ""
    company = ""
    company_type = ""
    source_url = ""
    status = ""
    for name, prop in props.items():
        if prop.get("type") == "title" and not title:
            title = prop_text(prop)
        if name in PROPERTY_ALIASES.get("company", []) and not company:
            company = prop_text(prop, token=token)
        if name in PROPERTY_ALIASES.get("company_type", []) and not company_type:
            company_type = prop_text(prop, token=token)
        if name in PROPERTY_ALIASES.get("source_url", []) and not source_url:
            source_url = prop_text(prop)
        if name in PROPERTY_ALIASES.get("status", []) and not status:
            status = prop_text(prop)
    payload = {
        "record_id": record_id,
        "page_id": page.get("id"),
        "title": title,
        "status": status,
        "notion_url": page.get("url"),
    }
    if not compact:
        payload["company"] = company or None
        payload["company_type"] = company_type or None
        payload["source_url"] = source_url or None
    return payload


def compact_notion_write_result(result: dict, *, dry_run: bool, operation: str) -> dict:
    page_payload = result.get("page_update") or result.get("page_create") or {}
    append_blocks = result.get("append_blocks") or []
    properties = page_payload.get("properties") if isinstance(page_payload, dict) else {}
    page = result.get("page") if isinstance(result.get("page"), dict) else {}
    return {
        "status": "dry_run" if dry_run else "written",
        "operation": operation,
        "resolved_record_id": result.get("resolved_record_id"),
        "resolved_page_id": result.get("resolved_page_id") or page.get("id"),
        "notion_url": page.get("url"),
        "job_description_source": result.get("job_description_source"),
        "job_description_path": result.get("job_description_path"),
        "property_count": len(properties or {}),
        "append_block_count": len(append_blocks) if isinstance(append_blocks, list) else None,
        "insert_after_block_text": result.get("insert_after_block_text"),
        "has_anchor": bool(result.get("insert_after_block_id") or result.get("insert_after_block_text")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read from or explicitly create records in the Notion applications tracker.")
    parser.add_argument("--database-id", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("schema")
    governance_schema_parser = subparsers.add_parser("ensure-governance-schema")
    governance_schema_parser.add_argument("--dry-run", action="store_true")
    governance_backfill_parser = subparsers.add_parser("backfill-governance-fields")
    governance_backfill_parser.add_argument("--dry-run", action="store_true")
    governance_backfill_parser.add_argument("--cache-path", default=str(DEFAULT_SWEEP_CACHE))
    governance_backfill_parser.add_argument("--sweep-dir", default=str(DEFAULT_SWEEP_DIR))
    governance_backfill_parser.add_argument("--report", default=str(DEFAULT_GOVERNANCE_BACKFILL_REPORT))

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=20)

    link_record_parser = subparsers.add_parser("link-record")
    link_record_parser.add_argument("record_id", type=int)
    link_record_parser.add_argument("--compact", action="store_true")

    templates_parser = subparsers.add_parser("templates")
    templates_parser.add_argument("--name", default=None)

    page_parser = subparsers.add_parser("read-page")
    page_parser.add_argument("page_id")
    page_parser.add_argument("--save", action="store_true")
    page_parser.add_argument("--output-dir", default="inbox/notion")

    prepare_parser = subparsers.add_parser("prepare-analysis-from-page")
    prepare_parser.add_argument("page_id")
    prepare_parser.add_argument("--payload-output-dir", default="inbox/notion")
    prepare_parser.add_argument("--description-output-dir", default="inbox/job_descriptions")

    prepare_record_parser = subparsers.add_parser("prepare-analysis-from-record")
    prepare_record_parser.add_argument("record_id", type=int)
    prepare_record_parser.add_argument("--payload-output-dir", default="inbox/notion")
    prepare_record_parser.add_argument("--description-output-dir", default="inbox/job_descriptions")

    sweep_sync_parser = subparsers.add_parser("sync-applications-sweep")
    sweep_sync_parser.add_argument("--output-dir", default=str(DEFAULT_SWEEP_DIR))
    sweep_sync_parser.add_argument("--refresh", choices=["missing", "full"], default="missing")
    sweep_sync_parser.add_argument("--summary-output", default=str(DEFAULT_SWEEP_SUMMARY))
    sweep_sync_parser.add_argument("--cache-output", default=str(DEFAULT_SWEEP_CACHE))

    sweep_cache_parser = subparsers.add_parser("build-applications-cache")
    sweep_cache_parser.add_argument("--sweep-dir", default=str(DEFAULT_SWEEP_DIR))
    sweep_cache_parser.add_argument("--summary-output", default=str(DEFAULT_SWEEP_SUMMARY))
    sweep_cache_parser.add_argument("--cache-output", default=str(DEFAULT_SWEEP_CACHE))

    refresh_cache_parser = subparsers.add_parser("refresh-applications-cache")
    refresh_cache_parser.add_argument("--output-dir", default=str(DEFAULT_SWEEP_DIR))
    refresh_cache_parser.add_argument("--refresh", choices=["missing", "full"], default="missing")
    refresh_cache_parser.add_argument("--summary-output", default=str(DEFAULT_SWEEP_SUMMARY))
    refresh_cache_parser.add_argument("--cache-output", default=str(DEFAULT_SWEEP_CACHE))

    create_parser = subparsers.add_parser("create-from-fit-map")
    create_parser.add_argument("--fit-map", default=".career-state/fit_map.json")
    create_parser.add_argument("--job-description", default=None)
    create_parser.add_argument("--dry-run", action="store_true")
    create_parser.add_argument("--template", choices=["default"], default="default")
    create_parser.add_argument("--template-id", default=None)
    create_parser.add_argument("--allow-mismatch", action="store_true")
    create_parser.add_argument("--no-append-summary", action="store_true")
    create_parser.add_argument("--compact", action="store_true")
    create_parser.add_argument("--status", default="Aplicação andamento")

    update_parser = subparsers.add_parser("update-from-fit-map")
    update_parser.add_argument("page_id")
    update_parser.add_argument("--fit-map", default=".career-state/fit_map.json")
    update_parser.add_argument("--job-description", default=None)
    update_parser.add_argument("--dry-run", action="store_true")
    update_parser.add_argument("--no-append-summary", action="store_true")
    update_parser.add_argument("--allow-mismatch", action="store_true")
    update_parser.add_argument("--compact", action="store_true")
    update_parser.add_argument("--status", default="Aplicação andamento")

    update_record_parser = subparsers.add_parser("update-from-fit-map-record")
    update_record_parser.add_argument("record_id", type=int)
    update_record_parser.add_argument("--fit-map", default=".career-state/fit_map.json")
    update_record_parser.add_argument("--job-description", default=None)
    update_record_parser.add_argument("--dry-run", action="store_true")
    update_record_parser.add_argument("--no-append-summary", action="store_true")
    update_record_parser.add_argument("--allow-mismatch", action="store_true")
    update_record_parser.add_argument("--compact", action="store_true")
    update_record_parser.add_argument("--status", default="Aplicação andamento")

    update_description_record_parser = subparsers.add_parser("update-description-record")
    update_description_record_parser.add_argument("record_id", type=int)
    update_description_record_parser.add_argument("--job-description", required=True)
    update_description_record_parser.add_argument("--source-url", default=None)
    update_description_record_parser.add_argument("--dry-run", action="store_true")
    update_description_record_parser.add_argument("--status", default="")

    create_description_parser = subparsers.add_parser("create-description-record")
    create_description_parser.add_argument("--job-description", required=True)
    create_description_parser.add_argument("--company", default=None)
    create_description_parser.add_argument("--role", default=None)
    create_description_parser.add_argument("--source-url", default=None)
    create_description_parser.add_argument("--dry-run", action="store_true")
    create_description_parser.add_argument("--template", choices=["default"], default="default")
    create_description_parser.add_argument("--template-id", default=None)
    create_description_parser.add_argument("--status", default="Fila Agente")

    args = parser.parse_args()
    token, default_database_id = notion_config()
    database_id = args.database_id or default_database_id

    if args.command == "schema":
        schema = retrieve_database(token, database_id)
        print(json.dumps(schema.get("properties", {}), ensure_ascii=False, indent=2))
        return 0

    if args.command == "ensure-governance-schema":
        result = ensure_governance_schema(token, database_id, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "backfill-governance-fields":
        result = backfill_governance_fields(
            token,
            database_id,
            cache_path=Path(args.cache_path),
            sweep_dir=Path(args.sweep_dir),
            dry_run=args.dry_run,
            report_path=Path(args.report),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "list":
        print(json.dumps(list_pages(token, database_id, args.limit), ensure_ascii=False, indent=2))
        return 0

    if args.command == "link-record":
        print(json.dumps(record_link(token, database_id, args.record_id, compact=args.compact), ensure_ascii=False, indent=2))
        return 0

    if args.command == "templates":
        data_source_id = discover_data_source_id(token, database_id)
        print(json.dumps(list_templates(token, data_source_id, args.name), ensure_ascii=False, indent=2))
        return 0

    if args.command == "read-page":
        payload = extract_page_payload(token, args.page_id)
        if args.save:
            path = save_page_payload(payload, Path(args.output_dir))
            print(f"Saved Notion page payload: {path}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "prepare-analysis-from-page":
        result = prepare_analysis_from_page(
            token,
            args.page_id,
            Path(args.payload_output_dir),
            Path(args.description_output_dir),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "prepare-analysis-from-record":
        result = prepare_analysis_from_record(
            token,
            database_id,
            args.record_id,
            Path(args.payload_output_dir),
            Path(args.description_output_dir),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "sync-applications-sweep":
        report = sync_applications_sweep(
            token,
            database_id,
            Path(args.output_dir),
            args.refresh,
        )
        outputs = build_sweep_outputs(
            Path(args.output_dir),
            Path(args.summary_output),
            Path(args.cache_output),
            remote_pages=report["remote_pages"],
            database_id=database_id,
        )
        print(
            json.dumps(
                {
                    "sync": {key: value for key, value in report.items() if key != "remote_pages"},
                    "summary": outputs["summary"]["coverage"],
                    "cache_file": args.cache_output,
                    "summary_file": args.summary_output,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "build-applications-cache":
        outputs = build_sweep_outputs(
            Path(args.sweep_dir),
            Path(args.summary_output),
            Path(args.cache_output),
            database_id=database_id,
        )
        print(
            json.dumps(
                {
                    "cache_file": args.cache_output,
                    "summary_file": args.summary_output,
                    "coverage": outputs["summary"]["coverage"],
                    "total_pages": outputs["summary"]["total_pages"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "refresh-applications-cache":
        report = sync_applications_sweep(
            token,
            database_id,
            Path(args.output_dir),
            args.refresh,
        )
        outputs = build_sweep_outputs(
            Path(args.output_dir),
            Path(args.summary_output),
            Path(args.cache_output),
            remote_pages=report["remote_pages"],
            database_id=database_id,
        )
        print(
            json.dumps(
                {
                    "sync": {key: value for key, value in report.items() if key != "remote_pages"},
                    "coverage": outputs["summary"]["coverage"],
                    "cache_file": args.cache_output,
                    "summary_file": args.summary_output,
                    "total_pages": outputs["summary"]["total_pages"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "create-from-fit-map":
        template_id = args.template_id or os.environ.get("NOTION_APPLICATIONS_TEMPLATE_ID", "").strip() or None
        result = create_from_fit_map(
            token,
            database_id,
            Path(args.fit_map),
            job_description_path=Path(args.job_description) if args.job_description else None,
            dry_run=args.dry_run,
            template=args.template,
            template_id=template_id,
            allow_mismatch=args.allow_mismatch,
            append_summary=not args.no_append_summary,
            status=args.status,
        )
        print(json.dumps(compact_notion_write_result(result, dry_run=args.dry_run, operation="create_from_fit_map") if args.compact else result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "update-from-fit-map":
        result = update_from_fit_map(
            token,
            database_id,
            args.page_id,
            Path(args.fit_map),
            job_description_path=Path(args.job_description) if args.job_description else None,
            dry_run=args.dry_run,
            append_summary=not args.no_append_summary,
            allow_mismatch=args.allow_mismatch,
            status=args.status,
        )
        print(json.dumps(compact_notion_write_result(result, dry_run=args.dry_run, operation="update_from_fit_map") if args.compact else result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "update-from-fit-map-record":
        result = update_from_fit_map_record(
            token,
            database_id,
            args.record_id,
            Path(args.fit_map),
            job_description_path=Path(args.job_description) if args.job_description else None,
            dry_run=args.dry_run,
            append_summary=not args.no_append_summary,
            allow_mismatch=args.allow_mismatch,
            status=args.status,
        )
        print(json.dumps(compact_notion_write_result(result, dry_run=args.dry_run, operation="update_from_fit_map_record") if args.compact else result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "update-description-record":
        result = update_description_record(
            token,
            database_id,
            args.record_id,
            Path(args.job_description),
            source_url=args.source_url,
            dry_run=args.dry_run,
            status=args.status,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "create-description-record":
        template_id = args.template_id or os.environ.get("NOTION_APPLICATIONS_TEMPLATE_ID", "").strip() or None
        result = create_description_record(
            token,
            database_id,
            Path(args.job_description),
            company=args.company,
            role=args.role,
            source_url=args.source_url,
            dry_run=args.dry_run,
            template=args.template,
            template_id=template_id,
            status=args.status,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
