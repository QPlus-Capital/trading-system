# Impact analysis

## Direct impact

The complete issue-defined boundary set is enumerated before implementation:

1. `Mt5Bridge.positions()` converts raw `POSITION_TYPE_*` values into `Position.side`.
2. `Mt5Bridge.loss_for_order()` converts an intended entry side into the terminal order type used
   by `order_calc_profit`.
3. `Mt5Bridge.loss_to_stop()` converts an open position's side into the terminal order type used
   by `order_calc_profit`.
4. `Mt5Bridge.place_order()` converts an intended entry side into order type and bid/ask execution
   price before `order_send`.
5. `Mt5Bridge.close_position()` converts an open position's side into the opposing order type and
   bid/ask execution price before `order_send`.

All five will consume one runtime converter. `tests/test_live_mt5_bridge.py` will exercise every
invalid boundary with a synthetic terminal that counts pricing and order calls.

## Transitive impact

- `positions()` feeds `owned_positions()`, `live.runner._total_open_risk`, all runner
  same-side/reversal/flatten decisions, and `monitoring.dashboard._load_live`.
- `loss_for_order()` feeds `live.preflight.preflight` and the runner's broker-refined candidate
  order sizing.
- `loss_to_stop()` feeds `live.runner._position_risk`, `live.runner._total_open_risk`, and the
  monitoring dashboard's open-risk display.
- `place_order()` is called only after live signals, sizing, and risk gates in
  `live.runner._act`.
- `close_position()` is called for reversals, long-only sell flattening, explicit flattening, and
  risk-controller flatten-all actions in `live.runner`.
- Legal values therefore retain the exact existing request path. Invalid values now terminate at
  the bridge boundary instead of becoming executable direction.
- Research stages and trade artifacts do not import or call the live bridge. No Stage 1-4 result
  or trade CSV producer is reachable from this change.

## Critical dependencies

- `live/mt5_bridge.py` is explicitly R3 in `.ai/quality/risk-classes.toml`.
- `tests/conftest.py` blocks accidental live MT5 calls; focused tests additionally replace the
  module's `mt5` object with a complete in-memory fake and leave `_connected` local to the test
  bridge.
- The critical mutation policy already copies and mutates `live/mt5_bridge.py`; its target will be
  extended from deal export to the side converter and the five affected methods. The Linux result
  cannot be generated until Actions quota resets.
- `live/runner.py`, `live/risk_control.py`, signals, account profiles, and live configuration are
  read-only consumers and remain unchanged.

## Unknown or dynamic edges

- MT5 is an external runtime API and Python type annotations cannot validate values received from
  it. The tests model documented constants plus invalid enum/string values without importing or
  initializing the Windows terminal package.
- The repository cannot prove what a future MT5 release may add. The converter deliberately
  treats every unrecognized future value as an error, which is the required fail-closed behavior.
- No ambiguous enum-semantic question remains: the issue and official documentation identify the
  only currently legal position types as BUY and SELL.

## Numerical and artifact impact

- Expected numerical effect: exactly none for all valid BUY/SELL inputs.
- No risk limit, risk amount, sizing value, price, quantity, request field, or account state moves.
- No research code, config, data, lineage, or stage is changed; the baseline
  `portfolio_trades.csv` and `full_history_trades.csv` hashes must remain unchanged.

## Failure modes

- Writing a validator that exists but one of the five production call sites never invokes.
- Validating only before `order_send` while an invalid side already reached
  `order_calc_profit`, tick lookup, or filling-mode selection.
- Accepting `True`/`False` because Python booleans compare equal to integer enum values.
- Mapping every non-BUY value to SELL inside the converter, merely moving the defect.
- Duplicating side validation per method so one copy can drift.
- Reversing the valid close order or bid/ask price while hardening the invalid path.
- A test asserting only `Mt5Error` without proving terminal pricing/order calls stayed at zero.
