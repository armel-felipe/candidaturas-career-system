# Cellular Application Orchestration Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace global, conversation-dependent application execution with application-scoped cellular runs that can safely process two vacancies in parallel in one authoritative workspace.

**Architecture:** Extend the existing SQLite database at .career-state/career.db into the transactional control plane for application runs, graph nodes, attempts, artifacts and locks. Keep application files as the audit/data plane: each planned node has an immutable manifest, compact handover and staging directory under .career-state/applications_v2/<application_id>/cells/. A graph compiler creates the DAG before execution; an executor reserves only ready nodes, applies capability allowlists, supports local repair attempts and publishes outputs atomically.

**Tech Stack:** Python 3 standard library (sqlite3, dataclasses, hashlib, pathlib, json), existing career_cli.py, existing FIT_MAP/CV/Notion services, pytest, Node DOCX renderer.

## Global Constraints

- A single workspace is authoritative and runs on one machine at a time; do not support concurrent execution across synced Mac/RPi5 copies.
- Every new cellular command requires --application-id; no fallback to global FIT_MAP, CV content, workflow state or derived context is allowed.
- SQLite stores identifiers, paths, hashes, versions, statuses and receipts—not job descriptions, FIT_MAP payloads, CV text or DOCX bytes.
- Every node writes only to its staging directory until its validators pass; approved files are published atomically as immutable revisions.
- Candidate facts remain read-only during application runs and all CV factual claims retain provenance references.
- Workspace locks are limited to LinkedIn session, Notion writes, delivery destination, Git sync and candidate-facts maintenance; application locks do not block other applications.
- Preserve legacy commands as explicit compatibility paths until the migration task removes their global fallback from cellular runs.

---

### Task 1: Make SQLite a safe cellular control plane

**Files:**
- Modify: src/career/services/database.py
- Create: src/career/services/cell_store.py
- Modify: tests/test_database.py
- Create: tests/test_cell_store.py

**Interfaces:**
- Produces Database.transaction(immediate: bool = False).
- Produces CellStore.create_run, reserve_node, finish_attempt, acquire_resource_lock, release_resource_lock, and list_ready_nodes.
- Later tasks consume statuses planned, reserved, running, repairing, validated, blocked, superseded, and cancelled.

- [ ] **Step 1: Write the failing schema and lock tests**

~~~python
def test_reserve_node_allows_distinct_applications(db):
    store = CellStore(db)
    store.create_run("app-a", "run-a", graph={"nodes": ["fit"]})
    store.create_run("app-b", "run-b", graph={"nodes": ["fit"]})
    assert store.reserve_node("run-a", "fit", "worker-a")["status"] == "reserved"
    assert store.reserve_node("run-b", "fit", "worker-b")["status"] == "reserved"

def test_resource_lock_is_exclusive(db):
    store = CellStore(db)
    assert store.acquire_resource_lock("notion-write", "worker-a")["acquired"] is True
    assert store.acquire_resource_lock("notion-write", "worker-b")["acquired"] is False
~~~

- [ ] **Step 2: Run the tests to confirm the APIs do not exist**

Run: pytest tests/test_cell_store.py -q

Expected: FAIL with ModuleNotFoundError or missing CellStore.

- [ ] **Step 3: Add additive, idempotent schema migration and transaction support**

Add these tables in Database.init_schema() without modifying legacy tables: application_runs, cell_nodes, cell_attempts, artifacts, resource_locks, workspace_leases and artifact_dependencies. Add indices on (run_id, status), (application_id, created_at), (resource_name, expires_at) and (artifact_id, input_hash).

Implement this transaction API so reservation uses BEGIN IMMEDIATE, checks the existing node status, inserts one attempt and commits before agent work begins:

~~~python
@contextmanager
def transaction(self, *, immediate: bool = False):
    conn = self.get_connection()
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
~~~

