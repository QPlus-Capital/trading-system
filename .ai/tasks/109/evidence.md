# Evidence

## HEAD

HEAD: pending

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_classify.py tests/test_engineering_docs.py` before the TOML change | 1 | RED: 9 failed, 90 passed. Both executable-contract cases, architecture R2, catch-all coexistence, duplicate-rule removal, tracked-tree reconstruction, and the new engineering-doc guards failed. |
| `adversarial-review` | independent Claude review | 1 | OWED: Codex built the change and cannot review it. The draft PR is the handoff surface. |

## Coverage and mutation

Focused post-change proof currently passes 99 tests. Full gate evidence is recorded after the
implementation commit binds the tested HEAD.

## Deferred checks

- Independent Claude review.
