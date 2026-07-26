# Evidence

## HEAD

HEAD: 05a5fd6f966844e9153d363620ec25160ea64fac

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uvx --from rust-just just impact origin/main` | 0 | R3: five research production paths, reported-result computation, Stage-4 verdict input, and critical mutation policy |
| `red-first` | `uv run pytest -q tests/test_research_scenarios.py` against `origin/main` | 1 | RED during collection: `ModuleNotFoundError: research.portfolio.scenarios` |
| `mutation-red-first` | Linux Critical mutation runs `30221165984`, `30221898816`, and `30222448165` | 1 | RED: the old ratchet rejected the new target; 79 initial scenario survivors were reduced by exact behavioural boundary tests before baseline review |
| `mutation-stability-red-first` | Linux Critical mutation run `30222908161` | 1 | RED: equivalent P-04 `stationary_bootstrap mutmut_44` alternated to survived; the exact ratchet exposed the nondeterministic no-op |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: all 8 changed Python files formatted; Ruff and strict mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_docs_language.py` | 0 | GREEN: 133 documentation, architecture-map, language, and engineering guards passed |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 178 files, Vulture, and pytest passed; 1,127 passed and one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: 524 direct/transitive tests passed; no unknown/dynamic edge was discovered |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: 18 deterministic properties passed twice with Hypothesis seed `20260721` |
| `integration-tests` | Stage 3 `research.stages.portfolio` and Stage 4 `research.stages.verdict` on `run_20260726_p10`, plus full `just check` | 0 | GREEN: real entrypoints completed; Stage 4 consumed 548 complete scenario days and remained FAIL only for pre-existing lineage/holdout/forced-selection reasons |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-10 --base origin/main` | 0 | GREEN: `Task P-10: valid (13 AC, 8 INV)` |
| `adversarial-review` | `.ai/tasks/P-10/review.md`, schema-checked by `validate_task P-10` | 0 | GREEN: 16 calendar, accounting, bundle, lineage, mutation, and gate-isolation counterexamples attempted; F1-F8 resolved |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: 255 live-risk, H4-path, sizing, scenario, regression, and workflow invariants passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `30223782263` on `e5ab3117f6a9800b8215e9530bdbb8c787b7a606` | 0 | GREEN: weakened-test probe and exact ratchet passed; 3,559/3,923 killed, 364 exactly classified survivors, score 0.9072 versus 0.8998 |
| `parity-where-applicable` | `uv run python -m research.regression --issue 51 --pair reports/research/run_20260726_p09_v4=reports/research/run_20260726_p10 --out reports/research/regression/51-comparison.json --trade-count-pct 0.0 --annual-return-pp 0.0` | 0 | GREEN: empty `unexpected_changes`; 1,348 trades and 40.6% annual return exact; both trade artifacts byte-identical |
| `live-money-review` | `git diff --quiet origin/main...HEAD -- live` plus signal/order/risk diff audit | 0 | GREEN: no `live/**`, signal, order, account, risk-limit, P-09 diagnostic, trade-generation, or sizing-policy path changed; no runner was touched |
| `human-decision-escalation` | issue/spec decision audit | 0 | GREEN: Jan's schema, calendar axis, joint resampling, production seed/count, fixed sensitivities, zero regression tolerances, and no-new-gate boundary were followed; no methodology question remains open |
| `no-autonomous-merge` | branch and PR-state audit | 0 | GREEN: feature branch only; merge and auto-merge remain disabled |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: secret scan clean, `pip-audit` found no known vulnerabilities, and static security checks passed |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | GREEN: R3; five production paths, fifteen direct tests, twenty-one transitive tests, one critical escalation, no unknown/dynamic edge |
| `pr-ready` | `uvx --from rust-just just pr-ready P-10 origin/main` | 0 | GREEN: READY; task schema, R3 classification, all required gates, review, and current evidence passed |

## Red-first proof

Before implementation, the complete focused file was run against `origin/main`:

`uv run pytest -q tests/test_research_scenarios.py`

Pytest failed during collection because `research.portfolio.scenarios` did not exist. The
acceptance oracle therefore could not construct a complete calendar-day scenario, retain a real
zero-trade day, reject an independently shuffled field, or produce a fixed-horizon path.

Linux mutation then supplied executable second-stage RED proofs. Run `30221165984` rejected the
unregistered target with 79 unexplained scenario survivors. Runs `30221898816` and `30222448165`
showed which accounting predicates, exact loss-day diagnostics, seed forwarding, same-day
aggregation, CSV failure paths, and joint-bundle boundaries were not yet observable. Targeted
tests killed 71 of the 79; the remaining seven scenario mutants are explicitly classified.

Run `30222908161` exposed a separate exact-ratchet instability: NumPy
`Generator.integers(0, high, ...)` and `Generator.integers(high, ...)` are the same API call, but
the equivalent P-04 mutant alternated between killed and survived under runner load. The redundant
argument was removed, and an independent 10,000-path comparison produced byte-identical arrays
with SHA-256
`e998aa659f6505bbf01eca1ea16840b5d94bff4d8265ce0da07b949f8e738785`.
Adjacent-date validation now uses `itertools.pairwise`, removing two further exact zip-default
mutants rather than tolerating them. Final Linux run `30223782263` passed on its own merits.

## Numerical regression

The real rerun is `reports/research/run_20260726_p10`, derived from current P-09 baseline
`run_20260726_p09_v4`. Stage 3 used forced `no_bb_wpr`,
`--fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full`; Stage 4 ran
against the published scenario artifact. The P-09 reference predates P-08's additive complexity
table, so validation used the reference's byte-identical robustness config
(`BA1F994E9438BE2E0F7772F1294CE4A54370ED08A363FAD09FAF62DDC2EF349E`) in an isolated worktree.
Forced selection makes that table irrelevant, and provenance was not falsified.

- Scenario rows: `548`, including `167` observed zero-trade days.
- Plug-in block length: `3`; production simulations: `10,000`; seed: `20260719`.
- `P(profit)`: `100.0% -> 100.0%` (delta `0.0 pp`); plug-in and fixed 5/10/20/60 sensitivities
  are all `100.0%` on this sample.
- Trade count: `1348 -> 1348`; annual return: `40.6% -> 40.6%`; total return:
  `60.8% -> 60.8%`.
- Hit rate, profit factor, payoff, expectancy, Sharpe, maximum drawdown, maximum daily loss,
  worst-day R (`-11.02R`), and tail cap (`0.1816%`) are exact.
- `portfolio_trades.csv` is byte-identical at SHA-256
  `B5A0A9BB6D19CCEE85C35AA6570A3BD67EA8FD885665D92901E5F14113F45129`.
- `full_history_trades.csv` is byte-identical at SHA-256
  `27592D20DDA0FB3B31EB06DE69D4D760D0F16CD961F2872E4F6376ACB3DD90DC`.
- `reports/research/regression/51-comparison.json` has exact zero tolerances and an empty
  `unexpected_changes` list.

The overall verdict correctly remains FAIL because the copied validation run crosses code
lineage, the reserved holdout is already declared contaminated, and selection was forced. Those
pre-existing failures are not P-10 gates; the hard limits, positive return, tail cap, and unchanged
`P(profit) >= 0.60` check all pass.

## Coverage and mutation

`tests/test_research_scenarios.py` contains 33 focused guards covering exact daily accounting,
Chicago-grid continuity, zero-trade frequency, H4-diagnostic provenance, multi-close aggregation,
Decimal CSV round-trip, joint-field identity, fixed horizon, source-index integrity, strict-profit
semantics, seed forwarding, all five block sensitivities, malformed artifacts, and real Stage-3/4
wiring. The deterministic property suite generates additional horizons, block lengths,
replication counts, seeds, and exact Decimal rows.

Final Linux run `30223782263` passed the weakened-test self-check and exact survivor ratchet:
3,559 killed of 3,923 selected mutants, 364 individually explained survivors, no timeout,
uncovered, suspicious, interrupted, or crashed mutant, and score `0.9072`. P-10 raises the prior
score of `0.8998`; no tolerance or threshold was weakened.

## Deferred checks

None for P-10. P-11/#52 exclusively owns any future scenario daily/trailing breach gate; P-10
changes no threshold, selection rule, or verdict criterion.