CellStore.reserve_node() must use one immediate transaction and return {"status": "busy"} rather than raising when the node is already reserved by a live worker.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_database.py tests/test_cell_store.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/services/database.py src/career/services/cell_store.py tests/test_database.py tests/test_cell_store.py
git commit -m "feat: add transactional cellular run store"
~~~

### Task 2: Define versioned cell contracts and compile an immutable DAG

**Files:**
- Create: src/career/cells/__init__.py
- Create: src/career/cells/contracts.py
- Create: src/career/cells/planner.py
- Modify: src/career/services/application_context.py
- Create: tests/test_cell_planner.py

**Interfaces:**
- Produces CellContract, NodePlan, RunPlan, CELL_CONTRACTS, and compile_run_plan(application_id, requested_deliverables, application_paths).
- RunPlan has run_id, application_id, nodes, edges, resource_locks, created_at, and contract_version.
- Node IDs are capture_source, normalize_job, analyze_fit, compose_cv, render_cv, review_cv, deliver_cv, sync_notion_initial, sync_notion_final, generate_feras, review_feras, generate_cover_letter, review_cover_letter, generate_habilidades, and review_habilidades.

- [ ] **Step 1: Write failing graph tests**

~~~python
def test_cv_and_notion_plan_has_ordered_nodes(tmp_path):
    plan = compile_run_plan("app-1", {"cv", "notion"}, paths_for("app-1", root=tmp_path))
    assert plan.dependencies_of("compose_cv") == ("analyze_fit",)
    assert plan.dependencies_of("review_cv") == ("render_cv",)
    assert plan.dependencies_of("sync_notion_final") == ("review_cv",)
    assert plan.is_acyclic()

def test_independent_output_branches_are_ready_after_fit(tmp_path):
    plan = compile_run_plan("app-1", {"cv", "feras"}, paths_for("app-1", root=tmp_path))
    assert {"compose_cv", "generate_feras"} <= set(plan.ready_after({"analyze_fit"}))
~~~

- [ ] **Step 2: Run the tests to confirm the compiler is missing**

Run: pytest tests/test_cell_planner.py -q

Expected: FAIL with missing career.cells module.

- [ ] **Step 3: Implement declarative contracts and compiler**

Use frozen dataclasses. Each contract defines requires, produces, validators, resources, invalidates, repair_scope, max_attempts, and allows_external_effect. The compiler rejects unknown deliverables, missing contracts, duplicate node IDs, output-path collisions and cycles before persisting a plan. It includes capture_source only when no job description exists.

Extend paths_for(application_id, root: Path | None = None) so the planner tests can construct application-local paths below tmp_path without altering the workspace. The default remains the current applications directory.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_planner.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/cells src/career/services/application_context.py tests/test_cell_planner.py
git commit -m "feat: compile application cell graphs"
~~~

### Task 3: Persist manifests, handovers and staged publications

**Files:**
- Modify: src/career/services/application_context.py
- Create: src/career/cells/manifests.py
- Create: src/career/cells/capabilities.py
- Create: tests/test_cell_manifests.py

**Interfaces:**
- Extend ApplicationPaths with plans_dir, cells_dir, artifacts_dir, reviews_dir, and run_completion_manifest.
- Produces ManifestStore.begin_attempt, write_handover, publish_file, finish_run.
- Produces CapabilitySet.assert_readable(path) and assert_writable(path).

- [ ] **Step 1: Write failing provenance and staging tests**

~~~python
def test_publish_records_input_hash_and_keeps_previous_revision(tmp_path):
    store = ManifestStore(paths_for("app-1", root=tmp_path))
    first = store.publish_file("compose_cv", 1, "cv_content", b'{"version": 1}', inputs={"fit_map": "a"})
    second = store.publish_file("compose_cv", 2, "cv_content", b'{"version": 2}', inputs={"fit_map": "b"})
    assert first.path != second.path
    assert second.manifest["inputs"]["fit_map"]["sha256"] == "b"

