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
- The converter rejects booleans, unknown integers, unknown strings, and every other object with a
  clear `Mt5Error`; it never assigns a default executable direction.
- `positions()` converts each raw MT5 position type before constructing or emitting any `Position`.
- `loss_for_order()` validates its side before `order_calc_profit`.
- `loss_to_stop()` validates a stopped position's side before `order_calc_profit`.
- `place_order()` validates its side before reading a tick, selecting a filling mode, or calling
  `order_send`.
- `close_position()` validates its position side before reading a tick, selecting a filling mode,
  or calling `order_send`.
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
- AC-09: All locally executable cumulative R3 gates pass; the Linux Critical mutation gate is
  recorded as blocked by the Actions quota until 2026-08-01, so readiness remains NOT READY.

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

- One bounded production change in `live/mt5_bridge.py`.
- Focused synthetic tests in `tests/test_live_mt5_bridge.py`.
- A generalized finding-registry entry and focused mutation patterns for the affected boundaries.
- Complete `.ai/tasks/ISSUE-103/` evidence and a blocked draft pull request.

## Risk class

R3. `scripts/quality/classify.py` classifies `live/mt5_bridge.py` as R3 because it is the broker
bridge for live orders, fills, and money legs. The change affects executable order and risk
boundaries even though the new behavior only rejects invalid inputs.

## Human decisions required

Jan has already ratified fail-closed behavior, exact accepted values, BUILD-ONLY draft status, and
the prohibition on touching the running live systems. Jan retains the go-live and merge decision
after the quota reset and independent Claude review.
