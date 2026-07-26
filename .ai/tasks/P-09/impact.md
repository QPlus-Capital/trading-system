# Impact analysis

## Classification

The explicit planned-path classifier reports R3 for `sizing.py`, `curves.py`, `risk.py`,
`factsheet.py`, the portfolio/verdict stages, documentation, and focused tests. The change affects
the account-limit path and reported drawdown used in a real-money decision.

## Current baseline observation

`reports/research/run_20260724_1146/portfolio_trades.csv` has six shorts overlapping
2025-04-10, but five are losses near -1R and only USDJPY is profitable at +2.00362R. The retired
selection's four profitable positions at +6.14R/+4.11R/+3.08R/+2.00R are absent. The real rerun is
therefore checked for honest current path changes; the prescribed old-structure magnitude is
proved only by a deterministic synthetic fixture.

## Direct impact

- Replace whole-loss-day low/high collapse with timestamped Decimal H4 OHLC inputs.
- Replay position events inside half-open H4 intervals and return one `DailyDiagnostics` object.
- Make policy evaluation, Stage 3, Stage 4, and the fact sheet consume that one path.
- Change only path metrics: daily loss, hard-limit breach flags, and intraday max drawdown.

## Transitive impact

Stage-3 `portfolio.json`, Stage-4 `verdict.json`, and the fact sheet receive corrected path metrics
and may change a deployability limit result. Trade extraction, sizing multiples, realized returns,
tail inputs, statistical edge metrics, signals, orders, and live execution remain unchanged.

## Critical dependencies

- `core.data.mt5_csv.parse_mt5_timestamps` owns broker-server-to-UTC conversion.
- `research.portfolio.drawdown.trailing_floor` owns the existing trailing-HWM rule.
- `research.portfolio.risk.evaluate_policy` is the sole policy-to-diagnostics boundary.
- Stage 3 produces the sized trade stream; Stage 4 and `factsheet.compute_factsheet` must consume
  its holdout-flat `PolicyResult` rather than reconstructing a separate flat path.

## Coupled quantity: daily minimum-equity path

Every producer and consumer that must move in one pass:

1. `research/portfolio/curves.py::load_daily_low_high` currently collapses all H4 lows/highs into
   whole-loss-day extrema, duplicates reset-straddling bars, and discards interval identity.
2. `research/stages/portfolio.py::main` loads those arrays and passes them to both flat and
   throttle policy evaluations.
3. `research/portfolio/risk.py::evaluate_policy` aligns the daily extrema and supplies them as
   `adverse` to the simulation.
4. `research/portfolio/sizing.py::simulate` builds `active_today`, marks every such trade at its
   direction-adverse whole-day extreme, assumes all markets hit those extrema simultaneously, and
   returns `min_equity_series`.
5. `research/portfolio/risk.py::evaluate_policy` passes that minimum series separately to
   `drawdown.evaluate` and `daily_breach`, then recomputes a running peak and max drawdown.
6. `research/stages/portfolio.py::main` displays and writes `max_drawdown_pct` and `breached` to
   `portfolio.json`.
7. `research/stages/verdict.py::main` reloads daily extrema, re-runs the selected policy, overwrites
   close-path `risk_stats.max_drawdown`, applies the breach gate, and writes `verdict.json`.
8. `research/portfolio/factsheet.py::_daily_equity` independently calls `simulate` without
   intraday extrema; `_money` computes close-only max drawdown, creating issue #28's split.
9. `research/portfolio/factsheet.py::_window` and `compute_factsheet` produce full/holdout,
   flat/compound money cells from that third path.
10. `research/portfolio/html_report.py` and `factsheet.render_terminal` render those cells; they
    need no new calculation and must continue to consume the fact-sheet values.
11. Trailing-HWM and daily-breach helpers in `research/portfolio/drawdown.py` remain mathematical
    primitives, but their inputs must come only from `DailyDiagnostics`.
12. `research/regression.py` reports Stage-3 `max_drawdown_pct` as the permitted path change while
    enforcing exact trade count, annual return, and full-history trade bytes.

## H4 input and replay route