def test_capability_rejects_other_application_path(tmp_path):
    caps = CapabilitySet(read_paths=[tmp_path / "app-a"], write_paths=[tmp_path / "app-a" / "staging"])
    with pytest.raises(CapabilityViolation):
        caps.assert_writable(tmp_path / "app-b" / "state.json")
~~~

- [ ] **Step 2: Run tests to confirm behavior is absent**

Run: pytest tests/test_cell_manifests.py -q

Expected: FAIL with missing manifest classes.

- [ ] **Step 3: Implement path-safe manifests and atomic publication**

Resolve every allowed and target path with Path.resolve(); reject paths outside the application directory. Write attempt data to cells/<node_id>/<attempt>/staging/; publish a successful revision through os.replace() into artifacts/<artifact_name>/<sha256-prefix>/. Store each input as {path, sha256, revision, source_kind} and each validator as {command, result, report_path, executed_at}.

finish_run() writes run_completion_manifest.json from validated artifacts and blocked nodes only; it does not infer completion from file existence.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_manifests.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/services/application_context.py src/career/cells/manifests.py src/career/cells/capabilities.py tests/test_cell_manifests.py
git commit -m "feat: add immutable cell manifests and staging"
~~~

### Task 4: Execute ready nodes, local repairs and resumptions

**Files:**
- Create: src/career/cells/executor.py
- Create: src/career/cells/handlers.py
- Create: tests/test_cell_executor.py

**Interfaces:**
- Produces CellExecutor.plan, run_ready, repair, resume, and finalize.
- Handler signature: def handler(context: CellExecutionContext) -> CellOutput.
- repair(run_id, node_id, reason) creates a new attempt and invalidates only contract descendants.

- [ ] **Step 1: Write failing execution tests**

