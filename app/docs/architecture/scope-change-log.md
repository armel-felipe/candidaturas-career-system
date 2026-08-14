# Scope-change log

## SC-2026-08-14-01 — controlled application handoff

- Decision: add `applications:handoff` as the operator-to-bot handoff boundary.
- Included: source validation, fingerprinting, compose target resolution, stale-target quarantine, profile binding, SQLite run/cell/input/request registration, and bounded `analyze_fit` preparation.
- Explicitly excluded: model execution, FIT_MAP completion, CV generation/review/delivery, Notion synchronization, Gmail, OneDrive, LinkedIn extraction, and automatic application submission.
- Reason: the immediate problem is context growth and missing persisted inputs between sessions. Adding downstream work would hide whether handoff itself is correct and would expand side-effect risk.
- Approval: user approved implementation with “manda a ver” after the design was presented.
- Change control: any downstream execution or new projected artifact must be proposed as a separate scope change, tested independently, and recorded here before implementation.
