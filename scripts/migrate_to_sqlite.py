#!/usr/bin/env python3
"""Migrate JSON state to SQLite. Run with --dry-run for preview, --cleanup to archive JSONs."""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

CAREER_STATE = Path(__file__).resolve().parent.parent / '.career-state'
LEGADO = CAREER_STATE.parent / 'legado'


def now():
    return datetime.now(timezone.utc).isoformat()


def count_applications():
    apps_dir = CAREER_STATE / 'applications_v2'
    if not apps_dir.exists():
        return 0
    count = 0
    for entry in sorted(apps_dir.iterdir()):
        if (entry / 'state.json').exists():
            count += 1
    return count


def _read_app_data(entry):
    """Read application data from state.json and identity.json in a directory."""
    state_file = entry / 'state.json'
    identity_file = entry / 'identity.json'
    if not state_file.exists():
        return None
    with open(state_file) as f:
        state = json.load(f)
    data = dict(state)
    if identity_file.exists():
        with open(identity_file) as f:
            identity = json.load(f)
        data['company'] = identity.get('company', '')
        data['role'] = identity.get('role', '')
        data['source_type'] = identity.get('source_type', '')
        data['source_url'] = identity.get('source_id', '')
    return data


def migrate_applications(db, dry_run=False):
    apps_dir = CAREER_STATE / 'applications_v2'
    if not apps_dir.exists():
        return 0
    count = 0
    dedup_map = {}
    for entry in sorted(apps_dir.iterdir()):
        if not entry.is_dir():
            continue
        data = _read_app_data(entry)
        if data is None:
            continue
        key = (data.get('company', ''), data.get('role', ''))
        if key in dedup_map:
            existing = dedup_map[key]
            if data.get('created_at', '') > existing.get('created_at', ''):
                dedup_map[key] = data
        else:
            dedup_map[key] = data
    for (company, role), data in dedup_map.items():
        if not dry_run:
            job_path = data.get('job_description_path') or ''
            if job_path and not job_path.startswith('/'):
                job_path = str(CAREER_STATE.parent / job_path)
            db.execute(
                "INSERT OR REPLACE INTO applications "
                "(id, company, role, source_type, source_url, stage, funil_stage, score, status, created_at, updated_at, job_description_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data.get('application_id', f"migrated_{company}_{role}"),
                    company, role,
                    data.get('source_type', ''),
                    data.get('source_url', ''),
                    data.get('stage', 'analyze_pending'),
                    data.get('funil_stage', 'Fila Agente'),
                    data.get('score'),
                    data.get('status', 'active'),
                    data.get('created_at', now()),
                    now(),
                    job_path or None
                )
            )
        count += 1
    return count


def migrate_workflow_events(db, dry_run=False):
    wf_file = CAREER_STATE / 'workflow_state.json'
    if not wf_file.exists():
        return 0
    with open(wf_file) as f:
        data = json.load(f)
    events = data.get('task_history', [])
    active_job_raw = data.get('active_job', 'unknown')
    active_job_id = active_job_raw.get('path', str(active_job_raw)) if isinstance(active_job_raw, dict) else str(active_job_raw)
    # Ensure the application exists (or use a placeholder)
    existing = db.fetch_one("SELECT id FROM applications WHERE id = ?", (active_job_id,))
    if not existing:
        active_job_id = 'migrated_workflow_state'
        existing = db.fetch_one("SELECT id FROM applications WHERE id = ?", (active_job_id,))
        if not existing:
            db.execute(
                "INSERT OR IGNORE INTO applications (id, company, role, stage, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (active_job_id, 'workflow_state', 'workflow_state', 'done', 'archived', now(), now())
            )
    for event in events:
        if not dry_run:
            db.execute(
                "INSERT INTO workflow_events (application_id, event, fingerprint, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    active_job_id,
                    event.get('task', 'unknown'),
                    event.get('output_fingerprint'),
                    json.dumps(event),
                    event.get('finished_at', now())
                )
            )
    return len(events)


