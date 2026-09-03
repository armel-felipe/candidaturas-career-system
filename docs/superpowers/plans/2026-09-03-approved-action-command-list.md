# Approved Notion action command-list compatibility

## Objective

Make the explicit Notion update path compatible with the pending-action shape
actually produced by the specialist and make approval execution idempotent.

## Completed work

- [x] Reproduce `approved_action_validation_failed` from the live pending action.
- [x] Confirm the artifact is `kind=notion` with `command_list`, not `command`.
- [x] Treat an already `written` action with a resolved page as completed without
      duplicating the external write.
- [x] Parse only the final canonical command from `command_list` and enforce
      approved Notion command prefixes.
- [x] Add regression tests for written and pending command-list actions.
- [x] Run the complete test suite: `843 passed, 3 warnings`.
- [x] Rebuild/recreate both production containers and verify the live artifact
      path through the deployed runtime.
