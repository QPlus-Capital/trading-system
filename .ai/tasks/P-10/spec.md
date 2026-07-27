# P-10: Bootstrap complete loss-day scenarios

## Problem

`research/engine/montecarlo.py::monte_carlo_paths` resamples trade slots, can terminate a path
early and pad it with artificial zero-PnL slots, and cannot preserve the joint relationship
between P-09's synchronized intraday minimum and the same day's close.

## Goal

Persist one complete scenario row for every observed Chicago loss day and derive the existing
Stage-4 `P(profit)` statistic from fixed-horizon stationary-bootstrap paths of those joint rows.

## Non-goals

- Changing any gate, threshold, verdict criterion, selection rule, trade, risk size, signal, cost,
  daily-limit decision, trailing-limit decision, or P-09 diagnostic.
- Implementing P-11's scenario breach replay or making any scenario statistic a new gate.
- Recomputing intraday minima, reviving retired whole-day extrema, or changing P-04's estimator or
  stationary-bootstrap implementation.
- Re-running Stage 1 or Stage 2.

## Behavioural requirements

- Stage 3 writes exactly one scenario for each day in the selected policy's
  `DailyDiagnostics.days`, the existing 16:15 America/Chicago loss-day grid.
- Each row carries source date, close realized price P&L, close-equity change,
  opening-to-minimum-equity change, closing-balance change, realized trade count, and daily swap.
- Close realized P&L excludes swap; daily swap is separate; closing-balance change is their net
  sum and equals the P-09 close-balance movement.
- Opening-to-minimum equity is copied from P-09 `DailyDiagnostics.minimum_equity -
  opening_balance`; no second path calculation is permitted.
- Zero-trade days remain as real rows. Their trade count, realized price P&L, and realized swap are
  zero, while their close-equity change may be non-zero as open positions mark to market.
- The scenario CSV serializes every money value as a canonical decimal string and validates the
  accounting identities when written and read.
- P-04 selects the plug-in block length from the complete daily closing-balance-change stream,
  including genuine zero-trade days.
- One P-04 stationary-bootstrap source-index draw resamples every field jointly. Each simulation
  contains exactly the observed number of calendar loss days, uses circular stationary blocks,
  and never pads or splits a row.
- Production uses 10,000 simulations and seed `20260719`; the Stage-4 lineage records the seed.
- The bootstrap artifact reports the selected plug-in result plus fixed 5/10/20/60-day
  sensitivity, even when a fixed length equals the selected length.
- Stage 4 feeds the plug-in path's calendar-day `P(profit)` into the existing unchanged
  `prob_profit >= 0.60` check. No sensitivity result affects the verdict.

## Acceptance criteria

- AC-01: A scenario set contains exactly one row per P-09 loss day, in strict chronological order.
- AC-02: Every required field is persisted; closing-balance change equals close realized P&L plus
  daily swap and equals the diagnostic close-balance movement.
- AC-03: Opening-to-minimum equity change is byte-faithful to P-09's diagnostic values and changes
  when that supplied diagnostic changes; no price/path input is accepted by the scenario builder.
- AC-04: Zero-trade days remain in the set at their observed frequency, with no synthetic padding.
- AC-05: Every simulated path has exactly the observed calendar-day horizon.
- AC-06: Complete rows are sampled jointly; an oracle presented with one independently shuffled
  field fails.
- AC-07: Fixed-seed scenario paths and summary artifacts are bit-for-bit deterministic.
- AC-08: The summary contains five named results: plug-in, fixed 5, 10, 20, and 60 days.
- AC-09: Stage 4 reads the Stage-3 scenario artifact, not the trade-slot bootstrap, and records the
  seed in lineage; missing or malformed scenarios fail closed.
- AC-10: The existing Monte-Carlo threshold and all verdict checks remain unchanged.
- AC-11: A real Stage-3/4 rerun against the current P-09 baseline produces
  `reports/research/regression/51-comparison.json` with zero trade-count and annual-return
  tolerances and no unexpected changes.
- AC-12: `portfolio_trades.csv` and `full_history_trades.csv` remain byte-identical; trade count,
  return, expectancy, Sharpe, and tail cap remain exact. Only `P(profit)` may move.
- AC-13: Every cumulative R3 gate passes with current-HEAD evidence.

## Invariants

- INV-01: Scenario dates use the DST-aware 16:15 America/Chicago loss-day axis owned by P-09.
- INV-02: P-09 `DailyDiagnostics` is the sole source of the intraday minimum.
- INV-03: A sampled day is an indivisible bundle; source indices are shared by every field.
- INV-04: The simulated horizon is calendar loss days, never trade slots.
- INV-05: Only genuine observed zero-trade days can produce a zero-trade sampled row.
- INV-06: Money is `Decimal` through scenario construction, serialization, validation, and path
  aggregation; NumPy float is confined to the existing P-04 estimator/resampler boundary.
- INV-07: The production replication count, seed, and fixed sensitivity lengths remain the P-04
  registered values.
- INV-08: No gate, threshold, selection, live path, trade stream, or P-09 risk diagnostic changes.

## Assumptions

- `DailyDiagnostics.days` is the authoritative contiguous observed loss-day grid produced by P-09.
- Realized trade P&L excluding swap is `PolicyResult.trade_pnl - PolicyResult.trade_swap`; both
  arrays already reflect the chosen policy size.
- A day's close-equity change is the difference from the prior observed close equity, with the
  account start balance as the predecessor of the first day.
- The current baseline for this additive package is P-09's completed
  `reports/research/run_20260726_p09_v4`.

## Open questions

None.

## Expected artifacts

- `research/portfolio/scenarios.py`.
- `loss_day_scenarios.csv` from Stage 3.
- `path_bootstrap.json` and seeded Stage-4 lineage.
- Focused unit, property, integration, and joint-bundle guards.
- `reports/research/regression/51-comparison.json`.

## Risk class

R3. The planned-path classifier assigns R3 because the work changes a reported Monte-Carlo result
consumed by the verdict and touches holdout/result-integrity paths.

## Human decisions required

Jan fixed the scenario schema, calendar-day horizon, joint stationary-bootstrap construction,
10,000 production replications, seed lineage, exact regression tolerances, and the boundary that
P-10 changes no gate. Jan retains merge, methodology, risk, and go-live authority.
