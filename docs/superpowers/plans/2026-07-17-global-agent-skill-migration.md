# Global Agent Migration Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install one dry-run-first migration skill shared by OpenCode and Codex.

**Architecture:** `~/.agents/skills/migrate-agent-skills/` is the sole source. Codex reads it through `~/.codex/skills/migrate-agent-skills` as a symlink; OpenCode reads the canonical `~/.agents/skills` location directly.

**Tech Stack:** Markdown SKILL.md, JSON evaluation prompts, POSIX symlink.

## Global Constraints

- The default operation is audit/dry-run; mutation requires explicit confirmation.
- Never delete untracked files automatically.
- Migrate `.opencode/skills` to `.agents/skills` and update active references relative to the repository root.
- Keep only one physical copy of the skill.

---

### Task 1: Create the canonical global skill

**Files:**
- Create: `/Users/mac/.agents/skills/migrate-agent-skills/SKILL.md`
- Create: `/Users/mac/.agents/skills/migrate-agent-skills/evals/evals.json`

- [ ] Write a valid SKILL.md with `name: migrate-agent-skills`, a trigger-focused description, audit, confirmation, migration, validation, and report sections.
- [ ] Include instructions to resolve repository root with Git, inventory absolute paths, preserve untracked files, and verify post-migration structure.
- [ ] Add three eval prompts: audit request, confirmed migration request, and untracked-residue case.
- [ ] Validate frontmatter, directory/name match, and JSON syntax.

### Task 2: Expose the canonical skill to Codex

**Files:**
- Create: `/Users/mac/.codex/skills/migrate-agent-skills` (symlink)

- [ ] Create a symlink whose target is `/Users/mac/.agents/skills/migrate-agent-skills`.
- [ ] Verify both locations resolve to the same SKILL.md and that no copied SKILL.md exists under the Codex path.
- [ ] Report the OpenCode and Codex discovery paths.
