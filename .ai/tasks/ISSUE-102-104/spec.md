# Issues 102 and 104: Reconstruct MT5 deal semantics

## Problem

`monitoring.deals.deals_to_trades` treats every symbol-bearing deal type other than MT5 `BUY` as
`SELL` and only recognizes `DEAL_ENTRY_IN`/`DEAL_ENTRY_OUT`, so non-trade deal types can acquire an
executable-looking direction while `INOUT` reversals and `OUT_BY` closes disappear or become one
mislabelled round trip.

## Goal

Fail closed on unsupported symbol-bearing deal types and reconstruct normal entries/exits, netting
reversals, and close-by exits as directionally correct, money-conserving monitoring trades.

Issues #102 and #104 are one package because they are one semantic boundary and both require a
single ordered state machine in `deals_to_trades`. Splitting them would create two competing
implementations of the same mapping and force the second package to rebase and retest the first.

## Non-goals

- Initializing or connecting to MT5, reading a live account, or starting/stopping either runner.
- Placing, modifying, or closing an order.
- Changing `live/**`, research, Stage 1-4, trade extraction, trading signals, risk limits, or
  execution behaviour.
- Inferring direction from profit, price outcome, closed-position state, or any value other than
  the authoritative MT5 deal type.
- Adding an undocumented `position_by_id` relationship to deal history. MT5 documents the
  close-by counterpart on the originating order, not as a deal property.

## Behavioural requirements

- A single monitoring converter accepts deal-type values only when `type(value) is int` and the
  value is exactly MT5 `DEAL_TYPE_BUY` (`0`) or `DEAL_TYPE_SELL` (`1`).
- Every other symbol-bearing deal type, including `BUY_CANCELED`, `SELL_CANCELED`, and `bool`,
  raises before any direction is emitted. The error identifies type, ticket, entry, and position.
- Empty-symbol balance, credit, commission, fee, and other cash deals remain absent from the trade
  reconstruction and present in `deal_ledger`.
- Entry values are interpreted explicitly: `IN=0`, `OUT=1`, `INOUT=2`, `OUT_BY=3`; unknown or
  non-integer values on symbol-bearing deals fail closed.
- `IN` opens or scales an active segment in the deal-type direction.
- `OUT` and `OUT_BY` reduce the segment identified by that deal's `position_id`; their deal type
  must be opposite the active position direction.
- `INOUT` closes the current segment and opens the residual volume in the deal-type direction
  under the same MT5 position identifier. Its volume must exceed the volume still open.
- Events are processed by `(time, ticket, source sequence)`. A segment cannot close before it
  opens, exceed its active volume, change symbol, or use a contradictory side.
- Partial entries and exits conserve volume. All profit, swap, commission, and fee legs are
  represented exactly once in reconstructed closed-trade `net_pnl`; no money leg is duplicated.
- An indivisible `INOUT` deal's complete money record is attributed once to the segment it closes.
  The residual opposite segment opens at the same ticket and time with no duplicated money.
- Normal one-entry/one-exit reconstruction and P-14 opening-basis and fee semantics remain exact.

## Acceptance criteria

- AC-01: A symbol-bearing unknown or non-trade deal type raises a contextual error before a
  direction is returned.
- AC-02: A `bool` deal type is rejected even though Python otherwise treats it as an integer.
- AC-03: An empty-symbol balance or credit deal is skipped by trade reconstruction and retained by
  the complete deal ledger.
- AC-04: A synthetic long-to-short `INOUT` reversal emits two closed trades with the same position
  identifier, correct opposite directions, correct residual volume, ordered boundaries, and
  exactly conserved money legs.
- AC-05: Synthetic paired `OUT_BY` closes are attributed by each deal's own position identifier to
  the correct long and short positions.
- AC-06: Scale-ins and partial exits preserve total opened/closed volume and all money legs.
- AC-07: Existing `tests/test_monitoring_deals.py` and `tests/test_monitoring_risk_view.py` pass;
  P-14 opening-basis and fee assertions remain exact.
- AC-08: Risk reconstruction recognizes the `INOUT` ticket as the new segment's opening boundary
  and excludes that ticket's own deal amount from its basis.
- AC-09: No `live/**`, research, Stage 1-4, account, order, risk-limit, or signal code changes.
- AC-10: The reference `portfolio_trades.csv` and `full_history_trades.csv` hashes remain
  byte-identical because no research producer is modified or run.
- AC-11: Every locally executable cumulative R3 gate passes. The Linux Critical mutation gate is
  recorded as blocked by the Actions quota until 2026-08-01, so readiness remains false.
- AC-12: The branch is pushed and exposed as a draft pull request only; it is never marked ready,
  merged, or configured for auto-merge.

## Invariants

- INV-01: The live runners are never imported, initialized, connected, stopped, or invoked.
- INV-02: `deal_ledger` remains the complete, exact Decimal money-event stream.
- INV-03: Trade direction comes only from explicit MT5 BUY/SELL deal types.
- INV-04: A non-trade or unknown symbol-bearing deal can never become BUY or SELL.
- INV-05: Every deal money leg enters at most one reconstructed closed trade.
- INV-06: `sum(trade.net_pnl)` equals the sum of money legs for the deal events consumed by those
  closed segments; open-position money remains visible in the ledger rather than invented into a
  closed trade.
- INV-07: OUT_BY attribution uses `DEAL_POSITION_ID`; no undocumented cross-position field is
  fabricated.
- INV-08: No research artifact or trading decision moves.
- INV-09: Money remains `Decimal`; no new float money path is introduced.

## Assumptions

- The bridge's synthetic/test deal dictionaries follow MT5's documented constants:
  `BUY=0`, `SELL=1`, `IN=0`, `OUT=1`, `INOUT=2`, and `OUT_BY=3`.
- MT5's documented `DEAL_POSITION_ID` is authoritative for the position that a deal opens,
  modifies, or closes.
- A netting reversal's INOUT deal volume is the sum of the old volume closed and the opposite
  residual volume opened.

## Open questions

- MT5 documents one atomic profit/swap/commission/fee record for an INOUT deal but does not define
  an economic split of commission or fee between the closed segment and the new residual segment.
  This package preserves the record exactly once on the segment the deal closes and never invents
  a proportional split. Jan should decide whether a future broker-export extension should capture
  order/fill allocation data for a different operator-report attribution convention. This does
  not affect total account P&L or the directional reconstruction.

## Expected artifacts

- A bounded strict converter and ordered position-segment reconstruction in
  `monitoring/deals.py`.
- Focused red-first behavioural tests in `tests/test_monitoring_deals.py` and
  `tests/test_monitoring_risk_view.py`.
- Extended existing `monitoring-deal-reconstruction` mutation patterns; no second mutation target.
- `.ai/tasks/ISSUE-102-104/` specification, impact, test, review, and evidence records.

## Risk class

R3 by manual upgrade. The path classifier returns R2 for monitoring semantics and its guards, but
the user explicitly requires R3 and the change reconstructs account P&L/risk information displayed
to a real-money operator. All cumulative R3 gates therefore apply.

## Human decisions required

Jan deliberately bundled #102 and #104, fixed the monitoring-only boundary, required strict
fail-closed deal types and explicit INOUT/OUT_BY support, suspended readiness while the Actions
quota is exhausted, and retains sole merge authority. The unresolved INOUT cost-allocation
reporting convention is recorded above and is not guessed or allowed to alter total money.
