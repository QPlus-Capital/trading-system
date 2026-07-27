# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_drawdown_does_not_use_a_later_profitable_close_as_its_peak` | RED: `-10.00%` | GREEN: `-1.00%` |
| AC-02 | `test_drawdown_uses_an_observable_h4_high_before_a_later_minimum` | RED: `-9.09%` | GREEN: later `109000` minimum uses `110000` HWM: `-0.91%` |
| AC-03 | real Stage-3/4 regression plus `test_fact_sheet_reuses_the_verdict_flat_daily_diagnostics` and verdict integration | No chronological cross-surface oracle | Portfolio/verdict stats/verdict path/fact sheet share the authoritative policy result |
| AC-04 | two `test_path_drawdown_*` ordering cases | RED: `10%` and `9.09%` | GREEN: `1%` in both cases |
| AC-05 | real artifact hashes plus H4/sizing suites | No coupled chronology guard | Daily loss/breach/trailing and scenario CSV exact |
| AC-06 | `test_same_day_balance_high_raises_the_conservative_trailing_floor` | Existing gate behaviour only | Gate flag remains true; chronological flag separately false in fixture |
| AC-07 | `test_summary_reports_all_metrics_and_all_p10_block_choices`, Stage-4 integration | No paired output | Both raw/bound values present; actual gate reads current convention |
| AC-08 | issue-91 regression and SHA-256 comparison | No issue-91 artifact | Zero-tolerance GREEN; both trade CSVs identical |
| AC-09 | cumulative commands in evidence | Implementation absent | All local gates pass; Linux mutation explicitly infrastructure-blocked |
| INV-01 | mypy plus H4/path-risk tests | No new Decimal path | Decimal boundaries and exact bound retained |
| INV-02 | synchronized H4 fixture suite | Existing same-H4 upper bound | Same upper-bound marks, chronological peaks |
| INV-03 | daily-loss and scale properties | Existing opening balance rule | Daily rule exact and unchanged |
| INV-04 | conservative/chronological paired trailing test | One convention only | Gate convention exact; paired diagnostic separate |
| INV-05 | internal/prop property and invariant suites | Existing dominance only | Both conventions fail closed on dominance |
| INV-06 | fact-sheet and real-verdict integration | Shared minimum but biased HWM | All deterministic surfaces share corrected result |
| INV-07 | `git diff --exit-code origin/main...HEAD -- live core/strategies` | No issue change | No live/signal diff and no live invocation |

## Red-first procedure

The four exact node IDs were run before production changes and all failed with the values above.
The implementation also exposed and fixed a pre-entry stale-market-close peak, covered by its own
boundary-entry regression.

## Integration and parity

- Exercise `evaluate_policy` and the real Stage-4 entrypoint.
- Assert `portfolio.json.max_drawdown_pct`,
  `verdict.json.stats.max_drawdown * 100`, `verdict.json.path.max_drawdown_pct`, and the holdout-flat
  fact-sheet value derive from the same `PolicyResult`.
- Rerun Stages 3 and 4 on the current baseline with the baseline's exact fixed/risk/stress/tail
  arguments.
- Run issue-91 regression with `--trade-count-pct 0.0 --annual-return-pp 0.0`.

## Mutation focus

Mutate HWM update order, interval/minimum comparison, daily fallback order, close-event observation,
sampled-path HWM order, alternative trailing HWM order, probability counts, serialization, and gate
wiring. Any unexplained survivor blocks.

## Statistical checks

- Reuse exact `clopper_pearson_upper`; do not add another interval estimator.
- The current and alternative convention counts use identical sampled paths, horizon, block length,
  replications, and seed, so their difference is paired and deterministic.
- Production measurement remains 10,000 replications at the registered seed.
