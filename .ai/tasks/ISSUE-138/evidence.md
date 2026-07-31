# Evidence

## HEAD

HEAD: c93d0d39e7c160a872ddae92bd4ddf1551895a7c

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_board.py` | 1 | 8 failed, 12 passed. Small/large projects cost 4/13 queries, status cost 10, metadata loaded twice, absence cost 13, and rate-limit type/progress/exit contracts were absent. |
| `risk-classification` | `uv run python -m scripts.quality.classify` | 0 | R3 because `scripts/quality/**` controls repository-wide guards; six changed paths, with `board.py` the only changed production file. |
| `format` | `just check-fast origin/main` | 0 | Both changed Python files were already formatted after the initial format-only correction. |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract` | 0 | Generated workflow-contract blocks and digests are current. |
| `check` | PowerShell: `$env:PYTHONUTF8='1'; just --shell "C:\Program Files\Git\bin\sh.exe" check` after rebasing onto `origin/main` at `90fdb04` | 0 | Ruff, strict MyPy over 193 source files, Vulture, and the complete deterministic suite passed: 1,710 passed, one unavailable-Mutmut skip, 98 existing warnings. |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py` after the semantic #136/#138 union | 0 | All 84 combined Permit, interleaving, query-cost, rate-limit, gateway, service, CLI, boundary, and pagination tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | Fixed Hypothesis seed `20260721` passed twice: 21 tests plus 21 tests. |
| `integration-tests` | `just check` | 0 | The full repository suite passed, including Board workflow/service integration and all existing consumers. |
| `artifact-schema` | `just check-task-artifact ISSUE-138 origin/main` | 0 | Valid R3 artifact with seven acceptance criteria and three invariants mapped. |
| `invariants` | `just check-invariants` | 0 | All 529 critical invariant tests passed; no live boundary was invoked. |
| `mutation-on-touched-critical` | production `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | Exact result `[]`: `board.py` and its tests exercise no configured critical mutation target. Native Mutmut correctly refused on Windows; no mutation result, target, baseline, or threshold change is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- core research live monitoring` | 0 | No trading, research, live, or monitoring production path changed; trading parity is not applicable. The full Linux suite remains deferred to the ready transition. |
| `live-money-review` | production diff plus `uv run python -m scripts.quality.review_selection R3 --base origin/main` | 0 | No live-money, runner, bridge, order, sizing, risk-limit, account, or methodology path changed or ran; the executable matrix selects code and test reviewers only. |
| `human-decision-escalation` | approved issue #138 scope and decision audit | 0 | Jan selected the single-item query, process-local immutable metadata cache, typed reset-time failure, partial-progress reporting, and no-retry boundary; no domain choice remains delegated. |
| `no-autonomous-merge` | branch and delivery-state audit | 0 | Feature branch only; the pull request will remain draft, auto-merge disabled, and Jan retains ready and merge authority. |
| `security` | `just check-security` | 0 | Secret scan passed, pip-audit found no known vulnerabilities, and high-signal security Ruff passed. |
| `impact` | `just impact origin/main` | 0 | One production file and one directly related test file; no transitive test, critical escalation, or unknown dynamic edge. |
| `live-query-cost` | GraphQL allowance before/after `uv run python -m scripts.quality.board status 138` | 0 | The current query succeeded against GitHub's live schema, returned `Implementing` with `risk:R3`, and consumed exactly one GraphQL point (2,348 to 2,347) without mutation. |

## Coverage and mutation

All seven acceptance criteria were red before the implementation. Query-cost tests observed the
old `project view`/`field-list`/`issue view`/`item-list --limit 1000` path. The missing
`BoardRateLimitError` made the type, reset-time, partial-progress, and no-retry regressions fail.

After the fix, status costs one issue-scoped GraphQL query for both a five-item and a 905-item
project. Project id, Status field id, and option ids load once per gateway; every label/status guard
still performs a fresh issue snapshot. `arm` and `start` retain initial, intermediate, and final
state reads. A truncated project-membership connection fails closed after one query rather than
misreporting absence.

The production mutation selector returned no targets. This is applicability evidence, not a
mutation-run claim: no configured target, policy, baseline, threshold, or survivor classification
changed.

## Deferred checks

- Independent Claude adversarial-code and test-quality review remains pending on the draft pull
  request. No builder-authored review verdict is claimed.
- Linux `full-quality` has not run. It is conditional on the ready transition; the full local
  1,646-test result is Windows evidence and is not presented as Linux parity.
