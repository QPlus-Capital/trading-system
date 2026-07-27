# Evidence

## HEAD

HEAD: 20df6cfb9d3acb4a0c657f7fc5a7d02c22ebda19

Only this evidence file may change after the tested HEAD.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Three changed Python files were already formatted; Ruff, strict mypy, impact analysis, and 74 focused tests passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 180 files, Vulture, and 1,194 tests passed; one Linux-only mutation self-test skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | Impact selected and passed 74 direct/transitive monitoring and property tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Twenty properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_monitoring_deals.py tests/test_monitoring_risk_view.py tests/test_monitoring_dashboard.py tests/test_monitoring_dashboard_copy.py` | 0 | 54 tests passed through the real deal, basis, risk-view, and dashboard consumers. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-102-104 --base origin/main` | 0 | Task artifact valid with 12 acceptance criteria and 9 invariants. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-102-104 --base origin/main` | 0 | Builder preflight records 18 counterexamples and one P3 human-decision question; independent Claude review remains required before ready state. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 306 critical invariant tests passed, including live risk, signal parity, H4 path, result integrity, and readiness guards. |
| `mutation-on-touched-critical` | GitHub Actions `Critical mutation` | 1 | Blocked by infrastructure — Actions quota exhausted until 2026-08-01. The Linux gate did not run and no result is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live core research` plus SHA-256 comparison of both reference trade CSVs | 0 | No live, signal, or research producer changed; both trade hashes match the registered baseline exactly. |
| `live-money-review` | source diff, 54 synthetic monitoring integration tests, and `just check-invariants` | 0 | No runner/MT5 initialization or live path edit; unsupported history fails closed before an operator direction is emitted. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-102-104 --base origin/main` | 0 | Jan's bundle/scope/draft/merge decisions and the unresolved INOUT cost-attribution question are explicit. |
| `no-autonomous-merge` | `git branch --show-current` and publication policy review | 0 | Feature branch `codex/issue-102-104-mt5-deal-semantics`; draft PR only, no ready/merge/auto-merge action. |

### Package evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 with all fourteen cumulative required gates; the existing mutation registry is an R3 governance path. |
| `red-first` | `uv run pytest -q tests/test_monitoring_deals.py tests/test_monitoring_risk_view.py` before implementation | 1 | RED: 6 failed and 26 passed. Unknown type `13` and `True` did not raise; INOUT emitted one row instead of two; OUT_BY emitted none; scale-in volume remained `0.1` instead of `0.3`; and the reversal opening boundary was absent. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | One production file; two direct and two transitive monitoring test modules plus property tests; no unknown or dynamic edges. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerability, and Ruff security checks passed. |
| `pr-ready` | pending evidence-only run | 1 | To be run after this evidence is committed; expected NOT READY solely because Linux mutation is blocked. |

## Numerical and artifact regression

No research stage was run. `git diff --exit-code origin/main...HEAD -- live core research` passed,
so neither trade producer is reachable from this package. The current registered reference
`run_20260727_issue58` hashes remain:

- `portfolio_trades.csv`:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv`:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

Normal IN/OUT, fee, ledger, and P-14 basis fixtures remain exact. Histories containing INOUT or
OUT_BY may correctly change operator trade count, close-window membership, per-trade R, hit rate,
profit factor, expectancy, and per-market rows. Aggregate ledger money remains exact.

## Coverage and mutation

Red-first tests covered every requested guard. Final focused integration ran 54 tests, conservative
impact ran 74, properties ran 20 twice, the full suite ran 1,194, and critical invariants ran 306.
The existing `monitoring-deal-reconstruction` mutation target now includes the strict converter,
entry/volume checks, opposite-side mapping, and row builder.

The Linux Critical mutation workflow did not run. Its exact-survivor baseline therefore was not
regenerated and no mutation score is claimed.

## Deferred checks

Linux Critical mutation is blocked by infrastructure — Actions quota exhausted until 2026-08-01.
This is a real readiness blocker, not a pending or claimed result. On quota reset: push an empty
commit, run Critical mutation, reconcile the exact baseline if required, update this evidence, run
`pr-ready`, obtain independent Claude review, and only then consider marking the PR ready. Jan
alone decides merge.
