from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import sys
import unicodedata

try:
    import notion_sync as legacy_notion
except ModuleNotFoundError:
    scripts_path = Path(__file__).resolve().parents[3] / "scripts"
    sys.path.insert(0, str(scripts_path))
    import notion_sync as legacy_notion

from career.schemas.notion import NotionApplicationsCacheSchema
from career.utils import read_json


_COMPARISON_OPERATORS = {
    "maior ou igual a": "greater_than_or_equal_to",
    "menor ou igual a": "less_than_or_equal_to",
    "maior que": "greater_than",
    "menor que": "less_than",
    "igual a": "equals",
}
_TEXT_TYPES = {"title", "rich_text"}
_SUPPORTED_FILTER_TYPES = _TEXT_TYPES | {"status", "select", "checkbox", "number", "date"}
_CONVERSATIONAL_FIELD_ALIASES = {
    "empresa": "company",
    "companhia": "company",
    "cargo": "role",
    "vaga": "role",
    "aderencia": "fit",
    "nota": "fit",
    "status": "status",
    "etapa funil": "status",
}


def _normalize_filter_text(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", str(value or "").casefold())
        if not unicodedata.combining(char)
    )


def _filter_property_names(schema: dict) -> list[tuple[str, str, dict]]:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    names: dict[str, tuple[str, str, dict]] = {}
    for name, prop in properties.items():
        names[_normalize_filter_text(name)] = (name, name, prop)
    for logical_name, aliases in legacy_notion.PROPERTY_ALIASES.items():
        for alias in aliases:
            prop = properties.get(alias)
            if prop:
                names[_normalize_filter_text(logical_name)] = (logical_name, alias, prop)
                break
    for conversational_name, logical_name in _CONVERSATIONAL_FIELD_ALIASES.items():
        aliases = legacy_notion.PROPERTY_ALIASES.get(logical_name, [])
        prop_name = next((alias for alias in aliases if alias in properties), None)
        if prop_name:
            names[_normalize_filter_text(conversational_name)] = (conversational_name, prop_name, properties[prop_name])
    return sorted(names.values(), key=lambda item: len(_normalize_filter_text(item[0])), reverse=True)


def _split_filter_clause(clause: str, schema: dict) -> tuple[str, str, dict, str]:
    normalized = _normalize_filter_text(clause).strip()
    for alias, property_name, prop in _filter_property_names(schema):
        if normalized == _normalize_filter_text(alias):
            return alias, property_name, prop, ""
        prefix = f"{_normalize_filter_text(alias)} "
        if normalized.startswith(prefix):
            return alias, property_name, prop, clause[len(alias):].strip()
    raise ValueError(f"Campo de filtro não reconhecido: {clause!r}.")


def _parse_filter_value(property_name: str, prop: dict, text: str) -> tuple[str, str | float | bool]:
    property_type = str(prop.get("type") or "")
    if property_type not in _SUPPORTED_FILTER_TYPES:
        raise ValueError(f"O campo {property_name!r} tem tipo {property_type!r}, que não pode ser filtrado.")

    normalized = _normalize_filter_text(text).strip()
    operator = "equals"
    for phrase, notion_operator in _COMPARISON_OPERATORS.items():
        if normalized.startswith(phrase + " "):
            operator = notion_operator
            text = text[len(phrase):].strip()
            break
    if not text:
        raise ValueError(f"Informe um valor para o campo {property_name!r}.")

    if property_type in {"status", "select"}:
        options = ((prop.get(property_type) or {}).get("options") or [])
        matched = next(
            (str(option.get("name")) for option in options if _normalize_filter_text(option.get("name", "")) == _normalize_filter_text(text)),
            None,
        )
        if not matched:
            raise ValueError(f"{property_name}: valor inválido {text!r}.")
        return "equals", matched
    if property_type == "checkbox":
        accepted = {"sim": True, "true": True, "nao": False, "false": False}
        if normalized not in accepted:
            raise ValueError(f"{property_name}: use sim ou não.")
        return "equals", accepted[normalized]
    if property_type in {"number", "date"}:
        if operator == "equals" and normalized in _COMPARISON_OPERATORS:
            raise ValueError(f"Informe um valor para o campo {property_name!r}.")
        if property_type == "number":
            try:
                return operator, float(text.replace(",", "."))
            except ValueError as exc:
                raise ValueError(f"{property_name}: informe um número válido.") from exc
        return operator, text
    if operator != "equals":
        raise ValueError(f"{property_name}: comparações numéricas ou de data não são válidas para texto.")
    return "contains", text


