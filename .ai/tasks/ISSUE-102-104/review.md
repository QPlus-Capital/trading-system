# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P3 | MT5 exposes one atomic INOUT money record but does not document how its commission/fee should be split between the closed segment and the new residual segment. | Preserve the deal exactly once on the closing segment, prohibit duplication or proportional invention, and escalate the alternative operator-report convention to Jan in `spec.md`. Total ledger and trade money remain reconcilable. | open-human-decision |

## Counterexamples attempted

The builder-side preflight exercised 18 concrete counterexamples:

1. BUY opening followed by SELL OUT.
2. SELL opening followed by multiple BUY partial OUT deals.
3. Out-of-order source records ordered by time and ticket.
4. Same-second opening fee excluded from its own risk basis.
5. Non-zero fee retained in both ledger and closed-trade P&L.
6. Empty input returns the stable schema.
7. Empty-symbol balance/credit remains ledger-only.
8. Symbol-bearing `BUY_CANCELED`-class type `13` raises.
9. Boolean deal type raises rather than coercing to BUY/SELL.
10. Unknown entry mode raises.
11. Boolean entry mode raises.
12. Long-to-short INOUT yields two directions and a residual volume.
13. INOUT after a partial exit uses remaining, not original, volume.
14. Two OUT_BY records close the positions named by their own IDs.
15. Scale-ins and partial exits conserve total volume and money.
16. A close with the same side as the active position raises.
17. A reversal segment uses the pre-INOUT ticket balance as its P-14 risk basis.
18. Existing dashboard, property, fee, ledger, and risk-view suites consume normal histories
    unchanged.

This is not the required independent Claude review. That review remains mandatory before the draft
can be made ready and before Jan can merge it.

## Dispositions

R-01 remains an explicit P3 human-decision question rather than an invented broker allocation.
The implemented convention is lossless and auditable: one atomic deal enters one closed segment
once, and aggregate ledger/trade money is conserved. Any different attribution requires Jan's
decision and richer broker/order evidence in a separate package.

## Scope review

The diff changes only monitoring reconstruction, focused tests, the existing mutation target, and
the task artifact. It does not change or invoke `live/**`, `research/**`, a runner, an MT5
connection, an account, an order, a risk limit, or a signal. The only numerical movements permitted
are corrected operator-only per-trade/grouping statistics when an account history actually
contains INOUT or OUT_BY deals.
