# Impact analysis

## Direct impact

- `AGENTS.md` and `CLAUDE.md` swap primary builder/reviewer contracts.
- The constitution, current engineering docs, README/roadmap, and Claude Markdown runtime files
  reconcile the same role language.
- The risk-model reasons and pull-request-template comment use the new role terms without changing
  their keys, classes, matching, required headings, or validation semantics.
- `tests/test_engineering_docs.py` becomes the executable role-assignment guard.

## Transitive impact

Every future Codex build and Claude design/review session reads the corrected contract; future role
language changes are checked by the normal test suite.

## Critical dependencies

The fixed tool-to-file binding, immutable real-money constraints, R3 readiness policy, and Jan's
exclusive decision and merge authority must remain intact.

## Unknown or dynamic edges

Claude Code discovers Markdown skills/subagents at runtime; this change alters their role remit but
does not alter their format, tools, hook wiring, or executable behaviour.
