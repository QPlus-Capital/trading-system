# Evidence

## HEAD

HEAD: 76103809c753fb1d990ad5d0b8bd626e738db3be

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python scripts/quality/classify.py --base origin/main` | 0 | R3 expected from `.ai/quality/**`, `scripts/quality/**`, role-contract, and guard-test paths. |
| `red-first` | `uv run pytest -q tests/test_quality_process_scaling.py tests/test_finding_registry_split.py` | 1 | RED during collection: missing `pr_transition_decision` and missing `scripts.quality.finding_registry`; 2 collection errors. |

## Coverage and mutation

Pending implementation. No mutation threshold, target, baseline, or survivor
classification is in scope.

## Deferred checks

Independent adversarial review is intentionally deferred to Claude on the draft pull
request. No deterministic build or gate result is being claimed yet.