def migrate_notion_cache(db, dry_run=False):
    cache_file = CAREER_STATE.parent / 'inbox' / 'notion' / 'applications_cache.json'
    if not cache_file.exists():
        return 0
    with open(cache_file) as f:
        data = json.load(f)
    records = data if isinstance(data, list) else data.get('applications', data.get('results', []))
    for rec in records:
        if not dry_run:
            db.execute(
                "INSERT OR REPLACE INTO notion_cache "
                "(id, raw_json, company, role, funil_stage, status, last_synced) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(rec.get('page_id', rec.get('id', ''))),
                    json.dumps(rec),
                    rec.get('company', ''),
                    rec.get('role', ''),
                    rec.get('status', ''),
                    rec.get('status', ''),
                    now()
                )
            )
    return len(records)


def migrate_keywords(db, dry_run=False):
    kw_file = CAREER_STATE / 'derived' / 'keyword_ats_registry.json'
    if not kw_file.exists():
        return 0
    with open(kw_file) as f:
        data = json.load(f)
    apps = data.get('applications', [])
    count = 0
    for app in apps:
        app_key = app.get('application_key', 'unknown')
        for kw in app.get('keyword_records', []):
            if not dry_run:
                db.execute(
                    "INSERT OR REPLACE INTO keyword_registry (keyword, application_id, coverage, evidence, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (kw.get('keyword', ''), app_key, kw.get('coverage', 'missing'), kw.get('evidence'), now())
                )
            count += 1
    return count


def migrate_session_registry(db, dry_run=False):
    reg_file = CAREER_STATE / 'session_registry.json'
    if not reg_file.exists():
        return 0
    with open(reg_file) as f:
        data = json.load(f)
    if not dry_run:
        for key, value in data.items():
            db.execute(
                "INSERT INTO session_memory (session_id, key, value, created_at, ttl_seconds) "
                "VALUES (?, ?, ?, ?, ?)",
                ('migration', key, json.dumps(value), now(), 86400)
            )
    return len(data)


def cleanup_jsons():
    backup_dir = LEGADO / 'migrated_jsons'
    backup_dir.mkdir(parents=True, exist_ok=True)
    sources = [
        CAREER_STATE / 'workflow_state.json',
        CAREER_STATE / 'session_registry.json',
        CAREER_STATE / 'application_alias_index.json',
        CAREER_STATE / 'derived' / 'keyword_ats_registry.json',
        CAREER_STATE.parent / 'inbox' / 'notion' / 'applications_cache.json',
    ]
    for src in sources:
        if src.exists():
            shutil.move(str(src), str(backup_dir / src.name))
            print(f"  Archived: {src.name}")


def main():
    parser = argparse.ArgumentParser(description='Migrate JSON state to SQLite')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--cleanup', action='store_true', help='Archive migrated JSONs to legado/')
    args = parser.parse_args()

    print(f"Applications: {count_applications()} directories found")

    if args.dry_run:
        print("--- DRY RUN ---")
        print(f"Applications to migrate: {count_applications()} (deduplicated)")
        print(f"Workflow events: will read from workflow_state.json")
        print(f"Notion cache: 7MB file, ~{os.path.getsize(CAREER_STATE.parent / 'inbox' / 'notion' / 'applications_cache.json') // 1000}KB")
        print(f"Keywords: will read from keyword_ats_registry.json")
        print(f"Session registry: will read from session_registry.json")
        print("--- DRY RUN complete ---")
        return

    from career.services.database import Database
    db = Database()
    db.init_schema()

    print("Migrating applications...")
    app_count = migrate_applications(db)
    print(f"  {app_count} applications migrated (deduplicated)")

    print("Migrating workflow events...")
    event_count = migrate_workflow_events(db)
    print(f"  {event_count} workflow events migrated")

    print("Migrating notion cache...")
    notion_count = migrate_notion_cache(db)
    print(f"  {notion_count} notion cache records migrated")

    print("Migrating keywords...")
    kw_count = migrate_keywords(db)
    print(f"  {kw_count} keyword records migrated")

    print("Migrating session registry...")
    sess_count = migrate_session_registry(db)
    print(f"  {sess_count} session registry records migrated")

    print("Migration complete!")

    if args.cleanup:
        print("Archiving migrated JSONs...")
        cleanup_jsons()
        print("Cleanup complete!")


if __name__ == '__main__':
    main()