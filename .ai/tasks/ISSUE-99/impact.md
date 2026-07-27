# Impact analysis

## Direct impact

- `research/portfolio/trades.py::timed_trades_from_report` changes one categorical producer:
  `row["entry"]` (`BUY`/`SELL`) becomes emitted `is_long`; `row["side"]` is no longer consulted.
- `tests/test_research_portfolio_trades.py` uses real closed-report semantics (`side=FLAT`) and
  guards BUY, SELL, and invalid entry-side behavior.
- `tests/test_research_h4_path.py` crosses the real producer boundary into P-09 synchronized H4
  reconstruction.
- Quality configuration registers the producer as a critical impact/mutation target; the finding
  registry records the stable-wrong-category failure.

## Coupled direction chain

There is one producer and the following consumers:

1. `timed_trades_from_report` is called by:
   - `research.engine.continuous.stage1_trade_returns`;
   - `research.portfolio.trades.extract_market_trades` for Stage 3 holdout extraction;
   - `research.portfolio.tail.full_history_trades`;
   - `research.portfolio.stats._market_trades` for the operator swap report.
2. Stage 1:
   - `stage1_trade_returns` carries `is_long` into `core.broker.swap_r_per_trade`;
   - corrected `swap_r` changes `net_r`, window returns, training/OOS ranking inputs, WFE, Sharpe,
     DSR/PBO diagnostics, candidate daily/window streams, SPA, Romano-Wolf, MCS, and selection.
   - None of those consumers is patched here; a future full Stage-1 rerun must re-derive them.
3. Stage 3 holdout:
   - `research.stages.portfolio` groups extracted trades and applies `swap_r_per_trade`;
   - `research.portfolio.risk.net_r`, sizing, edge metrics, fact sheet, annual return, and
     expectancy consume corrected swap.
4. Full-history tail:
   - `research.portfolio.tail` attaches corrected swap to its extracted stream;
   - gross crisis-tail R/day remains direction-independent, while RCK/net metrics can move.
5. P-09 H4 path:
   - `research.portfolio.sizing._synchronized_h4_minima` reads `is_long`;
   - longs take the interval low and shorts take the high;
   - corrected minima feed `DailyDiagnostics`, deterministic daily loss, max drawdown, and breach
     flags shared by Stage 3, Stage 4, and the fact sheet.
6. P-10 scenarios:
   - `build_loss_day_scenarios` copies opening-to-minimum changes and daily swap from the shared
     diagnostics/trades;
   - `loss_day_scenarios.csv` therefore changes without an independent direction implementation.
7. P-11 replay:
   - Stage 4 bootstraps those complete scenario days;
   - final-return distribution, expected shortfall, drawdown, time under water, all four breach
     probabilities, exact bounds, and verdict can move.
8. Operator swap report:
   - `_market_trades` now emits correct explicit direction to `swap_r_per_trade`;
   - issue #95 will separately make its displayed L/S count prefer that field.

## Transitive impact

The coupled direction chain above is the complete known transitive surface: Stage-1 net selection,
Stage-3 swap and H4 diagnostics, P-10 scenarios, P-11 path replay/verdict, the fact sheet, and the
operator swap report. Static impact analysis discovers no additional unknown edge; dynamic
Nautilus report generation is covered by the independent ten-market reconciliation.

## Artifacts carrying or inheriting direction

- Direct columns: `portfolio_trades.csv` and `full_history_trades.csv` carry `is_long` and
  `swap_r`; both must change bytes.
- Stage-1 internal/candidate artifacts do not carry trade-level `is_long`, but every net candidate
  return can inherit the corrected swap.
- Derived Stage-3/4 artifacts: `loss_day_scenarios.csv`, `portfolio.json`, `path_bootstrap.json`,
  `verdict.json`, fact-sheet/report output, and stage lineage hashes may change.
- The broker snapshot, selection/config inputs, H4 bars, signals, gross trade rows, and live state
  do not change.

## Exact-preservation boundary

For both holdout and full-history streams, compare row count and row-by-row:

- `market`, `ts_opened`, `ts_closed`;
- `entry`, `exit`, `sl_pct`;
- `pnl_base`, gross `r`.

Only `is_long`, `swap_r`, derived net/path metrics, generated artifact bytes, and lineage may move.
The #57 byte-identity rule is explicitly suspended only for these expected corrected columns.

## Critical dependencies

- `core.broker.swap_r_per_trade` already prefers explicit direction and never changes here.
- `research.portfolio.sizing._synchronized_h4_minima` already uses low for long/high for short.
- `research.portfolio.scenarios` and `path_risk` already consume shared diagnostics/scenario rows.
- The new `trade-direction-extraction` mutation target covers the producer's BUY/SELL/fail-closed
  boundary. Linux baseline measurement is deferred honestly to quota recovery.

## Unknown or dynamic edges

Nautilus report schemas and backtest execution are dynamic. Static fixtures previously invented
`side=LONG/SHORT` and hid the real closed-position state. Real acceptance therefore runs the
deployed ten-market extraction against the local catalog and independently compares emitted
Booleans with raw report `entry` counts. It never contacts MT5.

The copied Stage-3/4 baseline predates complete current lineage, so diagnostic reruns require the
existing explicit legacy-inspection mode and cannot produce a deployable PASS.

## Expected numerical impact

- Trade counts, identities, gross PnL, gross R, and gross crisis tail: exact no change.
- Direction split: `0/1348` and `0/8703` longs/total must become non-degenerate; exact per-market
  counts are measured.
- Total swap R and net returns: may improve or worsen according to broker long/short terms.
- H4 minima, intraday drawdown, daily loss, scenario paths, breach probabilities, and verdict:
  expected to move; the likely direction is worse because true longs were previously marked at
  the favorable high.
- Stage-1 rankings/selection: unknown until the required future nine-hour rerun; no value is
  guessed.

## Initial classification and impact

The explicit planned paths classify R3 with all fourteen cumulative gates. Before edits,
`just impact origin/main` reports no diff; final impact evidence is recorded after implementation.
