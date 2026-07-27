# Test plan

| Requirement | Red-first oracle | Required green result |
|---|---|---|
| AC-01 | single H4 dip then profitable close | `-1.00%`, never `-10.00%` |
| AC-02 | two H4 intervals, first closes at a new high | later `109000` minimum uses `110000` HWM; result `-0.91%` |
| AC-03 | real policy result through portfolio/verdict/fact-sheet surfaces | all deterministic flat values identical |
| AC-04 | one sampled scenario with an intraday dip and later high close | sampled drawdown uses prior HWM; result `1%` |
| AC-05 | compare diagnostics before/after on unchanged fixture | daily loss/breach/trailing arrays exact |
| AC-06 | same-day realized high fixture | actual trailing gate flag remains true |
| AC-07 | same fixture through sampled summary and verdict JSON | current versus chronological raw/bound values both present; actual gate reads current |
| AC-08 | zero-tolerance real-run regression and SHA-256 | no unexpected changes; both trade CSVs identical |
| AC-09 | cumulative workflow | every R3 gate has current-HEAD evidence |

## Red-first procedure

Add the H4 and path-risk boundary tests before changing production code. Run their exact node IDs
against current `main`; both current implementations must fail with the look-ahead values. Record
the command, exit status, and observed/expected values in `evidence.md`.

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
