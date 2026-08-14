# Scope-change log

## SC-2026-08-14-01 — controlled application handoff

- Decision: add `applications:handoff` as the operator-to-bot handoff boundary.
- Included: source validation, fingerprinting, compose target resolution, stale-target quarantine, profile binding, SQLite run/cell/input/request registration, and bounded `analyze_fit` preparation.
- Explicitly excluded: model execution, FIT_MAP completion, CV generation/review/delivery, Notion synchronization, Gmail, OneDrive, LinkedIn extraction, and automatic application submission.
- Reason: the immediate problem is context growth and missing persisted inputs between sessions. Adding downstream work would hide whether handoff itself is correct and would expand side-effect risk.
- Approval: user approved implementation with “manda a ver” after the design was presented.
- Change control: any downstream execution or new projected artifact must be proposed as a separate scope change, tested independently, and recorded here before implementation.

## SC-2026-08-14-02 — compact CV skill input

- Decision: reduce the CV skill loaded into agent requests from roughly 51 KB to 6.4 KB.
- Included: preserve the operational gates, evidence rules, language rules, output naming, DOCX validation, ATS registration, reviewer approval, delivery, and prohibitions in the loaded skill.
- Removed from the loaded context: duplicated examples and repeated long-form explanations already covered by `AGENTS.md`, `career-system`, and the executable commands.
- Compatibility: the bot-mounted `app/.agents` copy and the operator `.agents` copy are synchronized in behavior; the app copy retains its required `instruction_modules` metadata.
- Validation: the new context-budget test passes and the real bot_02 Innolevels CV request returns `status=ok`, with no oversized files.
