# Evidence

## HEAD

HEAD: 9b0d9bea6dbc1fb23edf2c4b4e79ad8293f47d89

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Ruff format/check and strict mypy passed; the impacted set passed 125 tests. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,240 passed, 1 skipped. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | One production file selected 9 direct and 2 transitive test files; 125 tests passed. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 21 property tests passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_parity_check.py tests/test_live_run_cli.py tests/test_live_runner.py tests/test_live_runner_cycle.py tests/test_monitoring_dashboard.py tests/test_monitoring_dashboard_copy.py tests/test_research_sizing.py tests/test_research_swap_analysis.py tests/test_signal_adapter_parity.py` | 0 | 125 tests passed through the bridge consumer set using synthetic fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Task schema, acceptance criteria, invariants, R3 declaration, and traceability are valid. |
| `adversarial-review` | `.ai/tasks/ISSUE-103/review.md` | 1 | **Outstanding:** mutation remediation materially changed the reviewed patch. The earlier review no longer covers the complete implementation; a fresh independent live-money review is required. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 325 critical invariant tests passed. |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30345100067`, then `MutationReport` / `load_baseline` / `check_baseline` against the retained report | 0 | Linux/Python 3.13 measured 4,909 mutants: 4,499 killed, 410 survived, 0 no-tests, and every other unhealthy status 0. The regenerated exact baseline accepts the retained report with no issues; the 410 survivor names are exactly main's pre-change survivor set. |
| `parity-where-applicable` | production diff audit plus SHA-256 comparison of `run_20260724_1146` trade CSVs | 0 | No research, signal, runner, risk-control, or monitoring behavior changed; both baseline trade artifacts remain byte-identical. |
| `live-money-review` | fake-only boundary proof plus `.ai/tasks/ISSUE-103/review.md` | 1 | Builder-controlled live-safety evidence is green, but the required fresh independent doubly-rigorous review is outstanding. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Jan's fail-closed rule, exact accepted values, five boundaries, synthetic-only constraint, and merge authority are explicit. |
| `no-autonomous-merge` | `git branch --show-current` plus PR state audit | 0 | Branch is `codex/issue-103-fail-closed-mt5-sides`; PR #105 remains draft, with no merge or auto-merge action. |

## Rebase and impact evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `rebase-current-main` | `git fetch origin main`; `git rebase origin/main`; `git merge-base HEAD origin/main` | 0 | Rebased before remediation onto required `main@8b75ff061c924e2dc415d70ad90700f79a15540c`. F-037 and merged F-038 were unioned in ID order. Mutation policy was unioned; the baseline was untouched until the single post-test regeneration. |
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3: the live broker boundary and quality policy/baseline change; all cumulative gates apply. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Exactly one changed production file; 9 direct and 2 transitive test files; no unknown/dynamic edge. |
| `registry` | registry ID audit across `origin/main` and open branches; `uv run pytest -q tests/test_finding_registry.py` | 0 | F-037 remains the issue finding. F-040 was free after reserving open-branch F-039 and now records the generalized mutation-coverage defect. Existing entries were not changed. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit reports no known vulnerabilities, and Ruff security checks passed. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-103 --base origin/main` | 1 | Correctly reports NOT READY on `adversarial-review` and `live-money-review` only. Mutation and every builder-controlled gate pass; the PR remains draft pending fresh independent review. |

## Red-first and mutation proof

The original production edit was absent when the invalid-side boundary tests first ran. Ten cases
failed because no `Mt5Error` was raised. After the first implementation, PR run `30339340183`
reported 38 branch-specific survivors:

- `Mt5Bridge.positions`: 14;
- `_runtime_side`: 3;
- `Mt5Bridge.place_order`: 10;
- `_order_type`: 1;
- `Mt5Bridge.close_position`: 6;
- `loss_for_order`: 1;
- `loss_to_stop`: 3.

The same run's two selected mutants with no covering test were:

- `live.mt5_bridge.xǁMt5Bridgeǁowned_positions__mutmut_1`;
- `live.mt5_bridge.xǁMt5Bridgeǁowned_positions__mutmut_2`.

Targeted fake-broker tests assert authoritative emitted position direction, exact symbol/filter
forwarding, direction-specific broker pricing arguments, complete entry/close request dictionaries,
and each boundary's full distinct failure message. They killed 33 of the 38 survivors and both
no-test mutants. The five remaining default-argument mutants were semantically meaningful and were
**not** classified: `_order_type` now requires explicit `opposite`, while unchanged public defaults
refer to module constants. This removes Mutmut's trampoline-default blind spot while leaving every
valid broker request unchanged. An isolated mutation replay confirmed those five mutant names no
longer exist.

No issue-103 survivor was classified. Final Linux run
[30345100067](https://github.com/QPlus-Capital/trading-system/actions/runs/30345100067) measured:

- total: 4,909;
- killed: 4,499;
- survived: 410;
- no tests: 0;
- skipped/suspicious/timeout: 0.

The workflow initially compared that report with the pre-remediation `4,646` baseline and therefore
exited on the intentionally stale total. The retained report was then used for the one permitted
wholesale regeneration. Replaying the repository comparator against that report and regenerated
baseline exits 0 with no issues. The survivor set is identical to main's 410 exact-name survivors:
zero added, zero newly classified, and zero formerly allowed survivors killed.

Ruff formatting after the measurement changed layout only. AST comparison proved the production
module and test behavior unchanged, and regenerating Mutmut names yielded the identical 581 names
for `live/mt5_bridge.py`; therefore the Linux measurement remains bound to the final code semantics.

## Numerical and artifact parity

The package changes only malformed-input refusal and testability at the live MT5 boundary. Legal
BUY/SELL behavior, prices, quantities, risk values, limits, request fields, and return values are
exact-pinned by the fake bridge tests. No Stage 1-4 producer or configuration is in the diff.

- `portfolio_trades.csv`:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv`:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

Both hashes remain byte-identical. No reported number moved.

## Live safety attestation

Every test replaces `live.mt5_bridge.mt5` with an in-memory fake. No command initialized or
connected MT5, inspected an account, restarted a runner, or placed, modified, or closed an order.
Neither running live runner was touched. Invalid inputs are additionally proven to leave pricing,
tick, filling, and order-send counters at zero.

## Coverage and mutation

The final deterministic suite has 1,240 passing tests, the impacted set has 125, the critical
invariant suite has 325, and 21 property tests pass twice at the fixed seed. Linux mutation has
4,499 of 4,909 mutants killed, 410 exact-name equivalent survivors inherited unchanged from main,
and zero no-test or other unhealthy results. This package adds no classified survivor and weakens
no target, test, threshold, comparison rule, risk limit, or live behavior.

## Deferred checks

The Linux mutation gate is complete and green. The sole substantive blocker is the fresh,
independent, doubly-rigorous live-money review required because the remediation materially changed
the previously reviewed patch. Jan retains the merge decision; PR #105 must remain draft.
