# Impact analysis

## Coupled quantity

The coupled quantity is the drawdown equity HWM and every minimum evaluated against it. The complete
producer/consumer chain is:

1. `research/portfolio/sizing.py::_synchronized_h4_minima` replays timestamped opens, closes, H4
   close observations, synchronized adverse interval marks, and realized swap-at-close.
2. `research/portfolio/sizing.py::_daily_diagnostics` packages the authoritative synchronized path
   in `DailyDiagnostics`; `DailyDiagnostics.max_drawdown_pct` exposes its chronological result.
3. `research/portfolio/risk.py::evaluate_policy` copies that value to
   `PolicyResult.max_drawdown_pct`.
4. `research/stages/portfolio.py::main` publishes it in `portfolio.json` and the Stage-3 table.
5. `research/stages/verdict.py::main` re-evaluates the same policy/H4 path, puts the same value in
   `stats.max_drawdown`, `verdict.json.path.max_drawdown_pct`, and supplies that same
   `PolicyResult` to the fact sheet.
6. `research/portfolio/factsheet.py::_money` reads `PolicyResult.max_drawdown_pct`; the holdout-flat
   cell reuses Stage 4's exact result rather than simulating independently.
7. `research/portfolio/html_report.py` and terminal rendering only display fact-sheet values.
8. `research/portfolio/scenarios.py` persists the same `DailyDiagnostics.minimum_equity` for P-10;
   it does not persist deterministic drawdown or construct another HWM.
9. `research/portfolio/path_risk.py::replay_scenario_path` repeats the HWM/minimum comparison over
   resampled P-10 days; `summarize_sampled_paths` derives drawdown percentiles consumed by Stage 4.
10. `research/stages/verdict.py` serializes and displays the P-11 drawdown percentiles.

Every consumer is covered in this package. Stage 1's return/drawdown selection metrics use a
different trade-window curve and are not consumers of the Stage-3 synchronized H4 quantity.

## Limit semantics kept separate

- Daily loss: `opening_balance - minimum_equity`, divided by that opening balance. Unchanged.
- Actual trailing gate: realized-balance HWM including same-day close, start-balance-anchored floor.
  Unchanged.
- Deterministic and sampled drawdown: chronological equity HWM. Corrected.
- Alternative trailing diagnostic: prior chronological balance HWM, measured separately and never
  substituted into the gate.

## Stage and artifact impact

- Stages 1 and 2 remain cached and valid.
- Stage 3 must rerun because `portfolio.json.max_drawdown_pct` is corrected; both trade CSVs and
  every non-path metric must remain exact.
- Stage 4 must rerun because deterministic drawdown, sampled drawdown percentiles, and the
  diagnostic-only trailing comparison change.
- `loss_day_scenarios.csv` schema and bytes are expected to remain unchanged.
- `path_bootstrap.json` and `verdict.json` gain labelled diagnostic-only chronological trailing
  fields.

## Expected numerical effect

- Deterministic max drawdown and P-11 drawdown percentiles can only improve or remain equal when
  removal of future peaks is the only change.
- Current trailing breach probabilities/bounds, daily breaches, final-return distribution,
  expected shortfall, time under water, trade count, returns, expectancy, Sharpe, and tail cap must
  remain exact.
- The alternative chronological trailing breach probability/bound is expected to be no greater
  than the current convention; its actual magnitude is data-dependent and must be measured.

## Critical dependencies

- P-09's synchronized H4 event/lifetime path remains authoritative.
- P-10's version-2 source-relative daily scenarios and P-04 stationary bootstrap remain unchanged.
- P-11's exact Clopper-Pearson implementation remains authoritative for both the gate and the new
  diagnostic bound.

## Failure modes

- Fixing only `DailyDiagnostics.max_drawdown_pct` while the H4 replay still loses intraday peak
  chronology.
- Fixing Stage 3 while P-11 replay retains the same future-close denominator.
- Correcting drawdown by changing the actual trailing HWM, silently moving a gate.
- Updating HWM from an H4 bar close before that close becomes observable.
- Tracking only the absolute daily minimum, which loses a higher peak before a later, higher
  minimum.
- Adding a helper that Stage 3/4/fact-sheet never consume.
- Reporting an alternative trailing number but accidentally gating on it.
- Letting a path-drawdown change mask any drift in returns, trade files, or tail sizing.

## Initial classification and impact

The explicit planned-path classifier returned R3 with all fourteen cumulative gates. Final
`just impact origin/main` output is recorded in evidence after the complete changed path exists.
