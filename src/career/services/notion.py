from __future__ import annotations

import notion_sync as legacy_notion
from pathlib import Path
import re

from career.schemas.notion import NotionApplicationsCacheSchema
from career.utils import read_json


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
