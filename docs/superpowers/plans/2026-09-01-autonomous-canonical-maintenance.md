# Autonomous Canonical Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o HarnessSupervisor receber pedidos de manutenção dos dois bots, validá-los, executar a correção em worktree isolado, submetê-la a gates e revisão independente com score mínimo de 99/100, commitá-la e retomar o run original.

**Architecture:** O pedido versionado será persistido no estado do projeto e validado contra o acervo canônico versionado, as exclusões de segurança e a allowlist exata do pedido. Um orquestrador próprio criará um worktree temporário para o agente de manutenção, coletará o diff e executará os testes; um segundo processo receberá somente spec, diff e evidências para revisar. Somente a combinação de hard gates aprovados, score do revisor `>=99/100` e base de checkout ainda válida poderá aplicar o patch e gerar o commit.

**Tech Stack:** Python 3, `pathlib`, `subprocess`, Git worktrees, pytest, HarnessSupervisor existente, `SubprocessAgentRunner`, JSON receipts e Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-01-autonomous-canonical-maintenance-design.md`

## Global Constraints

- Manter o mount de código dos bots read-only; nenhum processo Hermes de `vagas_bot_01` ou `vagas_bot_02` escreve no checkout canônico.
- Alterações podem atingir arquivos versionados do acervo canônico do projeto,
  incluindo código, skills existentes, referências, testes, documentação e
  configurações, desde que cada caminho esteja explicitamente em
  `allowed_paths`.
- Nunca alterar `outputs/`, `.career-state/`, `control-plane/`, SQLite ou artefatos selados para contornar gates.
- Nunca criar uma nova skill, uma nova pasta de skill ou um namespace canônico inexistente.
- Nunca alterar `.env`, tokens, chaves privadas, caches, dumps ou artefatos gerados não versionados.
- O pedido celular preserva `application_id` e `run_id` e nunca cria uma candidatura nova durante a retomada.
- O score de 99% é conformidade verificável; confiança textual do modelo não substitui hard gates.
- O limite de retry é três tentativas idempotentes por `request_id`.
- Operações externas em Notion, Gmail e OneDrive continuam usando seus próprios workflows e aprovações.
- Cada tarefa termina com teste executável e commit isolado antes da próxima tarefa.

## Método operacional reutilizável

Quando um plano ou pedido indicar `método de resolução: Loop Gauntlet`, o
orquestrador deve executar o ciclo de executor e revisor independente, usando a
crítica estruturada para alimentar novas tentativas do executor até a aprovação
de `>=99/100` ou o bloqueio após três tentativas. Esse é um método reutilizável
de execução e revisão; não é o nome deste plano nem de uma feature do sistema.

---

## Mapa de arquivos e responsabilidades

- Modify: `src/career/services/maintenance.py` — contrato versionado, validação de spec/evidência, fingerprint e compatibilidade com `maintenance:request`/`maintenance:apply`.
- Create: `src/career/services/maintenance_orchestrator.py` — worktree, tentativas, execução dos dois agentes, gates, aplicação, commit e receipt.
- Modify: `src/career/services/agent_runner.py` — permitir que o runner receba um workspace temporário e um perfil explícito sem alterar o comportamento dos especialistas existentes.
- Modify: `src/career/services/harness_supervisor.py` — reconhecer pedidos de manutenção estruturados e encaminhá-los ao orquestrador; preservar a classificação de relatórios e pipelines atuais.
- Modify: `src/career/cli.py` — adicionar `maintenance process` para execução pelo supervisor/worker e manter os subcomandos existentes.
- Create: `tests/test_maintenance_orchestrator.py` — contrato, isolamento, política do acervo, retry, revisão e commit usando repositórios Git temporários.
- Modify: `tests/test_canonical_maintenance.py` — compatibilidade, fingerprints e novas regras de request.
- Modify: `tests/test_harness_dispatch.py` — roteamento do pedido vindo de cada perfil e ausência de falsa classificação como vaga colada.
- Modify: `compose.yaml` — somente se o worker precisar de um serviço dedicado; o primeiro release usará o host do Harness, sem conceder escrita aos dois serviços Hermes.
- Modify: `docs/roadmap.md` — marcar `MAINT-002` somente após evidência de testes e canário dos dois bots.

## Interfaces entre tarefas

O contrato público do novo orquestrador será:

```python
class MaintenanceOrchestrator:
    def process(
        self,
        request_path: Path,
        *,
        max_attempts: int = 3,
        maintenance_config: dict[str, Any] | None = None,
        reviewer_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process one validated maintenance request."""
```

O retorno sempre terá `status`, `request_id`, `attempts`, `review`, `checks`,
`receipt_path` e `blocker_reason` quando não houver `status == "resumed"`.

O contrato do revisor será JSON e terá exatamente estes campos obrigatórios:

```json
{
  "status": "approved|rejected",
  "score": 99.0,
  "requirements": [{"id": "REQ-1", "status": "met", "evidence": "tests/test_maintenance_orchestrator.py::test_review"}],
  "blockers": [],
  "warnings": [],
  "reviewer_model": "maintenance-reviewer",
  "diff_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "spec_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
}
```

O relatório só será aceito quando `score >= 99.0`, todos os requisitos
obrigatórios estiverem `met`, `blockers` estiver vazio e os hashes conferirem.

### Task 1: Versionar e validar o pedido de manutenção

**Files:**
- Modify: `src/career/services/maintenance.py:13-53`
- Test: `tests/test_canonical_maintenance.py`

**Interfaces:**
- Produces `MAINTENANCE_REQUEST_VERSION = 2`.
- Produces `validate_maintenance_paths(root, allowed_paths) -> dict[str, Any]`, rejeitando exclusões, symlinks que escapem do repositório e criação de novas skills.
- Extends `create_maintenance_request(root, *, objective, allowed_paths, spec=None, evidence=None, requester_profile="", application_id=None, run_id=None, roadmap_id="MAINT-002", base_commit=None)` without breaking callers that pass only the current arguments.
- Produces `validate_maintenance_request(root, request_path) -> dict[str, Any]` and `maintenance_request_fingerprint(payload) -> str`.

- [ ] **Step 1: Write failing tests for the versioned contract.**

```python
def test_request_contains_spec_evidence_scope_and_fingerprint(tmp_path):
    request = create_maintenance_request(
        tmp_path,
        objective="Corrigir seletor canônico",
        allowed_paths=["src/career/services/cv_content.py"],
        spec={"requirements": [{"id": "REQ-1", "text": "Cobrir lacunas >36 meses"}]},
        evidence={"error": "seleção parava em seis experiências"},
        requester_profile="vagas_bot_01",
        application_id="app_demo",
        run_id="run_demo",
    )
    assert request["schema_version"] == 2
    assert request["application_id"] == "app_demo"
    assert request["spec"]["requirements"][0]["id"] == "REQ-1"
    assert len(request["request_fingerprint"]) == 64
    assert validate_maintenance_request(tmp_path, Path(request["request_path"]))["status"] == "ok"

def test_request_rejects_missing_requirement_spec(tmp_path):
    request = create_maintenance_request(
        tmp_path, objective="Sem spec", allowed_paths=["src/x.py"]
    )
    with pytest.raises(ValueError, match="spec"):
        validate_maintenance_request(tmp_path, Path(request["request_path"]))
```

- [ ] **Step 2: Run the focused tests and confirm the new contract fails.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_canonical_maintenance.py -k 'versioned or missing_requirement'`

Expected: FAIL because the current request has no schema version, spec, evidence or fingerprint.

- [ ] **Step 3: Implement the minimal versioned payload and validation.**

Canonicalize the JSON used for the fingerprint with sorted keys and compact
separators. Preserve the existing path normalization and reject absolute paths,
`..`, empty objectives, missing requirements, missing evidence, unknown schema
versions and an `application_id`/`run_id` pair with only one member.

Implement `validate_maintenance_paths` using the commit-base Git index and the
following deterministic rules: normalize every path as a repository-relative
POSIX path; require each path to be explicitly listed in `allowed_paths`; reject
`.career-state/`, `outputs/`, `control-plane/`, SQLite, `.env*`, credentials,
caches, dumps and sealed artifacts; reject a resolved path outside the repository;
allow a new file only when its parent directory already exists in the base
checkout; and allow files below `.agents/skills/<name>/` only when that skill
directory already exists in the base checkout. Return the normalized paths and
the precise blocker for every rejection.

Add these regression cases to `tests/test_canonical_maintenance.py`:

```python
def test_existing_canonical_skill_file_is_allowed(tmp_path):
    root = make_git_fixture(tmp_path, files={".agents/skills/demo/SKILL.md": "base\n"})
    result = validate_maintenance_paths(root, [".agents/skills/demo/SKILL.md"])
    assert result["status"] == "ok"

def test_new_skill_directory_is_rejected(tmp_path):
    root = make_git_fixture(tmp_path)
    result = validate_maintenance_paths(root, [".agents/skills/new-skill/SKILL.md"])
    assert result["status"] == "blocked"
    assert result["blocker"] == "new_skill_forbidden"

def test_generated_state_is_rejected_even_when_versioned_scope_is_requested(tmp_path):
    root = make_git_fixture(tmp_path)
    result = validate_maintenance_paths(root, [".career-state/applications_v2/demo/fit_map.json"])
    assert result["status"] == "blocked"
    assert result["blocker"] == "generated_state_forbidden"
```

- [ ] **Step 4: Run compatibility and focused tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_canonical_maintenance.py`

Expected: PASS, including the existing dry-run, apply and outside-allowlist tests.

- [ ] **Step 5: Commit the contract.**

```bash
git add src/career/services/maintenance.py tests/test_canonical_maintenance.py
git commit -m "feat: versiona pedidos de manutencao canonica"
```

### Task 2: Criar execução isolada do agente de manutenção

**Files:**
- Create: `src/career/services/maintenance_orchestrator.py`
- Modify: `src/career/services/agent_runner.py:12-114`
- Test: `tests/test_maintenance_orchestrator.py`

**Interfaces:**
- Produces `MaintenanceOrchestrator._create_worktree(base_commit) -> Path`.
- Produces `MaintenanceOrchestrator._run_maintenance_agent(worktree, request) -> dict[str, Any]`.
- Produces `MaintenanceOrchestrator._collect_candidate(worktree, base_commit, allowed_paths) -> dict[str, Any]`.
- Extends `AgentRunRequest` with `workspace_root: Path | None = None` only if needed; existing requests continue using `SubprocessAgentRunner.root`.

- [ ] **Step 1: Write failing isolation tests.**

```python
def test_maintenance_agent_writes_only_inside_temporary_worktree(tmp_path):
    root = make_git_fixture(tmp_path)
    request = make_valid_request(root, allowed_paths=["src/career/services/cv_content.py"])
    result = FakeMaintenanceRunner().run_in_worktree(root, request)
    assert result["status"] == "candidate_ready"
    assert result["worktree"] != str(root)
    assert (root / "src/career/services/cv_content.py").read_text() == "BASE\n"
    assert result["changed_files"] == ["src/career/services/cv_content.py"]

def test_candidate_rejects_new_file_outside_allowlist(tmp_path):
    root = make_git_fixture(tmp_path)
    request = make_valid_request(root, allowed_paths=["src/career/services/cv_content.py"])
    result = FakeMaintenanceRunner(extra_file="outputs/forbidden.txt").run_in_worktree(root, request)
    assert result["status"] == "rejected"
    assert "outputs/forbidden.txt" in result["blocker_reason"]
```

- [ ] **Step 2: Run the tests and verify failure.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'worktree or allowlist'`

Expected: FAIL because `MaintenanceOrchestrator` and the fixture runner do not exist.

- [ ] **Step 3: Implement worktree lifecycle and candidate collection.**

Set `base_commit=$(git rev-parse HEAD)` after validating the request, then use
`git worktree add --detach /tmp/career-maintenance-worktree "$base_commit"` and register a
`finally` cleanup with `git worktree remove --force`. Copy only the validated
request into the worktree under `.career-state/maintenance/requests/` so the
agent can read it without access to the original checkout. Run the maintenance
agent with `SubprocessAgentRunner(worktree)` and a dedicated `stage="maintenance"`.
Generate the candidate diff with `git diff --binary "$base_commit" --`, run
`validate_maintenance_paths` against the request and candidate paths, and reject
every changed path not in `allowed_paths` before any canonical apply. The
worktree may contain request metadata and receipts for the attempt, but those
files must be excluded from the candidate diff and never copied to the
canonical checkout.

- [ ] **Step 4: Run focused isolation tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'worktree or allowlist'`

Expected: PASS, with no source change in the original checkout during worker execution.

- [ ] **Step 5: Commit isolated worker support.**

```bash
git add src/career/services/maintenance_orchestrator.py src/career/services/agent_runner.py tests/test_maintenance_orchestrator.py
git commit -m "feat: executa manutencao em worktree isolado"
```

### Task 3: Implement gates e revisão independente com score 99

**Files:**
- Modify: `src/career/services/maintenance_orchestrator.py`
- Create: `tests/fixtures/maintenance_reviewer_approved.json`
- Create: `tests/fixtures/maintenance_reviewer_rejected.json`
- Test: `tests/test_maintenance_orchestrator.py`

**Interfaces:**
- Produces `_run_deterministic_checks(worktree, request, diff_path) -> dict[str, Any]`.
- Produces `_run_reviewer(review_input_dir, request, diff_path, checks) -> dict[str, Any]`.
- Produces `_accept_review(review, *, diff_sha256, spec_sha256) -> bool`.

- [ ] **Step 1: Write failing tests for hard gates and the threshold.**

```python
def test_reviewer_accepts_exactly_99_and_matching_hashes(tmp_path):
    review = reviewer_payload(score=99.0, requirements_met=True, blockers=[])
    assert orchestrator._accept_review(review, diff_sha256=review["diff_sha256"], spec_sha256=review["spec_sha256"])

def test_reviewer_rejects_98_99_even_without_blockers(tmp_path):
    review = reviewer_payload(score=98.99, requirements_met=True, blockers=[])
    assert not orchestrator._accept_review(review, diff_sha256=review["diff_sha256"], spec_sha256=review["spec_sha256"])

def test_hard_gate_rejects_high_score_when_test_failed(tmp_path):
    checks = {"status": "failed", "commands": [{"returncode": 1}]}
    result = orchestrator._approval_decision(review=reviewer_payload(score=100.0), checks=checks)
    assert result["status"] == "rejected"
```

- [ ] **Step 2: Run the threshold tests and verify failure.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'reviewer or threshold or hard_gate'`

Expected: FAIL because no reviewer schema validation or hard-gate decision exists.

- [ ] **Step 3: Implement deterministic checks and reviewer input.**

The deterministic checker must run `git diff --check`, validate changed paths,
verify the base commit, and execute `PYTHONPATH=src .venv/bin/pytest -q
tests/test_canonical_maintenance.py tests/test_harness_dispatch.py` in the
worktree. The reviewer input directory must contain the original spec, the
binary/text diff, changed-file list, command results and hashes. Invoke the
reviewer with a separate `SubprocessAgentRunner` and require the exact JSON
contract; reject malformed JSON, missing requirements, hash mismatch, score
below 99 or any blocker.

- [ ] **Step 4: Run reviewer and hard-gate tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'reviewer or threshold or hard_gate'`

Expected: PASS, including exact boundary behavior for `99.0` and `98.99`.

- [ ] **Step 5: Commit the review gate.**

```bash
git add src/career/services/maintenance_orchestrator.py tests/test_maintenance_orchestrator.py tests/fixtures/maintenance_reviewer_approved.json tests/fixtures/maintenance_reviewer_rejected.json
git commit -m "feat: adiciona revisao independente de manutencao"
```

### Task 4: Implement retry, receipt e aplicação transacional

**Files:**
- Modify: `src/career/services/maintenance_orchestrator.py`
- Modify: `src/career/services/maintenance.py:83-118`
- Test: `tests/test_maintenance_orchestrator.py`

**Interfaces:**
- Produces `_process_attempt(request, attempt_number) -> dict[str, Any]`.
- Produces `_write_receipt(request, result) -> Path`.
- Produces `_apply_and_commit(candidate, request, review) -> dict[str, Any]`.

- [ ] **Step 1: Write failing tests for retries, idempotency and commit.**

```python
def test_reviewer_feedback_retries_twice_then_succeeds(tmp_path):
    runner = SequencedRunner(["reject", "reject", "approve"])
    result = MaintenanceOrchestrator(tmp_path, runner=runner).process(request_path)
    assert result["status"] == "committed"
    assert result["attempts"] == 3

def test_fourth_failure_is_blocked_without_apply(tmp_path):
    runner = SequencedRunner(["reject", "reject", "reject"])
    result = MaintenanceOrchestrator(tmp_path, runner=runner).process(request_path)
    assert result["status"] == "blocked"
    assert result["attempts"] == 3
    assert git_log(tmp_path) == ["base"]

def test_successful_commit_contains_request_and_roadmap(tmp_path):
    result = approving_orchestrator(tmp_path).process(request_path)
    assert result["status"] == "committed"
    assert "maintenance_" in git_last_commit_message(tmp_path)
    assert "MAINT-002" in git_last_commit_message(tmp_path)
    assert Path(result["receipt_path"]).is_file()
```

- [ ] **Step 2: Run retry tests and verify failure.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'retry or idempotency or commit'`

Expected: FAIL because retries, receipt persistence and canonical commit are not wired.

- [ ] **Step 3: Implement bounded retries and feedback handoff.**

Persist each attempt under `.career-state/maintenance/attempts/maintenance_demo/1/`
with spec hash, diff hash, checks, reviewer report and status. On rejection,
pass the reviewer blockers to the next maintenance-agent prompt. Refuse a
request whose stored fingerprint already has status `committed` or `resumed`.

- [ ] **Step 4: Implement apply, post-apply checks and commit.**

Before applying, require canonical `HEAD == request["base_commit"]` and a clean
tracked checkout. Run
`apply_maintenance_patch(root=canonical_root, patch_path=candidate["patch_path"], request_path=request_path, apply=False)`, then apply once,
run the post-apply checks, stage only allowlisted canonical paths and commit with
`f"maintenance({request['request_id']}): {request['objective']} [{request['roadmap_id']}]"`. If post-apply checks
fail, restore the checkout using the inverse patch and leave the request
`blocked`; do not commit or resume.

- [ ] **Step 5: Run retry and commit tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py -k 'retry or idempotency or commit'`

Expected: PASS, including no commit after three rejected attempts.

- [ ] **Step 6: Commit transaction support.**

```bash
git add src/career/services/maintenance.py src/career/services/maintenance_orchestrator.py tests/test_maintenance_orchestrator.py
git commit -m "feat: aplica manutencao aprovada com receipt e commit"
```

### Task 5: Conectar pedidos dos bots ao HarnessSupervisor

**Files:**
- Modify: `src/career/services/harness_supervisor.py:1112-1180`
- Modify: `src/career/services/harness_supervisor.py:2531-2660`
- Modify: `tests/test_harness_dispatch.py`

**Interfaces:**
- Produces `HarnessSupervisor._is_maintenance_request(message) -> bool`.
- Produces `HarnessSupervisor._process_maintenance_request(payload) -> dict[str, Any]`.
- `handle_message(message, channel="cli", execute=True, runtime_context=None)` routes a valid maintenance request to `MaintenanceOrchestrator.process()` and returns the structured result.

- [ ] **Step 1: Write failing dispatch tests for both profiles.**

```python
@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_bot_maintenance_request_is_not_classified_as_pasted_job(profile):
    decision = HarnessSupervisor().classify(
        json.dumps({"kind": "canonical_maintenance", "requester_profile": profile,
                    "objective": "corrigir leitor canônico", "roadmap_id": "MAINT-002"})
    )
    assert decision.workflow == "maintenance"
    assert decision.requires_approval is False

def test_maintenance_request_requires_canonical_application_scope_when_cellular():
    result = supervisor.handle_message(json.dumps({"kind": "canonical_maintenance",
        "cellular": True, "objective": "corrigir", "allowed_paths": ["src/x.py"]}), execute=True)
    assert result["result"]["status"] == "blocked"
    assert result["result"]["blocker_reason"] == "explicit_application_scope_required"
```

- [ ] **Step 2: Run dispatch tests and verify failure.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_dispatch.py -k maintenance`

Expected: FAIL because the classifier does not expose a maintenance workflow.

- [ ] **Step 3: Add deterministic maintenance routing before pasted-job detection.**

Recognize only structured JSON with `kind == "canonical_maintenance"` or an
explicit internal envelope emitted by the agent. Do not classify arbitrary
prose containing “manutenção” as a maintenance request. Pass the original
profile, application/run scope, spec, evidence and allowlist unchanged to the
request validator. A cellular request without both IDs is blocked before the
worker starts.

- [ ] **Step 4: Execute through the orchestrator and preserve conversational status.**

When `execute=False`, return `prepared` with the request path and validation.
When `execute=True`, run the orchestrator and expose `requested`, `running`,
`rejected`, `blocked`, `committed` or `resumed` without converting a blocked
maintenance attempt into `completed`. Keep `generic_assistant` handling for
human-readable Harness reports unchanged.

- [ ] **Step 5: Run Harness tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_harness_dispatch.py tests/test_maintenance_orchestrator.py`

Expected: PASS, including both profile parametrizations and old dispatch tests.

- [ ] **Step 6: Commit supervisor integration.**

```bash
git add src/career/services/harness_supervisor.py tests/test_harness_dispatch.py
git commit -m "feat: encaminha manutencao dos bots ao supervisor"
```

### Task 6: Adicionar comando operacional e reload controlado

**Files:**
- Modify: `src/career/cli.py:438-446,1741-1765`
- Modify: `src/career/services/maintenance_orchestrator.py`
- Modify: `tests/test_maintenance_orchestrator.py`
- Test: `tests/test_runtime_verifier.py`

**Interfaces:**
- CLI: `request_path=/tmp/maintenance-request.json; npm run career -- maintenance process --request "$request_path"` delegates to `HarnessSupervisor` and prints JSON.
- Produces `_reload_profiles() -> dict[str, Any]` using `docker compose -f compose.yaml up -d --force-recreate vagas_bot_01 vagas_bot_02` only after a runtime/skill change is committed.
- Produces `_resume_original_run(request) -> dict[str, Any]` using the official scoped command only when the request has both `application_id` and `run_id`.

- [ ] **Step 1: Write failing tests for CLI, reload and scoped resume.**

```python
def test_cli_process_returns_blocked_receipt_for_invalid_request(tmp_path):
    result = run_cli("maintenance", "process", "--request", str(tmp_path / "bad.json"))
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "blocked"

def test_successful_skill_change_reloads_both_profiles(monkeypatch):
    result = orchestrator.reload_profiles_if_needed(changed_paths=[".agents/skills/escrita-humana/SKILL.md"])
    assert result["command"][-2:] == ["vagas_bot_01", "vagas_bot_02"]

def test_successful_code_change_without_run_does_not_resume(monkeypatch):
    result = orchestrator.resume_original_run({"application_id": "", "run_id": ""})
    assert result["status"] == "not_requested"
```

- [ ] **Step 2: Run the tests and verify failure.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py tests/test_runtime_verifier.py -k 'cli or reload or resume'`

Expected: FAIL because the CLI subcommand and post-commit lifecycle do not exist.

- [ ] **Step 3: Add `maintenance process` without changing legacy commands.**

Load the request with `read_json`, invoke `HarnessSupervisor(Path.cwd()).process_maintenance_request`, print the complete receipt and return nonzero for `blocked` or `rejected`. Keep `maintenance request` and `maintenance apply` behavior backward-compatible.

- [ ] **Step 4: Implement profile reload and scoped resume.**

Reload both services with the canonical `compose.yaml` only after a successful
commit when the validated maintenance policy marks the changed paths as
runtime-affecting: application code, Hermes code, existing skills, runtime
configuration or their dependencies. Documentation-only and test-only changes
do not trigger reload. The policy result, command and `docker compose ps`
output must be stored in the receipt.
Verify `docker compose ps --status running vagas_bot_01 vagas_bot_02` and record
the output. Resume only with the exact `application_id`/`run_id` from the request,
using `npm run applications:run -- --application-id "$application_id" --run-id "$run_id" --run-agent`;
never infer IDs from global pointers.

- [ ] **Step 5: Run CLI and lifecycle tests.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_maintenance_orchestrator.py tests/test_runtime_verifier.py -k 'cli or reload or resume'`

Expected: PASS, with external Docker calls mocked in unit tests.

- [ ] **Step 6: Commit operational entrypoint.**

```bash
git add src/career/cli.py src/career/services/maintenance_orchestrator.py tests/test_maintenance_orchestrator.py tests/test_runtime_verifier.py
git commit -m "feat: adiciona processamento operacional de manutencao"
```

### Task 7: Validar os dois bots e atualizar o estado de produção

**Files:**
- Modify: `tests/test_maintenance_orchestrator.py`
- Modify: `tests/test_harness_dispatch.py`
- Modify: `docs/roadmap.md`
- Read: `compose.yaml`, `hermes/vagas_bot_01/config.yaml`, `hermes/vagas_bot_02/config.yaml`, `AGENTS.md`

**Interfaces:**
- Produces a deterministic offline canary for each profile.
- Produces a live maintenance receipt with the requester profile, commit hash,
  reviewer score, reload status and resume status.

- [ ] **Step 1: Add profile-specific offline canaries.**

```python
@pytest.mark.parametrize("profile", ["vagas_bot_01", "vagas_bot_02"])
def test_profile_canary_produces_same_canonical_result(tmp_path, profile):
    request = make_valid_request(tmp_path, requester_profile=profile,
                                 allowed_paths=["src/career/services/cv_content.py"])
    result = approving_orchestrator(tmp_path).process(request)
    assert result["status"] == "committed"
    assert result["review"]["score"] >= 99.0
    assert result["changed_paths"] == ["src/career/services/cv_content.py"]
```

- [ ] **Step 2: Run the complete focused suite.**

Run: `PYTHONPATH=src .venv/bin/pytest -q tests/test_canonical_maintenance.py tests/test_maintenance_orchestrator.py tests/test_harness_dispatch.py tests/test_runtime_verifier.py`

Expected: PASS.

- [ ] **Step 3: Run project gates before deployment.**

Run: `npm run validate:structure`

Expected: exit 0.

Run: `npm run runtime:verify -- --strict`

Expected: exit 0 for the host configuration and both effective bot profiles.

Run: `git diff --check`

Expected: no output and exit 0.

- [ ] **Step 4: Run one controlled live request from each bot.**

Use a harmless allowlisted maintenance request that changes an existing test
fixture in a disposable Git checkout, while exercising the real supervisor
route once with `requester_profile="vagas_bot_01"` and once with
`requester_profile="vagas_bot_02"`. Confirm both requests reach `committed`,
the reviewer score is at least `99.0`, the commit hashes and receipts are
recorded, and no production checkout path changes. Separately exercise the
runtime-affecting policy with a mocked reload command and verify that it names
both services; a disposable test-fixture commit must not reload production.

- [ ] **Step 5: Update roadmap only with evidence.**

Change `MAINT-002` from `BACKLOG` to `DONE` only after both live receipts,
focused tests, structure validation, strict runtime verification and reload
checks are present. Add the exact commit hashes and receipt paths to the plan
row; if a live prerequisite fails, mark the item `BLOCKED` with that evidence
instead of claiming completion.

- [ ] **Step 6: Commit final evidence.**

```bash
git add docs/roadmap.md tests/test_maintenance_orchestrator.py tests/test_harness_dispatch.py
git commit -m "test: valida manutencao autonoma nos dois bots"
```

## Final verification checklist

- [ ] A request from each bot is recognized as `maintenance`, never as pasted job.
- [ ] Missing scope, invalid spec and forbidden paths are blocked before a worker starts.
- [ ] An existing canonical skill can be changed when explicitly allowlisted.
- [ ] Creation of a new skill is rejected before the worker starts.
- [ ] Versioned tests, docs and configuration may be changed only when explicitly allowlisted.
- [ ] The worker writes only in a temporary worktree.
- [ ] The reviewer is a separate read-only process and receives the original spec.
- [ ] `99.0` passes; `98.99` fails; hard gates override model confidence.
- [ ] Three rejected attempts stop without a canonical commit.
- [ ] Successful application creates a commit and a complete receipt.
- [ ] Both profiles reload after runtime/skill changes.
- [ ] The original scoped run resumes only when its IDs are present.
- [ ] `MAINT-002` is updated with real evidence, not a narrative assertion.
