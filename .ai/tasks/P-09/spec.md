# P-09: Reconstruct synchronized H4 portfolio risk

## Problem

`research/portfolio/sizing.py::simulate` combines each trade with its market's whole-loss-day
extreme, even when that price occurred outside the trade's lifetime or a different H4 interval,
creating impossible simultaneous portfolio losses and inconsistent Stage-3/fact-sheet drawdowns.

## Goal

Replace the whole-day approximation with one synchronized H4 upper-bound reconstruction whose
daily diagnostics are the sole source for daily loss, trailing-floor breaches, Stage-3 and
Stage-4 drawdown, and fact-sheet drawdown.

## Non-goals

- Changing signals, trades, selection, training, stops, costs, swap amounts, risk fractions,
  annual return, trade counts, edge statistics, tail statistics, or live execution.
- Adding tick/M1 bid-ask fill simulation or resolving within-H4 event order; those remain issue
  #24.
- Re-running Stage 1 or changing the current `run_20260724_1146` baseline.
- Reproducing retired-selection positions or forcing the real 2025-04-10 result to equal an old
  run.

## Behavioural requirements

- Load timestamped H4 low/high/close bars in the verified broker-server-to-UTC frame.
- Replay trade open/close events and bar intervals in timestamp order.
- MT5 stamps each H4 bar at its start. Replay its half-open interval and split that interval at
  exact trade events: an entry on the boundary participates in the following bar, while an exit
  on the boundary does not. A partially overlapping trade may consume only that bar's extreme;
  positions whose actual lifetimes do not overlap are never marked together.
- Use the low for a long and the high for a short, from that market and that H4 observation only.
- At each H4 timestamp, sum the adverse marks of positions whose markets have a contemporaneous bar
  and the last-close/entry marks of other open positions whose markets are closed. This
  deliberately assumes all same-interval adverse extrema co-occur and is labelled an **H4 upper
  bound**.
- Never combine adverse extremes from different H4 timestamps. When an open market has no bar at
  another market's timestamp, carry only its last observed close (or its known entry before its
  first post-entry bar); never borrow a prior extreme. A trade with no H4 observation anywhere in
  its non-zero lifetime fails closed.
- A bar interval that straddles the 16:15 America/Chicago loss-day reset contributes to both loss
  days only for positions whose lifetime overlaps that bar.
- Realized PnL and swap are booked exactly once at close. Swap is never included in an unrealized
  H4 mark.
- Preserve the existing realized-balance event order, compounding/throttle sizes, close-equity
  curve, balance HWM, and conservative same-day trailing-floor semantics.
- Return one immutable `DailyDiagnostics` object containing the loss-day labels, opening balance,
  close balance, close equity, minimum equity, daily-loss fraction, trailing floor, daily-breach
  flags, and trailing-breach flags.
- `PolicyResult`, Stage 3, Stage 4, and the fact sheet consume that object. The fact sheet must not
  call a close-only simulator or implement separate drawdown logic.

## Acceptance criteria

- AC-01: A trade opened at 13:00 and closed at 17:00 cannot consume the 01:00 market high.
- AC-02: A profitable short opened and closed within one observation boundary cannot consume a
  later H4 high.
- AC-03: Positions active in different H4 intervals cannot have their adverse extremes summed.
- AC-04: Positions active in the same H4 interval are conservatively summed and the output is
  explicitly labelled an H4 upper bound.
- AC-05: A reset-straddling H4 bar is assigned to both loss days only when the position overlaps
  it.
- AC-06: Swap is realized exactly once at close and never appears in an H4 unrealized mark.
- AC-07: Daily-limit and trailing-limit checks consume `DailyDiagnostics.minimum_equity`; the
  object contains every specified balance, loss, floor, and breach field.
- AC-08: Stage 3, Stage 4/verdict, and the fact sheet report identical flat maximum drawdown from
  the shared diagnostic path.
