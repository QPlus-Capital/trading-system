# Impact analysis

## Coupled Stage-1 return inventory

The complete return path was traced before implementation. Every consumer below must receive the
same net trade stream; changing only one would create a plausible but internally inconsistent
study.

1. **Realized trade extraction**
   - Training: `research/engine/walkforward_runner.py::run_walkforward.optimize` currently calls
     `extract_trade_pnls`, losing open/close time, direction, entry, exit, and stop distance.
   - OOS chosen path and candidate matrix:
     `research/engine/continuous.py::closed_pnls` currently reduces the positions report to
     `(close timestamp, gross pnl)`.
   - Stage-3 re-optimization parity:
     `research/portfolio/trades.py::_optimize` independently scores the same training candidates.

2. **Training window return and parameter rank**
   - `walkforward_runner.run_walkforward.optimize` passes the trade outcomes to
     `walkforward.calmar_score`; the winning candidate's `equity_curve` supplies `is_return`.
   - `portfolio.trades._optimize` uses the same `calmar_score` for the non-fixed Stage-3
     re-optimizer. The fixed Stage-3 path skips it and must remain unchanged.

3. **OOS window return and market summary**
   - `continuous.window_returns` assigns each realized trade to the window containing its close,
     divides by the one constant basis, and supplies both total `oos_return` and per-trade
     `oos_returns`.
   - `continuous.continuous_walk_forward` derives `oos_trades` and `oos_max_dd` from that same
     per-trade stream.
   - `characterize._run_task` aggregates those results into `mean_oos_pct`,
     `oos_maxdd_pct`, `pct_profitable`, `worst_market_pct`, and `return_per_dd`.

4. **Sharpe, WFE, and multiple-testing streams**
   - `walkforward.walk_forward_efficiency` and `normalized_wfe` consume `is_return` and
     `oos_return`.
   - `characterize._run_task` exposes `window_oos`; `_write_reports` pools it into
     variation/candidate Sharpe and DSR inputs.
   - `continuous.continuous_walk_forward` fills `oos_by_combo`; `characterize.candidate_streams`,
     `candidate_pbo`, and `variation_pbo` use it for PBO/CSCV.

5. **Persisted study and return/drawdown ranking inputs**
   - `characterize._save_csv` writes the net-derived task aggregates to `study.csv`.
   - `characterize._write_reports` aggregates `mean_oos_pct`, `oos_maxdd_pct`,
     `return_per_dd`, `pct_profitable`, and WFE into `ranking.csv`.
   - `stages.universe.per_config` converts `mean_oos_pct` and `return_per_dd` into `mean_ret`,
     `mean_rpd`, `worst_rpd`, and `frac_positive`.
   - `stages.edge.ranking`, `stages.select`, and `stages.universe.select_structure` consume those
     columns for eligibility and return-first selection. They require no separate cost logic:
     their inputs must already be net.

6. **Lineage**
   - `research/stages/lineage.py::external_inputs` already defines the canonical content hash for
     the `standard_broker()` swap snapshot.
   - `characterize.main` currently writes only catalog-at-seed metadata. A directly generated
     study must also write provenance binding its result artifacts to the pre-run swap snapshot.

## Direct impact

- Negative carry lowers training Calmar, in-sample return, OOS return, Sharpe, WFE, DSR inputs,
  PBO candidate streams, and return/drawdown scores according to each candidate's actual holding
  duration.
- Positive short-index carry increases the affected trade's net R with the sign already defined
  by `swap_r_per_trade`.
- Candidate parameters, variation/train-length ranking, and the selected universe may change
  after the deferred full Stage-1 run.

## Transitive impact

- `study.csv`, `ranking.csv`, `ranking_by_train.csv`, `overfitting.json`, `edge_ranking.csv`, and
  `selection.json` can change when the validation study is eventually rerun.
- Any later non-fixed Stage-3 extraction can choose training parameters consistently with Stage 1.
- The current fixed Stage-3 portfolio, tail, sizing, verdict, monitoring, and live paths do not
  consume the changed training optimizer and must remain numerically unchanged.

## Critical dependencies

- `core.broker.standard_broker`, `swap_r_per_trade`, `night_units`, and
  `swap_per_lot_night` are the sole snapshot, rollover, direction, and sign convention.
- `research.portfolio.trades.timed_trades_from_report` supplies explicit trade direction and the
  close-time realization seam.
- P-02's `flatten_on_stop=False` remains on both training configs, so only genuinely closed trades
  can receive swap and enter a score.
- P-02's constant `sizing_equity` basis remains the denominator for gross and swap-adjusted
  Stage-1 returns.
- `lineage.external_inputs` and `write_provenance` bind the generated study to snapshot content,
  config, raw bars, catalog sources, broker code, and producer git state.

## Unknown or dynamic edges

- The numerical movement and any ranking flips are intentionally unknown before the deferred
  nine-hour run.
- A snapshot can contain positive carry on some short index trades; therefore the direction
  guarantee is per trade/candidate conditional on carry sign, not an unconditional aggregate
  decrease.
- The pre-run regression thresholds are unresolved methodology decisions and are explicitly
  outside this code package.

## Deliberately unchanged paths

- Stage-3 fixed extraction, swap attachment, portfolio curves, tail, sizing, stress, fact sheet,
  and verdict calculations.
- `research/regression.py`, all `reports/` and `results/` artifacts, live code, signal code,
  monitoring code, account/risk limits, and broker snapshot contents.

## Tool result

The pre-code `just impact origin/main` run sees only this task artifact and therefore reports R0
with no production dependency edges. Planned-path classification is R3 for `characterize.py`,
`config.py`, `continuous.py`, `walkforward_runner.py`, and `portfolio/trades.py`, requiring all
cumulative R3 gates. The final tool run must classify the actual implementation diff and will be
recorded after it exists; the explicit coupled-quantity inventory above remains authoritative for
runtime/statistical edges that static imports cannot prove.
