# Impact analysis

## Direct impact

- `monitoring/deals.py::deals_to_trades` is the sole production edit. It will replace a grouped
  first-IN/last-OUT shortcut with an ordered state machine and a strict MT5 deal-type converter.
- `tests/test_monitoring_deals.py` will guard deal types, INOUT, OUT_BY, partial volume, and exact
  money conservation.
- `tests/test_monitoring_risk_view.py` will guard the new reversal segment's opening basis and the
  existing P-14 same-ticket convention.
- `.ai/quality/mutation.toml` extends the existing monitoring reconstruction target to cover the
  strict converter and state-machine helpers; it does not add a second matcher or target.

## Coupled quantities and every consumer

The coupled quantities are reconstructed direction and deal-to-trade grouping. Their complete
in-repository chain is:

1. `live/mt5_bridge.py::history_deals` is the upstream exporter. It returns raw MT5 `type`,
   `entry`, `position_id`, ticket, time, symbol, volume, and Decimal-compatible money legs.
   This package neither imports nor invokes the bridge.
2. `monitoring/deals.py::deals_to_trades` is the sole producer of reconstructed closed trades.
   It owns direction, grouping, volume, boundaries, and per-trade `net_pnl`.
3. `monitoring/deals.py::deal_ledger` independently retains every cash and trade money event.
   It is not changed; reconstruction must reconcile to it.
4. `monitoring/risk_view.py::per_trade_risk` consumes each reconstructed trade's `open_time` and
   `open_ticket` to calculate opening balance basis. It does not consume direction, but splitting
   INOUT creates a second opening boundary and therefore a second risk/R observation.
5. `monitoring/risk_view.py::window_history` consumes reconstructed `close_time` and `net_pnl`.
   Correct reversal grouping can change which rows fall in a history window.
6. `monitoring/deals.py::live_stats` consumes `net_pnl`, so corrected reversal rows can change trade
   count, hit rate, profit factor, and average win/loss while total closed money is conserved.
7. `monitoring/dashboard.py::_load_live` obtains deal dictionaries from the already-running bridge,
   but is not invoked by tests in this package.
8. `monitoring/dashboard.py::_live_view` calls `deals_to_trades`, maps symbols, computes risk and R,
   calls `window_history`/`live_stats`, and displays trade count, hit rate, profit factor,
   expectancy R, cumulative R, history captions, and per-market totals.
9. `monitoring/dashboard.py` does not display direction directly. A strict reconstruction failure
   propagates loudly instead of silently showing an executable-looking side.

No other production caller of `deals_to_trades` exists. No consumer infers direction from outcome
or closed-position state after this producer.

## Displayed operator impact

For accounts containing only normal IN/OUT deals, every displayed value remains exact. For
histories containing INOUT reversals or OUT_BY closes:

- trade count and close dates may change because previously omitted/recombined segments are
  represented;
- per-trade risk and R, hit rate, profit factor, average win/loss, and expectancy may change;
- market trade counts and per-market net rows may change;
- total ledger balance/equity and total money remain unchanged because every money leg is retained
  once.

These are expected corrections, not drift to suppress.

## Stage, live, and artifact impact

- No `core/**`, `research/**`, `live/**`, Stage 1-4, signal, execution, account, risk-limit, sizing,
  or order path changes.
- No MT5 connection or runner invocation is needed or permitted.
- No research stage rerun is required. Existing research artifacts remain valid.
- The reference `portfolio_trades.csv` and `full_history_trades.csv` are outside the modified
  producer path and must retain their recorded hashes.

## Critical dependencies

- MT5 `ENUM_DEAL_TYPE`, `ENUM_DEAL_ENTRY`, and `DEAL_POSITION_ID` semantics are authoritative.
- `monitoring/risk_view.py::balance_at` remains authoritative for P-14 ticket-ordered opening basis.
- `Decimal` sums in `deal_ledger` remain the account-money reconciliation source.

## Unknown or dynamic edges

- External consumers of Streamlit output are not represented in the static graph.
- The bridge does not export the originating order's `ORDER_POSITION_BY_ID`. MT5 documents each
  OUT_BY deal's own `DEAL_POSITION_ID`, which is sufficient to close that position; this package
  does not invent a cross-position relationship.
- MT5 does not document a per-segment commission/fee split for one INOUT deal. The exact atomic
  record is assigned once to the closing segment and the unresolved reporting preference is
  escalated in `spec.md`.

## Failure modes

- Writing a strict converter that tests `int(value)` and still accepts `True` or coerces unknown
  numeric values.
- Applying strict validation after the old ternary has already emitted SELL.
- Rejecting empty-symbol balance/credit events that should remain ledger-only.
- Treating INOUT as only OUT, losing the residual opposite position.
- Treating INOUT as only IN, leaving the prior direction stale.
- Duplicating the INOUT money record on both old and new segments.
- Grouping OUT_BY by close time or symbol instead of its authoritative position identifier.
- Closing a partial position too early or reporting only the first entry volume after a scale-in.
- Producing the correct helper while the real `deals_to_trades`/dashboard path still uses the old
  grouping.
- Changing monitoring totals to make corrected per-trade metrics look stable.
- Importing or initializing the running MT5 bridge during verification.

## Initial classification and impact

The explicit planned-path classifier returned R2: monitoring live-vs-backtest semantics plus guard
tests. The task is manually upgraded to R3 by instruction and consequence class. Final
`just impact origin/main` output will be recorded after the complete diff exists.
