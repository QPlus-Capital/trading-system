# Evidence

## HEAD

HEAD: 5d35026e07c7e97493fb44a61e8d895316435fc7

The only later commit permitted by readiness is this evidence file itself.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | Both changed Python files were already formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 tests passed. |
| `check` | `uvx --from rust-just just check` | 0 | Post-#98 rebase: Ruff, strict mypy over 180 files, Vulture, and 1,210 tests passed; one Linux-only mutation test was correctly skipped on Windows. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | The committed R3 diff selected and passed 108 bridge, runner, account, parity, monitoring, research-sizing, and swap-analysis tests. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | Post-#98 rebase: 21 properties passed twice at fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_parity_check.py tests/test_live_run_cli.py tests/test_live_runner.py tests/test_live_runner_cycle.py tests/test_monitoring_dashboard.py tests/test_monitoring_dashboard_copy.py tests/test_research_sizing.py tests/test_research_swap_analysis.py` | 0 | 108 tests passed through the complete bridge consumer set using synthetic fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Task schema, nine acceptance criteria, seven invariants, R3 declaration, traceability, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Twelve counterexamples remain resolved; range-diff proves the rebase changed no live implementation or test behaviour. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | Post-#98 rebase: 316 critical invariant tests passed, including live risk, account identity, parity, sizing, path risk, regression, and readiness. |
| `mutation-on-touched-critical` | Linux Critical mutation workflow | 1 | **Blocked by infrastructure:** the Actions allowance for this organisation is exhausted until 2026-08-01. Mutmut requires Linux/fork; this local run is the evidence, no mutation result is claimed, no survivor is classified without measurement, and no baseline or gate was weakened. |
| `parity-where-applicable` | non-target production diff audit plus SHA-256 comparison of `run_20260724_1146` trade CSVs | 0 | No research, core, monitoring, runner, risk-control, account, config, preflight, parity, or notification path changed. The two trade artifacts retain their baseline hashes exactly. |
| `live-money-review` | focused zero-call boundary tests, complete consumer integration set, and `.ai/tasks/ISSUE-103/review.md` | 0 | Every invalid value stops before terminal pricing/order calls; valid requests are exact-pinned. MT5 was never initialized or connected and neither running runner was touched. |
| `human-decision-escalation` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-103 --base origin/main` | 0 | Jan's fail-closed rule, exact values, five boundaries, synthetic-only safety constraint, draft-only delivery, and merge authority are explicit; no live-money decision remains delegated. |
| `no-autonomous-merge` | `git branch --show-current` plus PR delivery-state audit | 0 | Feature branch `codex/issue-103-fail-closed-mt5-sides`; draft PR only, with no ready, merge, or auto-merge action. |

### Additional evidence

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify $(git diff --name-only origin/main...HEAD)` | 0 | R3 because the broker bridge and quality registry/policy change; all fourteen cumulative gates apply. |
| `red-first` | `uv run pytest -q tests/test_live_mt5_bridge.py -k "fail_closed_on_unknown or fails_before"` before the production edit | 1 | Ten expected failures: three unknown position types and seven invalid pricing/entry/close sides all reported `DID NOT RAISE Mt5Error`. |
| `focused-green` | `uv run pytest -q tests/test_live_mt5_bridge.py` | 0 | 25 tests passed: invalid values leave all pricing/tick/filling/order counters at zero; valid BUY/SELL records and request dictionaries remain exact. |
| `registry-and-policy` | policy union audit plus `uv run pytest -q tests/test_finding_registry.py tests/test_quality_mutation.py` | 0 | Finding F-037 is unique; mutation policy retains main's history-deal pattern plus all issue-103 boundaries; mutation baseline unchanged. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | Exactly one changed production file; eight direct and two transitive test files; no unknown/dynamic edge or additional possible test discovered. |
| `security` | `uvx --from rust-just just check-security` | 0 | Post-#98 rebase: secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `post-119-rebase` | `git rebase origin/main` plus baseline/scope audit | 0 | Rebased onto `main@1815baa`; branch carries #119's `4,568`-mutant, 417-survivor exact baseline unchanged. No survivor was classified and no baseline file is in the branch diff. |
| `rebase-integrity` | `git range-diff 8263206..03662f2 8851b91..HEAD`; TOML structural-union audit; mutation-baseline diff | 0 | Live/test patches remain equivalent; F-035/F-037 are unique and ordered; every mutation target/pattern from main and the old branch remains; `.ai/quality/mutation-baseline.toml` is unchanged. No behavior changed. |
| `post-98-rebase-integrity` | `git range-diff 8851b91..acb4581 494eafc..HEAD`; TOML structural-union audit; mutation-baseline diff | 0 | Live/test patches remain equivalent; F-035/F-036/F-037 are unique and ordered; every mutation target/pattern from main and the old branch remains; `.ai/quality/mutation-baseline.toml` is unchanged. No behavior changed. |
| `artifact-hashes` | `Get-FileHash -Algorithm SHA256 reports/research/run_20260724_1146/{portfolio_trades.csv,full_history_trades.csv}` | 0 | `portfolio_trades.csv` remains `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`; `full_history_trades.csv` remains `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`. |
| `check-timeout-diagnostic` | initial `uvx --from rust-just just check` invocation with a 180-second host-tool cap | 124 | The host tool terminated the command at its time limit without a reported test failure. The identical command was rerun with sufficient time and passed as the required `check` record above. |
| `pr-ready` | `uv run python -m scripts.quality.pr_ready ISSUE-103 --base origin/main` | 1 | NOT READY on `mutation-on-touched-critical` alone, as required while Linux evidence is unavailable. |

