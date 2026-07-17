# Caminhos Portáveis do Projeto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar caminhos absolutos específicos do Mac e impedir que reapareçam.

**Architecture:** A documentação parte da raiz do repositório. Cada script em `scripts/generated/` calcula a raiz com `path.resolve(__dirname, "..", "..")` e monta a saída com `path.join`. O validador estrutural bloqueia o caminho absoluto nos roots ativos.

**Tech Stack:** Node.js CommonJS, Python 3 standard library, pytest, Markdown.

## Global Constraints

- Não usar `/Users/mac/llm server/projetos/candidaturas` em nenhum arquivo ativo.
- Não introduzir variável de ambiente nova.
- Scripts gerados escrevem em `<raiz>/outputs/_tmp/<nome>.docx` via `path.join`.
- Não alterar conteúdo de documentos, credenciais, rclone ou OneDrive.

---

### Task 1: Corrigir documentação e scripts gerados

**Files:**

- Modify: `COMO_USAR.md:139`
- Modify: `scripts/generated/cover_letter_chief_of_staff_dehaze_en.js`
- Modify: `scripts/generated/cv_capacity_planning_manager_en.js`
- Modify: `scripts/generated/cv_chief_of_staff_dehaze_en.js`
- Modify: `scripts/generated/cv_client_success_director_wellhub_en.js`
- Modify: `scripts/generated/cv_customer_service_book_fair.js`
- Modify: `scripts/generated/cv_diretor_operacoes_amg_group.js`
- Modify: `scripts/generated/cv_diretor_operacoes_confidencial.js`
- Modify: `scripts/generated/cv_diretor_operacoes_lemartransportes.js`
- Modify: `scripts/generated/cv_gerente_operacoes_grupo_easy.js`
- Modify: `scripts/generated/cv_global_product_operations_manager_bytedance_brazil_en.js`
- Modify: `tests/test_project_structure.py`

**Interfaces:**

- Consumes: Node `__dirname`, existing `fs` imports, and each existing DOCX filename.
- Produces: `<repository-root>/outputs/_tmp/<existing filename>.docx` from every generated script.

- [ ] **Step 1: Add the failing regression test**

```python
def test_project_has_no_machine_specific_workspace_path():
    forbidden = "/Users/mac/llm server/projetos/candidaturas"
    assert forbidden in validate_project_structure.FORBIDDEN_TEXT
    assert validate_project_structure.main() == 0
```

- [ ] **Step 2: Verify it fails before the gate exists**

Run: `pytest tests/test_project_structure.py::test_project_has_no_machine_specific_workspace_path -v`

Expected: FAIL because the forbidden string is not yet configured.

- [ ] **Step 3: Make the OpenCode documentation location-independent**

Replace the absolute startup command with:

```bash
# Na raiz do repositório clonado
opencode
```

- [ ] **Step 4: Replace each generated absolute output path**

Ensure each listed JS file imports `path` beside `fs`, then define its pre-existing filename as:

```javascript
const workspace = path.resolve(__dirname, "..", "..");
const outPath = path.join(workspace, "outputs", "_tmp", "<existing-output-filename>.docx");
```

Use `fs.writeFileSync(outPath, buffer)`. Do not change any document content, filename, or console behavior.

- [ ] **Step 5: Syntax-check all changed generated scripts**

Run:

```bash
for file in scripts/generated/cover_letter_chief_of_staff_dehaze_en.js scripts/generated/cv_capacity_planning_manager_en.js scripts/generated/cv_chief_of_staff_dehaze_en.js scripts/generated/cv_client_success_director_wellhub_en.js scripts/generated/cv_customer_service_book_fair.js scripts/generated/cv_diretor_operacoes_amg_group.js scripts/generated/cv_diretor_operacoes_confidencial.js scripts/generated/cv_diretor_operacoes_lemartransportes.js scripts/generated/cv_gerente_operacoes_grupo_easy.js scripts/generated/cv_global_product_operations_manager_bytedance_brazil_en.js; do node --check "$file"; done
```

Expected: no output, exit code 0.

- [ ] **Step 6: Commit Task 1**

```bash
git add COMO_USAR.md scripts/generated tests/test_project_structure.py
git commit -m "fix: make generated artifact paths portable"
```

### Task 2: Bloquear regressões de portabilidade

**Files:**

- Modify: `scripts/validate_project_structure.py:71-80`
- Test: `tests/test_project_structure.py`

**Interfaces:**

- Consumes: `FORBIDDEN_TEXT`, `SCAN_ROOTS`, and `iter_files`.
- Produces: a validator failure when the Mac-specific project path is found in an active file.

- [ ] **Step 1: Add the exact forbidden path to the validator**

Insert into `FORBIDDEN_TEXT`:

```python
"/Users/mac/llm server/projetos/candidaturas",
```

Keep all existing forbidden paths, strings, and roots unchanged.

- [ ] **Step 2: Run the focused regression**

Run: `pytest tests/test_project_structure.py::test_project_has_no_machine_specific_workspace_path -v`

Expected: PASS.

- [ ] **Step 3: Run complete verification**

Run:

```bash
rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!outputs/**' --glob '!inbox/**' '/Users/mac/llm server/projetos/candidaturas' AGENTS.md COMO_USAR.md .agents scripts src tests .env.example
python3 scripts/validate_project_structure.py
pytest -q
git diff --check
```

Expected: `rg` has no output; structural validation and pytest pass; diff check has no output.

- [ ] **Step 4: Commit Task 2**

```bash
git add scripts/validate_project_structure.py tests/test_project_structure.py
git commit -m "test: enforce portable project paths"
```
