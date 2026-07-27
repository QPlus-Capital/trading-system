# Evidence

## HEAD

HEAD: pending

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | pending | — | Not run. |
| `docs-consistency` | pending | — | Not run. |
| `check` | pending | — | Not run. |
| `impacted-tests` | pending | — | Not run. |
| `property-tests-where-applicable` | pending | — | Not run. |
| `integration-tests` | pending | — | Not run. |
| `artifact-schema` | pending | — | Not run. |
| `adversarial-review` | pending | — | Not run. |
| `invariants` | pending | — | Not run. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation` | — | Blocked by infrastructure — Actions quota exhausted until 2026-08-01. |
| `parity-where-applicable` | pending | — | Not run. |
| `live-money-review` | pending | — | Not run. |
| `human-decision-escalation` | pending | — | Not run. |
| `no-autonomous-merge` | pending | — | Not run. |

### Package evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify monitoring/deals.py tests/test_monitoring_deals.py tests/test_monitoring_risk_view.py .ai/tasks/ISSUE-102-104/*.md` | 0 | Classifier R2; manually upgraded to R3 by instruction and real-money monitoring consequence. |
| `red-first` | `uv run pytest -q tests/test_monitoring_deals.py tests/test_monitoring_risk_view.py` before implementation | 1 | RED: 6 failed and 26 passed. Unknown type `13` and `True` did not raise; INOUT emitted one row instead of two; OUT_BY emitted none; scale-in volume remained `0.1` instead of `0.3`; and the reversal opening boundary was absent. |
| `impact` | pending | — | Not run. |
| `security` | pending | — | Not run. |
| `pr-ready` | pending | — | Not run. |

## Numerical and artifact regression

Pending.

## Coverage and mutation

Focused behavioural, integration, property, full-suite, and invariant results will be recorded
after final HEAD. The Linux Critical mutation workflow is unavailable while the Actions quota is
exhausted; the existing mutation target was extended so every new critical helper is in scope when
the quota resets.

## Deferred checks

Linux Critical mutation is blocked by infrastructure: the GitHub Actions quota is exhausted until
2026-08-01. This is a real readiness blocker, not a pending or claimed result.
