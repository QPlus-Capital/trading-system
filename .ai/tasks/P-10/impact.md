# Impact analysis

## Direct impact

- Add a loss-day scenario module that converts a chosen `PolicyResult` and its P-09
  `DailyDiagnostics` into validated, Decimal-backed daily rows.
- Stage 3 persists `loss_day_scenarios.csv` beside the two unchanged trade streams.
- Stage 4 requires that artifact, draws joint P-04 stationary-bootstrap scenario paths, writes
  `path_bootstrap.json`, and supplies only the plug-in `P(profit)` to the existing check.
- Update architecture and methodology descriptions of Stage 3/4 artifacts and Monte Carlo.

## Transitive impact

`verdict.json.mc_prob_profit`, its terminal message, and the overall verdict may change only if the
new calendar-day probability crosses the already-existing 0.60 threshold. All underlying trades,
sizing, returns, edge statistics, P-09 diagnostics, account limits, fact-sheet metrics, and tail
statistics are unchanged.

## Critical dependencies

- `research/portfolio/sizing.py::DailyDiagnostics` owns the calendar grid, opening balance,
  close balance, close equity, and synchronized minimum equity.
- `research/portfolio/risk.py::PolicyResult` owns the chosen policy's net per-trade P&L and
  separately sized swap leg.
- `research/portfolio/curves.py::to_day` owns trade-close attribution to the Chicago loss day.
- `research/portfolio/resample.py::select_block_length` and `stationary_bootstrap` own the P-04
  block estimator and resampling draw.
- `research/stages/lineage.py::StageWriter` owns artifact hashes, upstream dependencies, and the
  recorded seed.

## Coupled quantity: daily scenario path

Every producer and consumer is handled in one pass:

1. `research/portfolio/sizing.py::simulate` produces `DailyDiagnostics` across all observed loss
   days, including days without a realized trade.
2. `research/portfolio/risk.py::evaluate_policy` returns those diagnostics plus `trade_pnl` and
   `trade_swap` at the chosen policy size.
3. `research/stages/portfolio.py::main` chooses flat/throttle and is the first point where the
   authoritative diagnostics and realized trade legs coexist. It must build and persist the
   scenario CSV here.
4. `research/stages/lineage.py` hashes that Stage-3 output and invalidates Stage 4 when it changes.
5. `research/stages/verdict.py::main` requires the scenario CSV and must not derive the new
   probability from `portfolio_trades.csv`, `sized_pnl`, or the retired whole-day-extreme path.
6. `research/engine/montecarlo.py::monte_carlo_paths` remains for its legacy callers but is removed
   from the Stage-4 verdict route; its trade-slot zero padding must not be reachable there.
7. `verdict.json`, terminal output, and `report.html` consume the one plug-in probability already
   used by the unchanged 0.60 check.
8. A new `path_bootstrap.json` reports plug-in and fixed-block sensitivity without adding a gate.
9. `research/regression.py` confirms the two trade files and every non-Monte-Carlo result remain
   unchanged.

## Artifact and stage impact

- Stage 1 and Stage 2 remain cached and unchanged.
- The P-09 baseline directory remains immutable.
- A copied candidate run reruns Stage 3 with forced `no_bb_wpr`,
  `--fixed live/config/rsi_wpr_bb.py --risk flat:0.15 --stress-mult 1.5 --tail full`, then Stage 4.
- Stage 3 adds one output; its existing trade CSV bytes and portfolio metrics must remain exact.
- Stage 4 adds one output and one seed entry; only `mc_prob_profit` is permitted to move.

## Numerical impact

Expected exact:

- trade count, identities, and both trade artifact hashes;
- total and annual return, hit rate, profit factor, payoff, expectancy, and Sharpe;
- P-09 maximum drawdown, maximum daily loss, and breach flags;
- worst-day R and tail cap.

Expected movement:

- `P(profit)` may move slightly because the horizon changes from a partially padded sequence of
  trade slots to a complete sequence of calendar loss days. Its direction is data-dependent.

## Live and security impact

No `live/**`, signal, order, account, secret, credential, sizing-policy, or execution path changes.
Generated research reports remain gitignored. The package changes research evidence only.

## Failure modes

- Implementing a sound scenario helper while Stage 4 still calls `monte_carlo_paths`.
- Recomputing opening-to-minimum equity from H4 prices instead of copying P-09 diagnostics.
- Resampling each CSV column independently, destroying the intraday-minimum/close relationship.
- Dropping zero-trade days before selecting the block length or computing path profit.
- Sampling trade days and inserting zeros to reach a calendar horizon.
- Keying sensitivity only by integer length and losing the distinct plug-in result when it equals
  5, 10, 20, or 60.
- Feeding a sensitivity result into the verdict or changing the 0.60 threshold.
- Recording the seed only in JSON but not Stage-4 lineage.
- Writing Decimal money through float formatting, breaking exact accounting identities.
- Rerunning Stage 1/2 or accepting drift in trade, return, path-risk, or tail metrics.

## Unknown or dynamic edges

- Generated run directories are gitignored, so the real Stage-3/4 and byte-parity proof must be
  recorded explicitly rather than inferred from source dependencies.
- The selected plug-in block length and the P(profit) delta are data-dependent. P-04 fails closed
  if its estimated length exceeds `floor(T/10)`; this package must report that failure, not clamp it.

## Initial impact command

`uv run python scripts/quality/classify.py` over the planned module, stage, documentation, and test
paths returned R3 for equity/swap/result computation, verdict, lineage, and methodology.
