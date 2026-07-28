# Impact analysis

## Direct impact

- `research/engine/continuous.py::window_returns` loses only the cumulative-equity/account-exhaustion
  branch. Attribution and division by the constant basis remain unchanged.
- `tests/test_research_continuous_windows.py` replaces compounding-ruin expectations with
  basis-relative scoring guards at and below cumulative `-basis`.
- `.ai/quality/finding-patterns.toml` records the generalized coupled-quantity defect required by
  constitution section 14.

## Transitive impact

The complete Stage-1 running-equity/ruin chain is:

1. `scoring_params` injects the recipe's start balance as Decimal `sizing_equity` into every
   training and continuous OOS backtest. This remains the sole position-size basis.
2. `stage1_trade_returns(..., fixed_basis=True)` converts each realized money PnL to gross `r`
   against that unchanged basis; swap stays separate and `net_r` is derived.
3. `stage1_account_returns` converts `net_r` to dimensionless basis-relative account returns, and
   `stage1_close_events` timestamps them.
4. `window_returns` is the sole window scorer. It currently sums all earlier events into a
   synthetic running equity only to raise at `<= 0`; it separately and correctly divides current
   events by the fixed basis.
5. `continuous_walk_forward` calls `window_returns` first for the chosen scheduled path and again
   for every inner grid combination when `collect_matrix=True`. Both paths are fixed in one edit.
6. Each returned `WalkForwardResult` carries basis-relative OOS return, trade returns, per-window
   max drawdown, and inner-combination scores. Per-window `equity_curve(..., 1.0)` remains only a
   drawdown measurement and does not drop a result.
7. `walkforward_runner.optimize` uses basis-relative `stage1_account_returns` and
   `calmar_score(..., 1.0)` for training selection. Its cumulative curve measures return and
   drawdown; it contains no ruin exception and remains unchanged.
8. `characterize._run_task` aggregates complete window results into return, drawdown, WFE,
   candidate-window events, and combo streams.
9. `characterize.main` catches a task exception and emits an `error` row. Removing the sole ruin
   exception means the two XAGUSD tasks reach `_run_task`'s normal numeric result path; genuine
   engine/data errors still fail into explicit error rows.
10. `characterize._save_csv` persists task rows. `_write_reports`, Stage 1 edge ranking, and Stage 2
    currently drop/mark incomplete error rows; they now receive the two numeric cells instead.
11. P-03 candidate streams and DSR/PBO/SPA/Romano-Wolf/MCS inputs can include the restored evidence
    on a future full Stage-1 rerun. No statistic or selection rule changes in this package.

There is exactly one account-exhaustion producer: `window_returns`. Repository search finds no
other Stage-1 running-balance viability check. The error-row machinery remains because it is the
correct fail-closed path for actual execution/data failures, not for valid negative candidates.

## Critical dependencies

- `research/engine/continuous.py` is registered in
  `.ai/quality/critical-dependencies.toml` with continuous-window, integration, and
  candidate-matrix coverage.
- The Linux mutation target `continuous-attribution` covers `window_returns`; no baseline is
  changed without a real Linux run.
- P-01 canonical net returns and P-02 non-flattening training boundaries remain authoritative.
- P-03 candidate persistence consumes the returned net event stream without recomputation.

## Unknown or dynamic edges

The real candidate verification crosses NautilusTrader and process boundaries, which static impact
analysis cannot prove. It runs `_run_task` directly on the frozen robustness config, broker
snapshot, and local XAGUSD data for the exact two affected candidates. The full 432-task process
pool is intentionally not rerun because 430 task paths are unchanged.

## Coupled quantity

The coupled quantity is the Stage-1 accounting basis:

- size: constant Decimal `sizing_equity`;
- gross return: fixed-basis `r`;
- statistical return: fixed-basis net account return;
- window denominator: the same fixed basis;
- training/OOS drawdown: cumulative statistical curve starting at unit basis;
- candidate existence: independent of cumulative balance.

The inconsistency was the last item: existence depended on a synthetic compounding balance while
all other quantities were basis-relative. Option A removes that concept without altering the
others.

## Stage and artifact impact

- Targeted XAGUSD task results change from two error rows to two numeric rows.
- A future full Stage-1 rerun will change `study.csv`, candidate evidence, rankings, and statistical
  diagnostics because they finally include those observations. That expected movement is not
  fabricated in this build-only package.
- Cached Stage 2-4 deployed artifacts are not rewritten. Forced deployment remains available and
  unchanged.
- The ignored regression candidate is a byte-copy of the current deployed baseline because no
  changed code is reachable from Stage 3/4.

## Expected numerical impact

- XAGUSD `no_wpr_rsi@36m` and `no_confirms@36m`: error -> finite numeric Stage-1 scores; direction
  and magnitude are measured by targeted real execution.
- Other Stage-1 candidates: no expected change unless they also crossed the removed arbitrary
  running-balance boundary without previously surfacing.
- Deployed `no_bb_wpr`: exact no change.
- Trade count, annual/total return, drawdown, expectancy, Sharpe, tail cap, and both trade CSV byte
  streams: exact no change.

## Measured impact

- `XAGUSD/no_wpr_rsi@36m`: error -> 21 windows, 742 trades, `mean_oos_pct=5.59`,
  `oos_maxdd_pct=6.69`, `return_per_dd=0.836`, `pct_profitable=76`, `wfe_norm=0.454`; all 24 inner
  combinations and 21 canonical candidate windows were returned.
- `XAGUSD/no_confirms@36m`: error -> 21 windows, 745 trades, `mean_oos_pct=5.21`,
  `oos_maxdd_pct=7.08`, `return_per_dd=0.735`, `pct_profitable=71`, `wfe_norm=0.427`; all 24 inner
  combinations and 21 canonical candidate windows were returned.
- Both real streams retain their large negative windows (worst about `-16.71%`) as evidence rather
  than substituting zero or dropping the task.
- Deployed regression remains exact: 1,348 trades, 40.6% annual return, 60.8% total return,
  `-3.30%` max drawdown, and identical trade CSV hashes.

## Initial classification and impact

The explicit planned-path classifier returns R3 with all fourteen cumulative gates. Before edits,
`just impact origin/main` reports no changed path; final impact evidence is recorded after the
implementation commit.
