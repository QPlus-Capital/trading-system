# Adversarial review

## Findings

Builder adversarial review completed after implementation; 15 temporal, cost, path-sharing,
boundary, asynchronous-market, and fail-closed counterexamples were attempted.

| ID | Severity | Finding | Counterexample | Status |
|---|---|---|---|---|
| F1 | P1 | The existing whole-day extrema erase H4 identity and position lifetime. | A 13:00-17:00 short is charged an unrelated 01:00 high. | RESOLVED |
| F2 | P1 | The fact sheet computes close-only drawdown independently of the Stage-3 breach path. | A recovered intraday dip produces different Stage-3 and fact-sheet max drawdowns. | RESOLVED |
| F3 | P1 | The first H4 implementation treated MT5 bar-start timestamps as point observations at bar end. | A trade entering exactly at 13:00 skipped the 13:00-17:00 bar and consumed the bar beginning at its 17:00 exit; two disjoint intra-bar lifetimes were not replayed in event order. | RESOLVED |

## Dispositions

F1 is resolved by half-open H4 interval replay split at every entry and exit, including exact
entry/exit boundary and disjoint intra-bar tests. F2 is resolved by passing the Stage-4 holdout
`PolicyResult` into the fact sheet; the real run reports `-3.30%` in Stage 3, verdict, and fact
sheet. F3 was found before final validation; its two focused guards fail against commit `699337f`
and pass against the final implementation.

The review also exercised long/short direction, unrelated earlier/later bars, same-interval
co-movement, different-interval and intra-interval non-overlap, Chicago reset overlap, swap at
close, exact daily/trailing boundaries, closed-market carry, wholly missing market evidence,
zero-duration trades, synthetic recovered days, non-path policy parity, and real Stage-3/4
entrypoints. No unresolved P0-P3 builder finding remains. Claude's independent review remains
mandatory.