def parse_application_filters(text: str, schema: dict) -> list[dict]:
    clauses = [item.strip() for item in re.split(r"\s+e\s+", str(text or ""), flags=re.IGNORECASE) if item.strip()]
    if not clauses:
        raise ValueError("Informe pelo menos um filtro.")
    filters = []
    for clause in clauses:
        _alias, property_name, prop, value_text = _split_filter_clause(clause, schema)
        operator, value = _parse_filter_value(property_name, prop, value_text)
        filters.append({
            "property_name": property_name,
            "property_type": str(prop.get("type")),
            "operator": operator,
            "value": value,
        })
    return filters


def build_application_filter(filters: list[dict]) -> dict:
    if not filters:
        raise ValueError("Informe pelo menos um filtro.")
    clauses = []
    for item in filters:
        property_type = item["property_type"]
        operator = item["operator"]
        if property_type in _TEXT_TYPES:
            clauses.append({"property": item["property_name"], property_type: {"contains": item["value"]}})
        else:
            clauses.append({"property": item["property_name"], property_type: {operator: item["value"]}})
    return clauses[0] if len(clauses) == 1 else {"and": clauses}


def _display_filters(filters: list[dict]) -> list[str]:
    labels = {
        "greater_than": ">",
        "greater_than_or_equal_to": ">=",
        "less_than": "<",
        "less_than_or_equal_to": "<=",
        "equals": "=",
        "contains": "contém",
    }
    return [f"{item['property_name']} {labels[item['operator']]} {item['value']}" for item in filters]


def application_filter_guidance(schema: dict) -> dict:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    status_property = next((prop for prop in properties.values() if prop.get("type") == "status"), {})
    return {
        "supported_fields": sorted(properties),
        "available_statuses": [str(option.get("name")) for option in ((status_property.get("status") or {}).get("options") or [])],
    }


def live_application_filter_guidance(token: str, database_id: str) -> dict:
    data_source_id = legacy_notion.discover_data_source_id(token, database_id)
    return application_filter_guidance(legacy_notion.retrieve_data_source(token, data_source_id))


def query_live_applications(token: str, database_id: str, filter_text: str, limit: int = 20) -> dict:
    if not str(filter_text or "").strip():
        raise ValueError("Informe pelo menos um filtro. Use Etapa Funil com um dos status disponíveis.")
    data_source_id = legacy_notion.discover_data_source_id(token, database_id)
    schema = legacy_notion.retrieve_data_source(token, data_source_id)
    filters = parse_application_filters(filter_text, schema)
    response = legacy_notion.query_data_source(
        token,
        data_source_id,
        {"page_size": min(max(int(limit), 1), 20), "filter": build_application_filter(filters)},
    )
    records = [_direct_application_record(page) for page in response.get("results", [])]
    return {
        "status": "completed",
        "filters": _display_filters(filters),
        "count": len(records),
        "records": records,
        **application_filter_guidance(schema),
    }


def _table_cell(value: object) -> str:
    text = str(value or "-").replace("|", "\\|").replace("\n", " ").strip()
    return text or "-"


