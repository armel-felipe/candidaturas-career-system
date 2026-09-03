# Harness routing and final-state guard

## Objective

Prevent post-analysis CV/Notion requests from falling into the generic assistant
and prevent a historical SQLite projection from being presented as a completed
FIT_MAP when the scoped canonical artifact is incomplete.

## Completed work

- [x] Reproduce the natural-language Notion routing failure.
- [x] Reproduce reuse of a historical summary without a scoped final FIT_MAP.
- [x] Route create/register/save/add Notion variants to `notion_update`.
- [x] Require scoped `fit_map.json`, matching job identity, and registered ATS
      keywords before FIT_MAP reuse.
- [x] Add regression tests and verify the red/green cycle.
- [x] Run the complete test suite: `841 passed, 3 warnings`.
- [x] Rebuild and recreate `vagas_bot_01` and `vagas_bot_02`.
- [x] Verify both containers, Telegram connectivity, production routing, and
      `runtime:verify -- --strict` with `blockers=[]`.

## Evidence

- Runtime commit: `f49159f`.
- Both production containers are running with zero restarts.
- Natural-language Notion variants resolve to `notion_update` in both
  containers.
- Incomplete scoped state is not reusable; finalized scoped state is reusable.
