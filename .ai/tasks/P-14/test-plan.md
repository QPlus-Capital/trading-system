# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_same_second_opening_cost_is_excluded_from_its_own_basis` | RED: timestamp-only reconstruction included the opening cost | GREEN: ticket 9 counts and opening ticket 10 does not |
| AC-02 | `test_history_deals_exports_ticket_and_fee` | RED: bridge omitted both fields | GREEN: ticket and all Decimal money legs exported |
| AC-02 | `test_fee_moves_ledger_equity_and_trade_net_pnl` | RED: fee was absent from all sums | GREEN: fee-only event moves all three outputs |
| AC-03 | `test_load_live_retries_an_interleaved_deal_snapshot` | RED: mixed history/account pair was returned | GREEN: changed ticket/content forces a retry |
| AC-03 | `test_load_live_retries_when_balance_changes_with_the_same_newest_ticket` | RED: one account read could not detect balance churn | GREEN: changed balance forces a retry |
| AC-04 | `test_load_live_fails_closed_when_history_never_stabilises` | RED: no bounded consistency guard existed | GREEN: three attempts raise and shut down |
| AC-05 | `just check` plus `tests/test_live_parity_check.py` and `tests/test_live_runner_cycle.py` | Existing baseline | GREEN: full suite and live parity/runner cycle pass |
| INV-01 | existing live runner/risk/parity invariant suite | Existing baseline | GREEN: full suite passes |
| INV-02 | Decimal type/value assertions in focused reconstruction tests | RED: monetary outputs used float | GREEN: exact Decimal money and R assertions pass |
| INV-03 | `test_fee_moves_ledger_equity_and_trade_net_pnl` and `test_the_ledger_carries_every_deal_not_just_completed_trades` | RED: fee was omitted from the complete ledger | GREEN: every deal and money leg reaches the ledger |
| INV-04 | `test_load_live_retries_an_interleaved_deal_snapshot` and `test_load_live_retries_when_balance_changes_with_the_same_newest_ticket` | RED: history/account could describe different observations | GREEN: ticket/content and balance must both be stable |
| INV-05 | autouse MT5 boundary guard plus fake bridge integration | Existing baseline | GREEN: no real terminal boundary called |