def format_application_table(result: dict) -> str:
    filters = ", ".join(str(item) for item in result.get("filters") or [])
    records = result.get("records") or []
    if not records:
        return f"0 registro(s) para: {filters or '-'}"
    lines = [
        f"{len(records)} registro(s) para: {filters}",
        "",
        "ID | Cargo | Empresa | Etapa Funil | Aderência | Link",
        "--- | --- | --- | --- | --- | ---",
    ]
    for item in records:
        lines.append(" | ".join([
            _table_cell(item.get("record_id")),
            _table_cell(item.get("role")),
            _table_cell(item.get("company")),
            _table_cell(item.get("status")),
            _table_cell(item.get("fit_score")),
            _table_cell(item.get("notion_url")),
        ]))
    return "\n".join(lines)


def build_cache(
    sweep_dir: Path = legacy_notion.DEFAULT_SWEEP_DIR,
    summary_path: Path = legacy_notion.DEFAULT_SWEEP_SUMMARY,
    cache_path: Path = legacy_notion.DEFAULT_SWEEP_CACHE,
    database_id: str | None = None,
) -> dict:
    outputs = legacy_notion.build_sweep_outputs(sweep_dir, summary_path, cache_path, database_id=database_id)
    cache = read_json(cache_path)
    NotionApplicationsCacheSchema(cache).validate()
    return outputs


def refresh_cache(
    token: str,
    database_id: str,
    sweep_dir: Path = legacy_notion.DEFAULT_SWEEP_DIR,
    summary_path: Path = legacy_notion.DEFAULT_SWEEP_SUMMARY,
    cache_path: Path = legacy_notion.DEFAULT_SWEEP_CACHE,
    refresh: str = "missing",
) -> dict:
    report = legacy_notion.sync_applications_sweep(token, database_id, sweep_dir, refresh)
    outputs = legacy_notion.build_sweep_outputs(
        sweep_dir,
        summary_path,
        cache_path,
        remote_pages=report["remote_pages"],
        database_id=database_id,
    )
    cache = read_json(cache_path)
    NotionApplicationsCacheSchema(cache).validate()
    return {"sync": {key: value for key, value in report.items() if key != "remote_pages"}, "outputs": outputs}


def backfill_governance(
    token: str,
    database_id: str,
    *,
    dry_run: bool = False,
    cache_path: Path = legacy_notion.DEFAULT_SWEEP_CACHE,
    sweep_dir: Path = legacy_notion.DEFAULT_SWEEP_DIR,
    report_path: Path = legacy_notion.DEFAULT_GOVERNANCE_BACKFILL_REPORT,
) -> dict:
    return legacy_notion.backfill_governance_fields(
        token,
        database_id,
        cache_path=cache_path,
        sweep_dir=sweep_dir,
        dry_run=dry_run,
        report_path=report_path,
    )


def notion_config() -> tuple[str, str]:
    return legacy_notion.notion_config()


def sanitize_automation_status(status: str) -> str:
    return legacy_notion.sanitize_automation_status(status)


def _extract_property(page: dict, logical_name: str) -> str:
    props = page.get("properties", {})
    for alias in legacy_notion.PROPERTY_ALIASES.get(logical_name, []):
        if alias in props:
            value = legacy_notion.prop_text(props[alias])
            if value:
                return value
    return ""


def _direct_application_record(page: dict) -> dict:
    title = legacy_notion.page_title(page).replace("\u00a0", " ").strip()
    record_id_raw = _extract_property(page, "record_id").strip()
    record_id = None
    if record_id_raw:
        match = re.search(r"(\d+)$", record_id_raw)
        if match:
            record_id = int(match.group(1))
    company = _extract_property(page, "company").strip()
    role = _extract_property(page, "role").strip()
    inferred_company, inferred_role = legacy_notion.infer_company_and_role(title)
    if not company:
        company = inferred_company
    if role == title and inferred_role:
        role = inferred_role
    if not role:
        role = inferred_role or title
    status = _extract_property(page, "status")
    description = _extract_property(page, "description")
    keywords = legacy_notion.split_terms(_extract_property(page, "keywords"))
    gaps = legacy_notion.split_terms(_extract_property(page, "gaps"))
    fit_raw = _extract_property(page, "fit")
    source_url = _extract_property(page, "source_url")
    fit_score = None
    if fit_raw:
        try:
            fit_score = float(fit_raw)
        except ValueError:
            fit_score = None
    search_text = legacy_notion.normalize_search_text(
        title,
        company,
        role,
        status,
        source_url,
        description,
        " ".join(keywords),
        " ".join(gaps),
    )
    return {
        "page_id": page.get("id"),
        "record_id": record_id,
        "title": title,
        "company": company,
        "role": role,
        "status": status,
        "is_archived": bool(page.get("archived") or page.get("in_trash")),
        "application_date": _extract_property(page, "application_date"),
        "fit_score": fit_score,
        "notion_url": page.get("url"),
        "source_url": source_url,
        "keywords": keywords,
        "gaps": gaps,
        "description": description,
        "body_text": "",
        "description_chars": len(description),
        "body_chars": 0,
        "source_file": f"notion:database:{page.get('id')}",
        "search_text": search_text,
    }


