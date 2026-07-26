# Evidence

## HEAD

HEAD: 361424233b2db6d98d47635abb560c388cc15b92

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | R3: sizing, synchronized account-limit diagnostics, holdout reporting, and verdict paths changed |
| `red-first` | `uv run pytest -q` over the nine initial P-09 guards against `origin/main` | 1 | RED as required: all 9 failed because `simulate` had no synchronized `h4_prices` path or shared daily diagnostic object |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | 9 changed Python files formatted; Ruff and strict mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_docs_architecture_map.py tests/test_docs_language.py` | 0 | 132 passed |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 176 files, Vulture, and pytest passed; 1,091 passed and 1 Windows-only mutation test skipped |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | 475 direct/transitive tests passed; no unknown or possibly affected edge was discovered |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | 17 properties passed twice with seed `20260721` |
| `integration-tests` | Stage 3 and Stage 4 on `run_20260726_p09_v4`, plus full `just check` | 0 | Real entrypoints completed on the current baseline inputs; Stage 4 generated the report and correctly remained overall FAIL for cross-code lineage, contaminated holdout, and forced selection while the hard-limit check passed |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-09` | 0 | `Task P-09: valid (13 AC, 9 INV)` |
| `adversarial-review` | `.ai/tasks/P-09/review.md`, schema-checked by `validate_task P-09` | 0 | 15 temporal/cost/path counterexamples attempted; F1-F3 resolved, legacy chronological-HWM issue isolated to follow-up #91, no unresolved in-scope P0-P3 finding |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | 222 passed, including live-risk, synchronized H4, sizing, drawdown, and regression invariants |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30212102398` on `361424233b2db6d98d47635abb560c388cc15b92` | 0 | GREEN: weakened-test probe and exact ratchet passed; 3,216/3,574 killed, 358 exactly classified survivors, score 0.8998 versus prior 0.8992 |
| `parity-where-applicable` | `uv run python -m research.regression --issue 35 --pair reports/research/run_20260724_1146=reports/research/run_20260726_p09_v4 --out reports/research/regression/35-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | Empty `unexpected_changes`; 1,348 to 1,348 trades, 40.6% to 40.6% annual return, 60.8% to 60.8% total return, and byte-identical trade artifacts |
| `live-money-review` | `git diff --quiet origin/main...HEAD -- live` plus signal/Stage-1 producer diff audit | 0 | No live, order, signal, Stage-1 trade-production, cost, stop, or tail logic changed; no runner was touched |
| `human-decision-escalation` | spec/issue decision audit | 0 | Jan's corrected baseline, synthetic fixture, exact zero regression tolerances, and same-H4 upper-bound decision were followed; no P-09 methodology question remains open |
| `no-autonomous-merge` | branch and PR-state audit | 0 | Feature branch only; merge and auto-merge remain disabled |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and static security checks passed |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | R3; six production paths, eleven directly related tests, twenty-one transitive tests, three critical escalations, no unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-09 origin/main` | 0 | READY: task schema, R3 classification, required gates, and current evidence passed |

## Red-first proof

The initial nine P-09 tests were run against `origin/main` before implementation and failed 9/9:
the old `simulate` API had no `h4_prices` input, no `DailyDiagnostics`, and still accepted
whole-loss-day `adverse` arrays.

The first implementation at `699337f` exposed a second red boundary proof:

`uv run pytest -q tests/test_research_h4_path.py::test_trade_uses_only_h4_observations_inside_its_lifetime tests/test_research_h4_path.py::test_disjoint_lifetimes_inside_one_h4_bar_are_not_summed`

It failed 2/2: a 13:00 entry was charged the wrong bar (`60,000` rather than `99,800`), and
disjoint lifetimes inside one H4 bar did not obtain valid observations. The half-open interval
replay split at every event makes both tests green. Linux mutation runs then supplied executable
RED evidence for remaining reset, direction, daily-limit, realization, swap, and diagnostic-field
boundaries before the final ratchet passed.

## Numerical regression

The real rerun is `reports/research/run_20260726_p09_v4`, derived from baseline
`run_20260724_1146`. Stage 3 used forced `no_bb_wpr`,
`--fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full`; Stage 4 ran
against that publication.

- Trade count: `1348 -> 1348` exactly.
- Annual return: `40.6% -> 40.6%` exactly.
- Total return: `60.8% -> 60.8%` exactly.
- Worst-day R: `-11.02R -> -11.02R`; tail cap: `0.1816% -> 0.1816%`.
- Flat max drawdown: `-4.14% -> -3.30%` (the permitted path change).
- Maximum synchronized daily loss: `2.27%`; hard daily/trailing breach days: `0/0`.
- Stage 3, verdict, and fact-sheet holdout-flat max drawdown are all `-3.30%`.
- `portfolio_trades.csv` is byte-identical at SHA-256
  `B5A0A9BB6D19CCEE85C35AA6570A3BD67EA8FD885665D92901E5F14113F45129`.
- `full_history_trades.csv` is byte-identical at SHA-256
  `27592D20DDA0FB3B31EB06DE69D4D760D0F16CD961F2872E4F6376ACB3DD90DC`.
- `reports/research/regression/35-comparison.json` has exact zero tolerances and an empty
  `unexpected_changes` list.

The current baseline's real 2025-04-10 positions do not reproduce the retired structure: all six
are shorts, but only USDJPY is profitable at about `+2.00R`; the other five are near `-1R`.
Accordingly, the required six-short/four-winner structure is exercised deterministically in
`test_synthetic_retired_six_short_day_replaces_impossible_breach`: the legacy whole-day mark is
`3.20%`, the synchronized result is `0.37%`, the day closes up, and no 3% daily breach occurs.

## Coverage and mutation

`tests/test_research_h4_path.py` contains 41 focused guards covering exact entry/exit boundaries,
disjoint and concurrent lifetimes, the Chicago reset, asynchronous-market carry, long/short and
legacy direction, Decimal span boundaries, swap-once realization, missing/invalid H4 inputs,
daily/trailing strictness, the synthetic retired structure, and exact non-path parity. Fact-sheet
and policy integration tests prove the shared object is consumed on the real reporting path.

Linux run `30212102398` passed the self-test and exact survivor ratchet at 0.8998. P-09 added 429
selected mutants while increasing killed mutants from 2,828 to 3,216. The pre-existing close-path
`simulate` gap tightened from 35 to 21 survivors; every P-09 survivor is individually classified
as an exact dtype/schema/control-flow equivalent or a display-only/fallback-only irrelevant
variant.

## Deferred checks

None for P-09. Tick/M1 bid-ask fills and within-H4 sequencing remain in backlog issue #55 (the
residual scope formerly tracked by #24). Chronological intraday drawdown HWM ordering is isolated
to #91 because P-09 was required to preserve the existing HWM convention.
