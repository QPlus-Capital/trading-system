# Evidence

## HEAD

HEAD: pending-final-tested-commit

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_review_observation.py tests/test_quality_pr_ready.py tests/test_quality_validate_task.py tests/test_ci_cost_workflows.py` | 1 | RED: collection failed because `scripts.quality.review_observation` did not exist |

## Coverage and mutation

Focused behavioural coverage includes review/commit ordering, GitHub verdict states, validator and
readiness agreement, Markdown-shape independence, evidence-only currency, and CI diff selection.
Mutation results are pending the final R3 gate run.

## Deferred checks

Independent review is deferred to a fresh reviewer after the draft pull request is opened.