def list_database_applications(token: str, database_id: str) -> dict:
    pages = legacy_notion.query_all_database_pages(token, database_id)
    applications = [_direct_application_record(page) for page in pages]
    applications.sort(
        key=lambda item: (
            1 if item.get("is_archived") else 0,
            -(int(item["record_id"]) if isinstance(item.get("record_id"), int) else -1),
            str(item.get("page_id") or ""),
        )
    )
    return {
        "version": 1,
        "generated_at": legacy_notion.datetime.now(legacy_notion.timezone.utc).isoformat(),
        "source": {
            "database_id": database_id,
            "mode": "direct_query",
        },
        "coverage": {
            "remote_total_pages": len(applications),
            "applications_with_description": sum(1 for item in applications if item.get("description_chars", 0) > 0),
        },
        "applications": applications,
    }


def fetch_application_page(token: str, page_id: str) -> dict:
    return legacy_notion.extract_page_payload(token, page_id)


def prepare_analysis_from_record(
    token: str,
    database_id: str,
    record_id: int,
    payload_output_dir: Path,
    description_output_dir: Path,
) -> dict:
    return legacy_notion.prepare_analysis_from_record(
        token,
        database_id,
        record_id,
        payload_output_dir,
        description_output_dir,
    )


def update_status(token: str, database_id: str, page_id: str, status: str, *, dry_run: bool = False) -> dict:
    data_source_id = legacy_notion.discover_data_source_id(token, database_id)
    schema = legacy_notion.retrieve_data_source(token, data_source_id)
    prop_name, prop = legacy_notion.find_prop(schema, "status")
    if not prop_name or not prop:
        raise SystemExit("Could not find a status property in the Notion database.")
    converted = legacy_notion.property_value(prop, status)
    if converted is None:
        raise SystemExit(f"Could not convert status value for Notion property {prop_name!r}.")
    payload = {"properties": {prop_name: converted}}
    if dry_run:
        return {"page_id": page_id, "dry_run": True, "page_update": payload}
    return {"page_id": page_id, "dry_run": False, "page": legacy_notion.update_page(token, page_id, payload)}


def update_from_fit_map_record(
    token: str,
    database_id: str,
    record_id: int,
    fit_map_path: Path,
    job_description_path: Path | None,
    *,
    status: str,
    dry_run: bool = False,
    append_summary: bool = True,
) -> dict:
    return legacy_notion.update_from_fit_map_record(
        token,
        database_id,
        record_id,
        fit_map_path,
        job_description_path=job_description_path,
        dry_run=dry_run,
        append_summary=append_summary,
        allow_mismatch=False,
        status=status,
    )