~~~python
def test_failed_render_repair_does_not_rerun_fit_map(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv"}).run_id
    orchestrator.mark_validated(run_id, "analyze_fit")
    orchestrator.fail(run_id, "render_cv", "docx_layout")
    repaired = orchestrator.repair(run_id, "render_cv", "docx_layout")
    assert repaired.attempt == 2
    assert orchestrator.node_status(run_id, "analyze_fit") == "validated"

def test_executor_never_runs_child_before_parent(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv"}).run_id
    assert "render_cv" not in orchestrator.ready_nodes(run_id)
~~~

- [ ] **Step 2: Run the tests to verify failure**

Run: pytest tests/test_cell_executor.py -q

Expected: FAIL with missing executor.

- [ ] **Step 3: Implement deterministic executor**

The executor reserves nodes through CellStore, materializes CellExecutionContext from the manifest allowlist, invokes exactly one handler, runs every contract validator, then either publishes and marks validated or keeps staging, writes the blocker and marks blocked. It reserves workspace resources only for contracts that request them and never runs a handler after a dependency failure.

Repair starts at the contract repair_scope, creates a new attempt under the same run_id, preserves the prior attempt, and marks only declared descendants superseded. resume uses database plus manifests, never conversation state.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_executor.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/cells/executor.py src/career/cells/handlers.py tests/test_cell_executor.py
git commit -m "feat: execute and repair cellular application nodes"
~~~

### Task 5: Add application-scoped CLI plan, run and inspection commands

**Files:**
- Modify: src/career/cli.py
- Modify: package.json
- Create: tests/test_cell_cli.py

**Interfaces:**
- New commands: career applications plan --application-id ID --deliverable cv --deliverable notion; career applications run --application-id ID --run-id RUN; career applications repair --application-id ID --run-id RUN --node NODE --reason TEXT; career applications inspect-run --application-id ID --run-id RUN.
- New npm aliases: applications:plan, applications:run, applications:repair, applications:inspect-run.

- [ ] **Step 1: Write CLI parser and output tests**

~~~python
def test_plan_requires_application_id_and_emits_run_id(capsys, seeded_application):
    code = main(["applications", "plan", "--application-id", seeded_application, "--deliverable", "cv"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["run_id"]

def test_cellular_run_rejects_missing_application_id():
    with pytest.raises(SystemExit, match="application-id"):
        main(["applications", "run", "--run-id", "run-1"])
~~~

- [ ] **Step 2: Run tests to verify failure**

Run: pytest tests/test_cell_cli.py -q

Expected: FAIL because the commands do not exist.

- [ ] **Step 3: Implement CLI adapters without implicit global paths**

Add subparsers under applications. Output only status, run ID, ready/blocked nodes, artifact paths and next action. Do not add a cellular CLI that accepts raw global FIT_MAP/CV paths.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_cli.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/cli.py package.json tests/test_cell_cli.py
git commit -m "feat: expose cellular run commands"
~~~

### Task 6: Migrate intake, context and FIT_MAP into cells

**Files:**
- Modify: src/career/services/intake.py
- Modify: src/career/services/derived_context.py
- Modify: src/career/services/fit_map.py
- Modify: src/career/services/cv_content.py
- Modify: src/career/cells/handlers.py
- Create: src/career/services/provenance.py
- Create: tests/test_cell_intake.py
- Create: tests/test_fit_map_provenance.py

**Interfaces:**
- capture_source persists job_description.md and source metadata under the application directory.
- normalize_job builds packs in that application's derived/ directory and publishes handover_summary.json plus evidence_index.json.
- analyze_fit validates and publishes an app-specific FIT_MAP with job fingerprint and candidate-facts revision.

- [ ] **Step 1: Write failing cross-application and invalidation tests**

~~~python
def test_normalization_keeps_fingerprints_per_application(two_applications):
    first, second = two_applications
    normalize_job(first)
    normalize_job(second)
    assert read_json(first.derived_dir / "manifest.json")["fingerprint"] != read_json(second.derived_dir / "manifest.json")["fingerprint"]

def test_new_fit_map_revision_invalidates_cv_descendants(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv", "feras"}).run_id
    orchestrator.mark_validated(run_id, "compose_cv")
    orchestrator.publish_new_fit_map(run_id, input_hash="changed")
    assert orchestrator.node_status(run_id, "compose_cv") == "superseded"
~~~

- [ ] **Step 2: Run the tests to reproduce current global-path risk**

Run: pytest tests/test_cell_intake.py tests/test_fit_map_provenance.py -q

Expected: FAIL until all helper paths are explicit.

- [ ] **Step 3: Implement explicit application paths and lineage**

Refactor cellular public builders in derived_context.py and cv_content.py to accept immutable ApplicationPaths or explicit paths; cellular handlers never call configure_derived_dir, configure_state_store_path or configure_paths. Keep them only as deprecated legacy adapters.

Add FIT_MAP provenance {job_fingerprint, candidate_facts_revision, draft_sha256, contract_version, produced_by_attempt}. Reject mismatched fingerprints. On changed FIT_MAP hash, invalidate only contract descendants.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_intake.py tests/test_fit_map_provenance.py tests/test_packs.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/services/intake.py src/career/services/derived_context.py src/career/services/fit_map.py src/career/services/cv_content.py src/career/services/provenance.py src/career/cells/handlers.py tests/test_cell_intake.py tests/test_fit_map_provenance.py
git commit -m "feat: scope intake and FIT_MAP to cells"
~~~

### Task 7: Move CV composition, rendering and review to explicit cell inputs

**Files:**
- Modify: src/career/services/cv_content.py
- Modify: scripts/docx/generate_custom_cv.js
- Modify: src/career/cells/handlers.py
- Modify: src/career/services/review.py
- Create: tests/test_cell_cv_pipeline.py
- Modify: tests/test_custom_cv_generation.py

**Interfaces:**
- build_cv_content(application_paths, fit_map_path, candidate_facts_revision) -> dict.
- render_cv(content_path, output_dir, application_id) -> Path.
- review_cv writes reports under applications_v2/<id>/reviews/ and produces an approved artifact manifest.

- [ ] **Step 1: Write failing two-CV concurrency test**

~~~python
def test_two_cv_cells_do_not_share_language_or_period(two_cell_runs):
    first, second = two_cell_runs
    first_result = first.execute_until("review_cv")
    second_result = second.execute_until("review_cv")
    assert first_result.artifact_path != second_result.artifact_path
    assert first_result.manifest["application_id"] != second_result.manifest["application_id"]
    assert first_result.manifest["inputs"]["fit_map"]["sha256"] != second_result.manifest["inputs"]["fit_map"]["sha256"]
~~~

- [ ] **Step 2: Run tests to reproduce the global-path risk**

Run: pytest tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -q

Expected: FAIL until renderer and review paths are explicit.

- [ ] **Step 3: Implement app-scoped CV handlers**

compose_cv publishes versioned cv_content.json with experience_id and evidence_id references. render_cv uses that exact revision and writes an application-scoped filename. review_cv runs existing objective gates against that artifact and records report hashes in its manifest.

Do not encode role/date values in the renderer. Add provenance validation against the canonical candidate-facts revision while allowing locale aliases, experience selection and job-specific wording.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/services/cv_content.py scripts/docx/generate_custom_cv.js src/career/cells/handlers.py src/career/services/review.py tests/test_cell_cv_pipeline.py tests/test_custom_cv_generation.py
git commit -m "feat: run CV pipeline as scoped cells"
~~~

### Task 8: Add receipt-based Notion, delivery and remaining output branches

**Files:**
- Modify: src/career/services/notion.py
- Modify: scripts/notion_sync.py
- Modify: src/career/services/feras.py
- Modify: src/career/services/cover_letter.py
- Modify: src/career/services/habilidades_chave.py
- Modify: src/career/cells/contracts.py
- Modify: src/career/cells/handlers.py
- Create: tests/test_cell_notion_delivery.py
- Create: tests/test_cell_deliverable_branches.py

**Interfaces:**
- sync_notion_initial and sync_notion_final require notion-write and publish record/page ID, URL, operation, request hash and response hash.
- deliver_cv requires delivery:<canonical-target> and publishes artifact-hash delivery receipts.
- FERAS, carta and skills consume FIT_MAP plus normalized packs and are independent of the CV branch.

- [ ] **Step 1: Write failing receipt and branch tests**

~~~python
def test_repeated_notion_final_sync_reuses_matching_receipt(fake_notion, cell_run):
    first = sync_notion_final(cell_run, fake_notion)
    second = sync_notion_final(cell_run, fake_notion)
    assert first.receipt["request_hash"] == second.receipt["request_hash"]
    assert fake_notion.mutation_count == 1

def test_feras_can_complete_when_cv_is_blocked(orchestrator):
    run_id = orchestrator.plan("app-1", {"cv", "feras"}).run_id
    orchestrator.mark_validated(run_id, "analyze_fit")
    orchestrator.fail(run_id, "compose_cv", "ats_blocker")
    assert "generate_feras" in orchestrator.ready_nodes(run_id)
~~~

- [ ] **Step 2: Run tests to verify failure**

Run: pytest tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py -q

Expected: FAIL with missing receipt and branch behavior.

- [ ] **Step 3: Implement receipt-first effects and branch handlers**

Calculate remote request hashes from application ID, node ID, artifact hashes and target status. Reuse matching validated receipts before mutating Notion or delivery. Otherwise acquire the resource lock, mutate, persist receipt, then release. Do not pass DOCX files to the current text-only Notion extra-artifact reader.

For successful output nodes, write compact handovers and evidence indexes. Branch handlers reject pointers from another application.

- [ ] **Step 4: Run focused tests**

Run: pytest tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add src/career/services/notion.py scripts/notion_sync.py src/career/services/feras.py src/career/services/cover_letter.py src/career/services/habilidades_chave.py src/career/cells/contracts.py src/career/cells/handlers.py tests/test_cell_notion_delivery.py tests/test_cell_deliverable_branches.py
git commit -m "feat: add cellular output and receipt branches"
~~~

### Task 9: Enforce workspace ownership, migrate legacy state and verify real parallel execution

**Files:**
- Modify: src/career/services/application_context.py
- Modify: src/career/services/multiagent.py
- Modify: src/career/services/harness_supervisor.py
- Modify: src/career/services/applications_v2.py
- Create: scripts/migrate_cellular_runs.py
- Create: tests/test_cell_workspace_safety.py
- Create: tests/test_cell_migration.py
- Create: tests/test_cell_parallel_integration.py
- Modify: AGENTS.md
- Modify: .agents/skills/career-system/SKILL.md

**Interfaces:**
- Produces WorkspaceLease.acquire(owner, ttl_seconds), heartbeat(owner), release(owner).
- New commands: career applications migrate-cellular --application-id ID --dry-run and career applications verify-parallel --fixture-dir PATH.
- applications:agent-heartbeat schedules cellular nodes and no longer configures mutable module globals for cellular runs.

- [ ] **Step 1: Write failing workspace, migration and subprocess tests**

~~~python
def test_second_workspace_owner_is_blocked(db):
    lease = WorkspaceLease(db)
    assert lease.acquire("rpi5") is True
    assert lease.acquire("macbook") is False

def test_migration_never_marks_unreviewed_cv_as_validated(tmp_path):
    result = migrate_application(tmp_path / "legacy-app", application_id="app-1", dry_run=False)
    assert result["imported_nodes"]["review_cv"] == "blocked"

def test_two_processes_complete_separate_normalization_cells(tmp_path):
    results = run_parallel_fixture_workers(tmp_path, applications=("app-a", "app-b"))
    assert {item["status"] for item in results} == {"validated"}
    assert results[0]["job_fingerprint"] != results[1]["job_fingerprint"]
~~~

- [ ] **Step 2: Run tests to verify failure**

Run: pytest tests/test_cell_workspace_safety.py tests/test_cell_migration.py tests/test_cell_parallel_integration.py -q

Expected: FAIL until enforcement and harness exist.

- [ ] **Step 3: Implement enforcement, migration and regression harness**

The workspace lease is acquired before a cellular worker starts and renewed during execution. An expired lease can be taken only after recording prior owner and expiry. Multiagent requests include run ID, node ID, manifest path, explicit allowlists and application ID. Legacy commands can retain global paths only when not marked cellular; cellular requests fail rather than downgrade.

The migration script creates imported manifests from existing files and marks unknown validations blocked; it never fabricates success or rewrites artifacts. The parallel verification command starts two subprocesses against one temporary workspace/database and asserts no cross-application paths, fingerprints, manifests or artifacts.

- [ ] **Step 4: Update operational rules**

Document the one-workspace rule, Mac/RPi5 lease handoff, cell commands, local repair, context handover and global-fallback prohibition in AGENTS.md and the canonical career-system skill.

- [ ] **Step 5: Run full validation**

Run: pytest -q && ./scripts/python.sh scripts/career_cli.py project validate-structure && npm run runtime:diagnose

Expected: all pytest tests pass; project structure validation and runtime diagnosis return success.

- [ ] **Step 6: Commit**

~~~bash
git add src/career/services/application_context.py src/career/services/multiagent.py src/career/services/harness_supervisor.py src/career/services/applications_v2.py scripts/migrate_cellular_runs.py tests/test_cell_workspace_safety.py tests/test_cell_migration.py tests/test_cell_parallel_integration.py AGENTS.md .agents/skills/career-system/SKILL.md
git commit -m "feat: verify and document cellular orchestration"
~~~

## Plan Self-Review

- Spec coverage: Tasks 1–5 establish transactional orchestration, graph compilation, manifests, repairs and CLI. Tasks 6–8 migrate every output branch and provenance. Task 9 enforces the single-workspace rule, compatibility migration and actual two-process regression testing.
- Placeholder scan: all tasks specify files, interfaces, failing tests, expected commands and commits.
- Consistency: cellular execution always carries application_id, run_id and node_id; SQLite coordinates control state while manifests preserve immutable data-plane provenance.
