# ISSUE-103: Fail closed on invalid MT5 side values

## Problem

`live/mt5_bridge.py` maps legal BUY/SELL values correctly, but five live order and risk boundaries
use catch-all branches that silently interpret every unknown runtime value as SELL, or as the
opposing BUY close, instead of refusing an ambiguous safety input.

## Goal

Normalize direction through one runtime converter that accepts only the two documented MT5
position types and the two internal side literals, and raise `Mt5Error` before any position,
pricing call, or order request can be produced from an invalid value.

## Non-goals

- Do not initialize or connect to MT5, inspect an account, touch either running runner, or place,
  modify, or close an order.
- Do not change signal generation, sizing, risk limits, exit geometry, symbol resolution, filling
  modes, account identity, research, or reported results. The read-only monitoring risk header may
  become indeterminate when a raw position is undecodable; it must not hide that exposure.
- Do not change the valid BUY/SELL requests, prices, return values, or public data structures.
- Do not address monitoring deal-type reconstruction; issues #102 and #104 own that scope.
- Do not persist or alter clearing of the runner halt state; pre-existing issue #122 owns that
  policy and requires Jan's per-cause decision.

## Behavioural requirements

- One runtime converter accepts internal `"BUY"` / `"SELL"` strings and the terminal's explicit
  `POSITION_TYPE_BUY` / `POSITION_TYPE_SELL` values and returns the canonical internal `Side`.
- The converter accepts every runtime position type implementing Python's integral index protocol
  (`operator.index`), including `int`, `IntEnum`, C-extension integer scalars, and other integral
  representations. Booleans remain explicitly rejected before indexing because they alias 0/1.
  Internal side strings continue to accept `str` subclasses with exact BUY/SELL values.
- The converter rejects booleans, unknown integers, unknown strings, and every other object with a
  clear `Mt5Error`; it never assigns a default executable direction.
- Position reads preserve two separate facts: every decodable account position and every raw record
  that could not be decoded. `positions()` remains the actionable compatibility surface, while
  `position_snapshot()` carries both facts to account-wide risk and monitoring.
- An undecodable foreign record is never emitted as an actionable position and never triggers
  flattening, but it makes account-wide risk indeterminate (`inf`) and blocks every new entry.
- An undecodable owned record remains a semantic safety halt. During that halt, per-record owned
  decoding closes every retrievable owned position and alerts with each rejected ticket.
- `owned_positions()` applies `magic == MAGIC` to raw records before converting direction, so no
  malformed unowned record can interrupt an owned manage/close/flatten path.
- `loss_for_order()` validates its side before `order_calc_profit`.
- `loss_to_stop()` validates a stopped position's side before `order_calc_profit`.
- `place_order()` validates its side before reading a tick, selecting a filling mode, or calling
  `order_send`.
- `close_position()` validates its position side before reading a tick, selecting a filling mode,
  or calling `order_send`.
- A flat account returns an empty position list, and ownership filtering returns every owned
  position in terminal order rather than merely the first.
- `loss_to_stop()` validates direction before the no-stop early return because an unverifiable
  side cannot become safe merely by also lacking a stop.
- The daily/trailing safety cut-off executes before open-risk reconstruction. A dedicated
  `Mt5SideError` from ambiguous side conversion halts, alerts, and execute-mode flattens; a routine
  `Mt5Error` from a transient symbol or position read propagates to the polling retry without
  halting or touching open positions.
- After a transient read failure, the next healthy cycle still evaluates `must_flatten`; a real
  daily/trailing breach then halts and flattens normally.
- During a safety halt, a failed owned-position lookup for one market alerts and does not prevent
  every retrievable owned position in later markets from being closed.
- A malformed position the runner does not own cannot halt the runner or flatten any owned
  position. Valid foreign positions remain included in account-wide open-risk accounting.
- Valid BUY/SELL pricing, entry requests, close requests, and position records remain exactly as
  they are on `origin/main`.

## Acceptance criteria

- AC-01: Raw `POSITION_TYPE_BUY` and `POSITION_TYPE_SELL` produce BUY and SELL positions exactly;
  an unknown raw type raises before any `Position` is returned.
- AC-02: An invalid side passed to `loss_for_order()` raises before `order_calc_profit` is called.
- AC-03: An invalid `Position.side` passed to `loss_to_stop()` raises before
  `order_calc_profit` is called.
- AC-04: An invalid side passed to `place_order()` raises before `order_send` or another
  order-preparation terminal call occurs.
- AC-05: An invalid `Position.side` passed to `close_position()` raises before `order_send` or
  another close-preparation terminal call occurs.
- AC-06: Legal BUY and SELL pricing and placement requests retain their exact order types,
  bid/ask choices, fields, and results.
- AC-07: Legal BUY and SELL close requests retain their exact opposing order types, bid/ask
  choices, fields, and results.
- AC-08: The confirmed catch-all-side defect class is generalized in the finding registry and the
  converter plus all five boundaries enter the critical mutation scope.
- AC-09: Every selected MT5 boundary mutant executes a test; all non-equivalent branch survivors
  are killed, the exact baseline is regenerated from the final Linux review-remediation report,
  and every builder-controlled R3 gate passes. The material remediation then receives a new full
  independent review before readiness.