- AC-09: A deterministic synthetic six-short fixture with four profitable trades at
  `+6.14R/+4.11R/+3.08R/+2.00R` and an up close reproduces the retired whole-day result near 3.20%,
  while synchronized H4 reconstruction is between 0.30% and 0.45% and has no 3% daily breach.
- AC-10: Real Stage-3 and Stage-4 entrypoints run on the current baseline
  `run_20260724_1146` with the prescribed fixed config and flat 0.15% risk.
- AC-11: `reports/research/regression/35-comparison.json` uses zero trade-count and annual-return
  tolerances, has empty `unexpected_changes`, and proves byte-identical
  `full_history_trades.csv`.
- AC-12: Trade count, annual/total return, hit rate, profit factor, expectancy, Sharpe,
  worst-day R, tail cap, and every other non-path portfolio statistic remain exact.
- AC-13: Every cumulative R3 gate passes with current-HEAD evidence.

## Invariants

- INV-01: H4 lows/highs are market-, interval-, direction-, and position-lifetime-specific.
- INV-02: Same-H4 co-movement remains conservative; cross-H4 co-movement is prohibited.
- INV-03: Trade entry/exit boundary comparisons are explicit and tested.
- INV-04: The prop loss-day axis remains 16:15 America/Chicago and DST-aware.
- INV-05: Realized balance, event ordering, sizes, close equity, and swap realization do not move.
- INV-06: One diagnostic object controls daily breach, trailing breach, drawdown, verdict, and fact
  sheet.
- INV-07: Asynchronous market hours carry the last close/entry without borrowing an extreme; a
  trade with no lifetime H4 observation fails closed.
- INV-08: No live, signal, selection, trade-production, cost, or tail logic changes.
- INV-09: Regression thresholds remain exactly zero and cannot be relaxed after seeing results.

## Risk class

R3. The planned-path classifier assigns R3 because the change touches position sizing, intraday
drawdown, account-limit decisions, reported results, holdout evaluation, and verdict paths.

## Scope

- `research/portfolio/curves.py`: timestamped H4 input loading and loss-day interval attribution.
- `research/portfolio/sizing.py`: synchronized H4 replay and immutable daily diagnostics.
- `research/portfolio/risk.py`: diagnostic-driven breach and drawdown results.
- `research/portfolio/factsheet.py`: consume policy diagnostics rather than a close-only path.
- `research/stages/portfolio.py` and `research/stages/verdict.py`: pass H4 inputs and publish one
  path definition.
- Architecture/methodology documentation, focused behavioural/integration/property tests, critical
  mutation configuration, regression output, and P-09 task artifacts.

## Assumptions

- MT5 H4 stamps retain the verified UTC conversion used by catalog ingestion.
- Backtest trade timestamps and MT5 H4 stamps are bar-start timestamps. The issue's boundary rule
  therefore maps to half-open bar intervals with exact event splits, not point observations.
- Markets have asynchronous sessions. Standard mark-to-market treatment carries the last close
  while that market has no new H4 bar; only a same-timestamp bar may contribute an adverse extreme.
- The current baseline's 2025-04-10 slice contains six shorts but only one profitable trade
  (`+2.00R`); the retired four-profitable-trade structure is absent and numeric acceptance belongs
  to the deterministic synthetic fixture.

## Expected artifacts

- Shared `DailyDiagnostics` results in policy, verdict, and fact-sheet paths.
- Focused H4 lifetime, synchronization, reset, swap, gate, parity, and real-entrypoint tests.
- `reports/research/regression/35-comparison.json` comparing a P-09 Stage-3/4 rerun with
  `run_20260724_1146`.

## Human decisions

Jan corrected the reference baseline to `run_20260724_1146`, required a synthetic numeric fixture
when retired positions are absent, fixed exact zero regression tolerances, and retained the
same-H4 upper-bound assumption. Issue #35 fixes the remaining temporal, cost, and reporting
semantics. Jan retains methodology, live-money, merge, and go-live authority.

## Open questions

None.

## Human decisions required

No implementation decision remains open. Jan must approve the merge and any later go-live use.
