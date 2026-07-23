# Impact analysis

## Direct impact

- `live/mt5_bridge.py` exports complete, exact deal money legs plus ticket identity.
- `monitoring/deals.py` reconstructs ticket-ordered balances, fee-inclusive trades, and equity.
- `monitoring/dashboard.py` accepts only a stable deal-history/account snapshot.
- Focused monitoring and bridge tests prove all three P1 defects and the fail-closed boundary.
- The mutation policy covers the touched reconstruction functions.

## Transitive impact

Only operator-facing dashboard values can move: historical per-trade R, fee-inclusive net PnL and
equity, and any metric derived from those display values. No research artifact, signal, order,
sizing decision, live risk limit, or runner behaviour consumes these monitoring results.

## Critical dependencies

`Mt5Bridge.history_deals`, `monitoring.deals`, `_load_live`, and the existing complete-ledger risk
view form one coupled path. Ticket and fee fields must reach the final `_live_view` call rather
than being correct only at their point of definition.

## Unknown or dynamic edges

The deployed broker's use of MT5 `fee` is not available offline. Snapshot churn depends on real
deal timing, so tests use deterministic fakes and no terminal interaction.

## Initial `just impact`

The pre-implementation run saw only this task artifact and therefore reported R0, no production
files, and the full suite as its conservative recommendation. The specification manually upgrades
the package to R3 because the declared scope includes `live/mt5_bridge.py`; impact analysis will be
rerun after implementation so the executable report sees the complete change set.