- AC-10: Every position type accepted by `operator.index` maps by its documented value, exact
  BUY/SELL `str` subclasses map normally, booleans and loose-equality impostors remain rejected,
  and no rejected owned value reaches a terminal call.
- AC-11: A flat account returns `[]` from both position surfaces; two owned positions of opposite
  sides plus a foreign position return the exact two owned positions in terminal order.
- AC-12: An invalid side with no stop raises before the no-stop return and before pricing.
- AC-13: A bridge-side position conversion failure halts, alerts, and execute-mode flattens every
  retrievable owned position; routine `symbol_info` and `positions_get` failures close nothing,
  leave the runner unhalted for retry, and do not prevent a later healthy cycle from evaluating a
  real daily/trailing breach. The daily/trailing cut-off remains before open-risk reconstruction.
- AC-14: A failed owned-position lookup during flattening is alerted and isolated to that market;
  every retrievable owned position in the remaining markets is still closed.
- AC-15: A foreign/manual position with an unsupported type is filtered using `magic` before owned
  conversion and cannot halt or flatten a healthy execute-mode book; every valid foreign position
  remains visible to account-wide risk.
- AC-16: A foreign/manual position with an unsupported type, with or without a stop, makes
  account-wide open risk infinite, blocks a real BUY signal before order placement, leaves the
  runner unhalted, and appears as unpriceable in the monitoring risk header.
- AC-17: With one decodable and one undecodable owned raw position, both a conversion-triggered halt
  and a genuine trailing-limit halt close the decodable ticket and alert with the undecodable
  ticket; the test uses the real `Mt5Bridge` raw `positions_get` path.
- AC-18: `operator.index` failures from either `TypeError` or `ValueError`, including malformed
  position magic, become a clear `Mt5SideError` rather than escaping unclassified.

## Invariants

- INV-01: Tests use only synthetic terminal objects and in-memory positions; no test imports,
  initializes, connects to, or sends a request to a real MT5 terminal.
- INV-02: No invalid value reaches `order_calc_profit`, `symbol_info_tick`, filling-mode
  selection, or `order_send`.
- INV-03: Legal BUY/SELL behavior is unchanged at every affected boundary.
- INV-04: One converter owns runtime side classification; no affected boundary retains an
  `if BUY else SELL` default.
- INV-05: No signal, risk limit, sizing value, research result, or trade record changes. Monitoring
  changes only by refusing to show determinate headroom for an undecodable position.
- INV-06: `portfolio_trades.csv` and `full_history_trades.csv` remain byte-identical because no
  research producer or configuration changes.
- INV-07: The branch remains a draft, never merges autonomously, and requires Jan's approval after
  Linux mutation evidence and Claude's independent live-money review.
- INV-08: A position-side conversion error can neither bypass the daily/trailing cut-off nor
  truncate best-effort flattening of other markets without a critical log and alert; a routine
  terminal read error cannot liquidate a book whose limits have not breached.
- INV-09: An invalid unowned record cannot trigger a destructive action, while an invalid owned
  record still raises `Mt5SideError` and retains the verified halt behavior.

## Assumptions

- The official MT5 Python constants used by this repository expose distinct integer values for
  `POSITION_TYPE_BUY` and `POSITION_TYPE_SELL`, as stated by issue #103 and the linked MT5
  `ENUM_POSITION_TYPE` documentation.
- The current runner constructs only the two valid internal `Side` literals; this package hardens
  the external/runtime boundary rather than correcting an active wrong-side route.

## Open questions

None. Jan and Claude fixed the severity, fail-closed policy, accepted values, five call sites,
incomplete-exposure semantics, per-record safety flattening, and synthetic-only verification
boundary.

## Expected artifacts

- Bounded production changes in `live/mt5_bridge.py` and the safety consumers in `live/runner.py`.
- Focused synthetic tests in `tests/test_live_mt5_bridge.py` and
  `tests/test_live_runner_cycle.py`.
- A generalized finding-registry entry and focused mutation patterns for the affected boundaries.
- Complete `.ai/tasks/ISSUE-103/` evidence and a draft pull request pending independent review.
- One wholesale mutation-baseline refresh from the final Linux report.

## Risk class

R3. `scripts/quality/classify.py` classifies `live/mt5_bridge.py` as R3 because it is the broker
bridge for live orders, fills, and money legs. The change affects executable order and risk
boundaries even though the new behavior only rejects invalid inputs.

## Human decisions required

Jan has ratified integral index-protocol acceptance with explicit boolean rejection, exact accepted
values, raw ownership filtering, dedicated conversion-failure handling, incomplete-exposure
blocking, per-record safety flattening, draft status, the requirement to kill rather than classify
non-equivalent boundary mutants, F-040/F-041/F-042/F-047/F-048/F-049 registration, and the
prohibition on touching the running live systems. Five
semantically meaningful default-argument mutants were
unobservable through Mutmut's unchanged trampoline defaults; the implementation therefore removes
that untestable representation without changing the public defaults: the private order-type helper
requires explicit `opposite`, while public defaults reference immutable module constants. Jan
retains the go-live and merge decision after a new full independent review.
