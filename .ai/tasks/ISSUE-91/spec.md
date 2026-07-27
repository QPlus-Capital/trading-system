# ISSUE-91: Replay drawdown peaks chronologically

## Problem

`research/portfolio/sizing.py::DailyDiagnostics.max_drawdown_pct` and
`research/portfolio/path_risk.py::replay_scenario_path` let a later close-equity high-water mark
become the denominator for an earlier intraday minimum, so the reported drawdown contains
look-ahead.

## Goal

Compute deterministic Stage-3/4/fact-sheet and sampled-path maximum drawdown from the equity
high-water mark actually available when each minimum occurred, while preserving all existing daily
and trailing limit rules.

## Non-goals

- Changing daily-limit opening-balance semantics.
- Changing the existing trailing-floor convention, any limit, confidence bound, threshold, gate,
  signal, sizing decision, trade stream, return calculation, or tail cap.
- Reconstructing P-10 scenario paths or changing the stationary bootstrap.
- Using the result of the alternative trailing-HWM diagnostic as a gate.

## Behavioural requirements

- H4 replay compares every synchronized interval minimum with the equity HWM known before or at
  that interval.
- The equity HWM advances only after an observable earlier boundary close, realized event, or
  daily close; a later event cannot change an earlier drawdown.
- An observable high reached before a later interval minimum is the denominator for that later
  drawdown.
- The fallback without H4 bars treats each day's minimum as occurring before that day's close.
- `DailyDiagnostics.max_drawdown_pct` is the sole Stage-3, Stage-4, and fact-sheet deterministic
  path drawdown.
- P-11 sampled-path drawdown compares the day's minimum with the prior chronological equity HWM,
  then updates the HWM from that day's close.
- The established trailing gate still raises its balance HWM with the same day's realized close
  before testing that day's minimum.
- A separate diagnostic replays the trailing HWM strictly chronologically: test the day's minimum
  against the prior balance HWM, then update the HWM with the close. Report its raw internal
  trailing/any breach probabilities and exact one-sided 95% Clopper-Pearson upper bound beside the
  gate convention. It never changes `internal_breach_gate_passes`.

## Acceptance criteria

- AC-01: A `100000 -> 99000 intraday -> 110000 close` fixture reports `-1.00%`, not `-10.00%`.
- AC-02: A prior H4 close at `110000` followed by a later synchronized minimum at `109000` reports
  `-0.91%`; the earlier absolute `100000` interval minimum is not compared with the later peak.
- AC-03: Stage 3, Stage 4, and the fact sheet publish the same deterministic chronological result.
- AC-04: P-11 replay applies the same minimum-before-close chronology to every sampled day.
- AC-05: Daily loss and breach arrays remain based on opening balance and are byte-identical for an
  unchanged trade path.
- AC-06: Existing trailing breach flags and gate bounds remain unchanged.
- AC-07: The current and strictly chronological trailing-HWM raw probabilities and exact upper
  bounds are serialized and printed side by side, with the latter labelled diagnostic-only.
- AC-08: A zero-tolerance regression preserves trade count, return, expectancy, Sharpe, tail cap,
  and both trade CSV byte streams; only drawdown outputs may move.
- AC-09: Every cumulative R3 gate passes for the final HEAD.

## Invariants

- INV-01: Money, prices, and gate bounds remain `Decimal` at their authoritative boundaries.
- INV-02: H4 adverse marks remain the synchronized same-H4 upper bound from P-09.
- INV-03: Daily limits remain relative to each day's opening balance.
- INV-04: Trailing floors remain anchored to start balance and keep the existing same-day realized
  close convention for the actual gate.
- INV-05: Internal limits remain strictly tighter than prop-hard limits and their dominance checks
  remain fail-closed.
- INV-06: Stage 3, Stage 4, and the fact sheet do not implement independent drawdown paths.
- INV-07: No live module is invoked or changed.

## Assumptions

- An H4 close is observable at the interval end and may raise the HWM for later intervals.
- Within an H4 interval only the synchronized adverse portfolio mark is used; favorable within-bar
  sequencing remains unknowable and is not invented.
- A P-10 daily scenario contains a minimum that precedes its recorded close for chronological
  drawdown and for the alternative trailing diagnostic.

## Open questions

- **Jan decision required:** should the trailing-limit gate eventually adopt the strictly
  chronological balance HWM instead of the deliberately conservative same-day-close convention?
  This package measures both conventions but leaves the existing gate unchanged. Changing it would
  change a live-money go/no-go gate and requires a separate ratified task.

## Expected artifacts

- Corrected chronological H4 diagnostics and P-11 path replay.
- Side-by-side trailing-HWM convention diagnostics in `path_bootstrap.json`, `verdict.json`, and
  terminal output.
- Focused behavioural, integration, property, and mutation evidence.
- `reports/research/regression/91-comparison.json`.

## Risk class

R3. The planned-path classifier assigns R3 because the change touches position sizing/intraday
drawdown, reported-result computation, Stage-4 verdict evidence, methodology, and the finding
registry.

## Human decisions required

Jan fixed the zero-tolerance regression, preserved every limit/bound/threshold, and explicitly
reserved any trailing-gate convention change for his decision. Jan alone approves merge.