- Replace the lossy daily-extreme loader with a timestamped H4 low/high/close loader using
  `parse_mt5_timestamps`.
- Preserve raw H4 observation identity and the bar's four-hour loss-day overlap.
- Align contemporaneous marks by exact H4 interval across markets.
- Treat every MT5 timestamp as the start of a half-open H4 interval, split it at trade events, and
  include a trade only for the interval segment where its lifetime actually overlaps.
- Aggregate adverse marks only within one timestamp. Asynchronous sessions carry the last
  close/entry, never a prior extreme; a trade with no H4 observation during its whole non-zero
  lifetime fails closed.
- Keep the existing daily close arrays for the close-equity, sizing, and realized-return path so
  the coupled change cannot alter non-path metrics.

## Shared diagnostics

`DailyDiagnostics` owns days, opening balance, close balance, close equity, minimum equity,
daily-loss fraction, trailing floor, daily breach, and trailing breach. `PolicyResult` carries this
object. Stage 3 and Stage 4 use its breach and maximum-drawdown data; the fact sheet consumes
policy results and never reconstructs a close-only drawdown.

## Numerical impact

Expected exact:

- trade count and trade identities;
- `full_history_trades.csv` bytes;
- annual and total return;
- per-trade sized net PnL under flat 0.15%;
- hit rate, profit factor, payoff, expectancy, Sharpe;
- worst-day R, tail cap, and Monte-Carlo inputs.

Expected to change:

- synchronized-H4 minimum equity;
- maximum intraday drawdown;
- maximum daily-loss fraction;
- daily/trailing breach flags when a prior breach was impossible.

The synthetic retired-structure fixture must move from about 3.20% to 0.30-0.45%. The current
baseline's real path delta is data-dependent and must be recorded per evaluated policy/variation,
not forced to the retired result.

## Stage and artifact impact

- No Stage-1 or Stage-2 artifact is regenerated.
- Stage 3 is rerun with forced `no_bb_wpr`, `--fixed live/config/rsi_wpr_bb.py`,
  `--risk flat:0.15`, `--stress-mult 1.5`, and `--tail full`.
- Stage 4 is rerun on that exact Stage-3 publication.
- Stage lineage will republish Stage-3/4 artifacts on one frozen P-09 code state.
- The reference directory remains immutable; the candidate run is a copy whose Stage-3/4
  artifacts are replaced by the real entrypoints.
- `reports/research/regression/35-comparison.json` uses
  `--trade-count-pct 0.0 --annual-return-pp 0.0`; any unexpected change blocks readiness.

## Live and security impact

No `live/**`, account, order, signal, stop, sizing, risk-limit, credential, or runtime process is
touched. The change affects research reconstruction and the go-live evidence only. Market CSVs and
generated reports remain gitignored.

## Failure modes

- Adding a correct H4 helper while Stage 3 still passes whole-day arrays.
- Retaining cached daily low/high arrays through another caller.
- Filtering position lifetime by loss day but not by H4 timestamp.
- Summing one market's 01:00 high with another market's 13:00 low.
- Excluding an entry-boundary bar, including an exit-boundary bar, or combining disjoint
  intra-bar lifetimes.
- Assigning a reset-straddling bar to a day when the trade does not overlap it.
- Realizing swap in the H4 mark and again at close.
- Computing breaches from diagnostics but leaving max drawdown on close equity.
- Letting the fact sheet call `simulate` independently or recompute drawdown.
- Re-running Stage 1, modifying trade producers, or accepting non-path metric drift.

## Unknown or dynamic edges

- Generated run directories are gitignored and cannot be covered by static dependency analysis.
- Real H4 schedules are asynchronous across FX, metals, and indices. The Stage-3 integration must
  prove last-close/entry carry handles closed-market intervals while every non-zero trade still has
  at least one lifetime H4 observation.

## Initial impact command

`uv run python -m scripts.quality.classify` over the planned production, stage, documentation, and
test paths returned R3 with sizing, drawdown, risk-policy, holdout, verdict, and result-integrity
reasons. Final `just impact origin/main` is recorded after the committed diff exists.