## Red-first proof

The production edit was absent when the five new invalid-boundary guards first ran. Pytest expanded
them to ten cases and exited 1: the old `positions()` emitted SELL for unknown enum values; the two
pricing methods selected SELL; `place_order()` constructed a SELL entry; and `close_position()`
constructed the opposing BUY close. None raised.

After implementation, the same cases raise `Mt5Error`. The fake terminal records zero
`order_calc_profit`, `symbol_info_tick`, `symbol_info`, and `order_send` calls. Separate legal
fixtures pin both position enums, same-side pricing, entry bid/ask selection, complete entry
requests, opposing close types, close bid/ask selection, complete close requests, and return
values.

## Numerical and artifact parity

This package changes only malformed-input behavior in `live/mt5_bridge.py`. No valid signal, side,
price, quantity, risk amount, limit, request field, or result changes. No Stage 1-4 producer or
configuration is in the diff, so no research stage was rerun.

The current baseline artifacts were hashed before and after the package:

- `portfolio_trades.csv`:
  `b5a0a9bb6d19ccee85c35aa6570a3bd67ea8fd885665d92901e5f14113f45129`;
- `full_history_trades.csv`:
  `27592d20dda0fb3b31eb06de69d4d760d0f16cd961f2872e4f6376acb3dd90dc`.

Both remain byte-identical. No reported number moved.

## Live safety attestation

All new tests replace `live.mt5_bridge.mt5` with an in-memory fake and set connection state only on
the test-local bridge. No command imported the real terminal package for use, called `connect()` or
`initialize()`, inspected an account, restarted a process, or placed, modified, or closed an
order. Neither running live runner was touched.

## Coverage and mutation

The post-#119 invariant suite has 316 passing tests, the complete deterministic suite has 1,210, and
21 properties pass twice with the fixed seed. Range-diff shows the bridge/test implementation patch
is unchanged, so the prior 25-test bridge and 108-test impact evidence remains applicable. Coverage
includes all five issue-defined runtime boundaries, both legal directions, unknown integer/string
values, and Python's boolean/integer alias.

The critical mutation policy now includes the shared side converter, centralized order-type
mapping, and all five boundary methods while retaining the existing history-deal target. The branch
inherits #119's measured `4,568`-mutant, 417-survivor baseline unchanged. Linux Critical mutation is
**blocked by infrastructure — Actions quota exhausted until 2026-08-01**; no branch-specific
survivor classification or baseline regeneration is claimed.

## Deferred checks

Only the Linux Critical mutation gate and subsequent independent Claude review/Jan decision remain.
On quota reset, push an empty commit to retrigger Linux mutation, reconcile the exact baseline if
required, update this evidence, rerun `pr-ready`, and only then consider marking the PR ready.
