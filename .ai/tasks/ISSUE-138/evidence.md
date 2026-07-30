# Evidence

## HEAD

HEAD: 6b711c671a756ad7a939402bb0952eb0af0d9bce

This is the unchanged production HEAD exercised by the uncommitted red-first task and test
contract. The final evidence will bind the implementation HEAD.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py` | 1 | 8 failed, 12 passed. Small/large projects cost 4/13 queries, status cost 10, metadata loaded twice, absence cost 13, and rate-limit type/progress/exit contracts were absent. |

## Coverage and mutation

All seven acceptance criteria were red. Query-cost tests observed the current
`project view`/`field-list`/`issue view`/`item-list --limit 1000` path. The missing
`BoardRateLimitError` made the type, reset-time, partial-progress, and no-retry regressions fail.

The existing guard-read invariants remained green: `arm` and `start` each performed their initial,
intermediate, and final `issue_state` reads. The implementation must preserve those counts while
changing only immutable metadata reuse.

## Deferred checks

- One bounded live `status` command will confirm the exact query count only after deterministic
  tests are green.
- Independent adversarial/live-money review and Linux mutation evidence remain pending.
