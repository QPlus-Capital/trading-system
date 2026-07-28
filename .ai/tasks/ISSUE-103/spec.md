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
  modes, account identity, monitoring, research, or reported results.
- Do not change the valid BUY/SELL requests, prices, return values, or public data structures.
- Do not address monitoring deal-type reconstruction; issues #102 and #104 own that scope.

## Behavioural requirements

- One runtime converter accepts internal `"BUY"` / `"SELL"` strings and the terminal's explicit
  `POSITION_TYPE_BUY` / `POSITION_TYPE_SELL` values and returns the canonical internal `Side`.
- The converter accepts integer and string subclasses supplied by extension/runtime boundaries,
  while explicitly excluding booleans from the integer enum branch.
- The converter rejects booleans, unknown integers, unknown strings, and every other object with a
  clear `Mt5Error`; it never assigns a default executable direction.
- `positions()` converts each raw MT5 position type before constructing or emitting any `Position`.
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
- The daily/trailing safety cut-off executes before open-risk reconstruction. If reconstruction
  rejects an external position representation, the runner halts and alerts instead of retrying.
- During a safety halt, a failed owned-position lookup for one market alerts and does not prevent
  every retrievable owned position in later markets from being closed.
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
- AC-10: Integer/string runtime subclasses map by their documented values, booleans and loose-
  equality impostors remain rejected, and no rejected value reaches a terminal call.
- AC-11: A flat account returns `[]` from both position surfaces; two owned positions of opposite
  sides plus a foreign position return the exact two owned positions in terminal order.
- AC-12: An invalid side with no stop raises before the no-stop return and before pricing.
- AC-13: A bridge-side position conversion failure halts and alerts the runner; a daily/trailing
  breach is evaluated before any account-wide open-position read can fail.
- AC-14: A failed owned-position lookup during flattening is alerted and isolated to that market;
  every retrievable owned position in the remaining markets is still closed.

## Invariants

- INV-01: Tests use only synthetic terminal objects and in-memory positions; no test imports,
  initializes, connects to, or sends a request to a real MT5 terminal.
- INV-02: No invalid value reaches `order_calc_profit`, `symbol_info_tick`, filling-mode
  selection, or `order_send`.
- INV-03: Legal BUY/SELL behavior is unchanged at every affected boundary.
- INV-04: One converter owns runtime side classification; no affected boundary retains an
  `if BUY else SELL` default.
- INV-05: No signal, risk limit, sizing value, research result, trade record, or monitoring
  behavior changes.
- INV-06: `portfolio_trades.csv` and `full_history_trades.csv` remain byte-identical because no
  research producer or configuration changes.
- INV-07: The branch remains a draft, never merges autonomously, and requires Jan's approval after
  Linux mutation evidence and Claude's independent live-money review.
- INV-08: A position-read exception can neither bypass the daily/trailing cut-off nor truncate
  best-effort flattening of other markets without a critical log and alert.

## Assumptions

- The official MT5 Python constants used by this repository expose distinct integer values for
  `POSITION_TYPE_BUY` and `POSITION_TYPE_SELL`, as stated by issue #103 and the linked MT5
  `ENUM_POSITION_TYPE` documentation.
- The current runner constructs only the two valid internal `Side` literals; this package hardens
  the external/runtime boundary rather than correcting an active wrong-side route.

## Open questions

None. Jan and Claude fixed the severity, fail-closed policy, accepted values, five call sites, and
synthetic-only verification boundary.

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

Jan has already ratified fail-closed behavior, runtime-compatible integer/string subclasses with
explicit boolean rejection, exact accepted values, draft status, the requirement to kill rather
than classify non-equivalent boundary mutants, F-040/F-041 registration, and the prohibition on
touching the running live systems. Five semantically meaningful default-argument mutants were
unobservable through Mutmut's unchanged trampoline defaults; the implementation therefore removes
that untestable representation without changing the public defaults: the private order-type helper
requires explicit `opposite`, while public defaults reference immutable module constants. Jan
retains the go-live and merge decision after a new full independent review.
