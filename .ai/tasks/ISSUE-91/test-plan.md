# Test plan

| Requirement | Before-fix RED | After-fix result |
|---|---|---|
| AC-01 | `-10.00%` | `-1.00%` |
| AC-02 | `-9.09%` | later `109000` minimum uses `110000` HWM: `-0.91%` |
| AC-03 | no chronological surface oracle | portfolio/verdict stats/verdict path/fact sheet share the policy result |
| AC-04 | `10%` for the same-day fixture and `9.09%` with a prior-day high | `1%` in both cases |
| AC-05 | no coupled chronology guard | daily loss/breach/trailing arrays and scenario CSV remain exact |
| AC-06 | existing conservative fixture | actual trailing gate flag remains true |
| AC-07 | no paired trailing convention output | both raw/bound values present; gate reads only current convention |
| AC-08 | no issue-91 artifact | zero-tolerance regression green; both trade CSVs identical |
| AC-09 | implementation absent | every locally runnable R3 gate passes; Linux mutation is explicitly infrastructure-blocked |

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