def perform_cell_sync(client, request: dict) -> dict:
    """Execute one injected Notion write and return a bounded cellular receipt.

    Cellular callers deliberately supply a client.  The legacy module keeps its
    command-line OAuth/token implementation, while this boundary makes cell
    effects testable and prevents a default handler from making a remote write.
    """
    if client is None:
        raise RuntimeError("Notion cell sync requires an injected client")
    if not isinstance(request, dict):
        raise ValueError("Notion cell request must be an object")
    if hasattr(client, "sync_cell"):
        response = client.sync_cell(dict(request))
    elif callable(client):
        response = client(dict(request))
    else:
        raise TypeError("Notion cell client must implement sync_cell(request)")
    if not isinstance(response, dict):
        raise ValueError("Notion cell client returned an invalid response")
    page = response.get("page") if isinstance(response.get("page"), dict) else {}
    page_id = str(response.get("page_id") or response.get("id") or page.get("id") or "")
    url = str(response.get("url") or page.get("url") or "")
    if not page_id or not url:
        raise ValueError("Notion cell response must include page_id and url")
    response_hash = hashlib.sha256(
        json.dumps(response, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return {
        "operation": str(request["operation"]),
        "target": str(request["target"]),
        "request_hash": str(request["request_hash"]),
        "response_hash": response_hash,
        "application_id": str(request["application_id"]),
        "run_id": str(request["run_id"]),
        "node_id": str(request["node_id"]),
        "record_id": str(response.get("record_id") or page_id),
        "page_id": page_id,
        "url": url,
    }


class NotionCellAdapter:
    """Lazy bridge from a cell receipt request to the established Notion sync."""

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        service=None,
        credentials: tuple[str, str] | None = None,
    ) -> None:
        self._env = env
        self._service = service
        self._credentials = credentials

    def preflight(self) -> tuple[str, str]:
        if self._credentials is not None:
            return self._credentials
        if self._env is not None:
            token = str(self._env.get("NOTION_TOKEN") or "").strip()
            database_id = str(self._env.get("NOTION_APPLICATIONS_DATABASE_ID") or "").strip()
            if not token or not database_id:
                raise RuntimeError("Notion cell preflight failed: NOTION_TOKEN and NOTION_APPLICATIONS_DATABASE_ID are required")
            return token, database_id
        try:
            return notion_config()
        except (SystemExit, ValueError) as exc:
            raise RuntimeError(f"Notion cell preflight failed: {exc}") from exc

    def sync_cell(self, request: dict) -> dict:
        token, database_id = self.preflight()
        fit_map_path = Path(str(request.get("fit_map_path") or ""))
        job_description_path = Path(str(request.get("job_description_path") or ""))
        if not fit_map_path.is_file() or not job_description_path.is_file():
            raise RuntimeError("Notion cell preflight requires FIT_MAP and job description artifacts")
        record_id = str(request.get("record_id") or "").strip()
        operation = str(request.get("operation") or "")
        if operation == "notion_final_sync" and not record_id:
            raise RuntimeError("Notion final sync requires an existing record")
        try:
            if self._service is not None and record_id:
                result = self._service.update(
                    token, database_id, int(record_id), fit_map_path, job_description_path,
                    status=str(request["status"]), dry_run=False,
                )
            elif self._service is not None:
                result = self._service.create(
                    token, database_id, fit_map_path, job_description_path,
                    status=str(request["status"]), dry_run=False,
                )
            elif record_id:
                result = update_from_fit_map_record(
                    token, database_id, int(record_id), fit_map_path, job_description_path,
                    status=str(request["status"]), dry_run=False,
                )
            else:
                result = legacy_notion.create_from_fit_map(
                    token, database_id, fit_map_path, job_description_path,
                    status=str(request["status"]), dry_run=False,
                    extra_artifacts=[Path(item) for item in request.get("extra_artifacts", ())],
                )
        except (SystemExit, ValueError) as exc:
            raise RuntimeError(f"Notion cell sync failed: {exc}") from exc
        page = result.get("page") if isinstance(result.get("page"), dict) else {}
        page_id = str(result.get("resolved_page_id") or page.get("id") or "")
        url = str(page.get("url") or "")
        if not page_id or not url:
            raise RuntimeError("Notion cell sync did not return a page ID and URL")
        return {"page_id": page_id, "record_id": str(result.get("resolved_record_id") or record_id or page_id), "url": url}
