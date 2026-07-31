# Evidence

## HEAD

HEAD: 6094ff20098784ce0f39a1634c553e76a28cb06e

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | At pre-implementation commit `46aca97`: `uv run pytest -q tests/test_quality_board.py` | 1 | 8 failed, 75 passed: AC-01 through AC-07 and INV-03 were RED; INV-01 and INV-02 already held. Against the pre-review-fix helpers, the nine committed review regressions produced 9 failed, 98 passed, including the D-01 type-loss path. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because `scripts/quality/**` controls repository-wide guards; `board.py` is the only changed production file. |
| `format` | `just check-fast origin/main` | 0 | Ruff format reported both changed Python files already formatted; Ruff, strict MyPy over 193 source files, and all 110 focused tests passed. |
| `docs-consistency` | `uv run python -m scripts.quality.workflow_contract` | 0 | Generated workflow-contract blocks and digests are current. |
| `check` | `just check` | 0 | Ruff, strict MyPy over 193 source files, Vulture, and the complete deterministic suite passed: 1,736 passed, one unavailable-Mutmut skip, 98 existing warnings. |
| `impacted-tests` | `uv run pytest -q tests/test_quality_board.py` | 0 | All 110 Permit, interleaving, query-cost, rate-limit, gateway, service, CLI, boundary, pagination, and real-write-command tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | Fixed Hypothesis seed `20260721` passed twice: 21 tests plus 21 tests. |
| `integration-tests` | `just check` | 0 | The full repository suite passed, including Board workflow/service integration and all existing consumers. |
| `artifact-schema` | `just check-task-artifact ISSUE-138 origin/main` | 0 | Valid R3 artifact with seven acceptance criteria and three invariants mapped. |
| `adversarial-review` | Claude review `4827246531` of prior head `e77e8d4` | 1 | D-01 through D-04 and S-01 through S-05 were reproduced and fixed; the Notes were reconciled. A complete independent re-review of `6094ff2` is required and is not claimed by the builder. |
| `invariants` | `just check-invariants` | 0 | All 529 critical invariant tests passed; no live boundary was invoked. |
| `mutation-on-touched-critical` | production `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | Exact result `[]`: `board.py` and its tests reach no configured critical mutation target. The Linux mutation job is therefore vacuous for this diff; no mutation result, target, baseline, threshold, or survivor change is claimed. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- core research live monitoring` | 0 | No trading, research, live, or monitoring production path changed; trading parity is not applicable. The full Linux suite remains deferred to the ready transition. |
| `live-money-review` | production diff plus `uv run python -m scripts.quality.review_selection R3 --base origin/main` | 0 | No live-money, runner, bridge, order, sizing, risk-limit, account, or methodology path changed or ran; the executable matrix selects `adversarial-code-reviewer` and `test-quality-reviewer` only. |
| `human-decision-escalation` | approved issue #138 scope and decision audit | 0 | Jan selected the single-item query, process-local immutable metadata cache, typed reset-time failure, partial-progress reporting, and no-retry boundary; no domain choice remains delegated. |
| `no-autonomous-merge` | `gh pr view 144 --json isDraft,autoMergeRequest` | 0 | Pull request remains draft and `autoMergeRequest` is null; Jan retains ready and merge authority. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-138 --base origin/main` | 1 | Correctly NOT READY on the independent-review record alone: the material fix at `6094ff2` requires a complete fresh Claude re-review before readiness can pass. |
| `security` | `just check-security` | 0 | Secret scan passed, pip-audit found no known vulnerabilities, and high-signal security Ruff passed. |
| `impact` | `just impact origin/main` | 0 | One production file and one directly related test file; no transitive test, critical escalation, or unknown dynamic edge. |
| `live-query-cost` | GraphQL allowance before/after `uv run python -m scripts.quality.board status 138` | 0 | The current query succeeded against GitHub's live schema, returned `Implementing` with `risk:R3`, and consumed exactly one GraphQL point (2,348 to 2,347) without mutation. |

## Coverage and mutation

Eight binding criteria were red before the implementation: AC-01 through AC-07 and INV-03.
INV-01 and INV-02 were already satisfied and are not misreported as red. Query-cost tests observed
the old `project view`/`field-list`/`issue view`/`item-list --limit 1000` path. The review regressions
then proved the D-01 type erasure and eight adjacent boundary gaps red before their fixes.

After the fix, status costs one issue-scoped GraphQL query for both a five-item and a 905-item
project. Project id, Status field id, and option ids load once per gateway; every label/status guard
still performs a fresh issue snapshot. `arm` and `start` retain initial, intermediate, and final
state reads. Every permit removal passes through `_remove_approved_and_verify`. Rate limits on reads
and all five write operations retain the typed error, completed-step list, and reset time; if the
failed response has no reset, exactly one non-retry `gh api rate_limit` lookup supplies it. GraphQL
error types and REST remaining-zero headers precede English-text classification. A truncated label
or project-membership connection fails closed rather than deciding from incomplete state. A project
item with a null Status is reported as `unset`, not absent.

The production mutation selector returned no targets. This is applicability evidence, not a
mutation-run claim: no configured target, policy, baseline, threshold, or survivor classification
changed.

## Deferred checks

- Complete independent Claude adversarial-code and test-quality re-review remains required on
  material head `6094ff2`. No builder-authored review verdict is claimed.
- Linux `full-quality` has not run. It is conditional on the ready transition; the full local
  1,736-test result is Windows evidence and is not presented as Linux parity.
