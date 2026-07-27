# Adversarial review

## Status

Builder counterexample analysis is complete. Independent Claude review remains external and is
required before Jan's merge decision.

## Rebase review coverage

The branch now includes PR #96's chronological H4 drawdown replay in the same
`research/portfolio/sizing.py` function changed by issue #99. The issue #99 delta remains
patch-equivalent after rebase and targeted tests confirm the intended combined behavior, but the
earlier independent review did not review this combined #96/#99 implementation. It therefore does
not cover the current branch HEAD. A fresh independent review of the interaction is required before
this draft can be considered ready; no readiness claim is made here.

The later rebase onto `origin/main` at `8851b91fbf20469d75cd9c2ee2900ccc05183f20` adds merged PR
#97's broker-aware `_market_trades` behavior downstream of issue #99's direction producer. Registry
F-035/F-038, mutation targets, and critical-dependency edges are complete unions and the issue #99
patch remains range-diff equivalent, but the combined producer/helper path is a behavioral addition
to the branch. The current operator caller omits the broker argument, so no existing report changes
from this rebase; still, the earlier review does not cover the combined boundary. Independent review
must rerun before readiness.

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| ISSUE-99-R1 | P1 | Synthetic reports used `side=LONG/SHORT`, while real closed positions expose `side=FLAT` and opening direction in `entry`. | Replace fixtures with real schema semantics and add raw-report reconciliation. | resolved |
| ISSUE-99-R2 | P1 | Stable all-false artifacts passed byte-drift gates because those gates prove reproducibility, not categorical correctness. | Assert extracted direction against independent raw BUY/SELL counts and register the generalized pattern. | resolved |
| ISSUE-99-R3 | P1 | Fixing only swap would leave H4 adverse marks on the wrong side, or fixing H4 locally would leave Stage-1/3 swap wrong. | Fix the sole producer and test both swap and synchronized-H4 consumers. | resolved |
| ISSUE-99-R4 | P2 | A permissive fallback could silently classify future/invalid Nautilus entry values as short. | Exhaustively accept BUY/SELL and raise on every other value. | resolved |
| ISSUE-99-R5 | P1 | Treating this as an exact-no-drift repair would either reject the correct trade CSV changes or conceal their risk effect. | Suspend #57 only for the two direction/swap columns, and require exact row identity plus exact gross fields. | resolved |
| ISSUE-99-R6 | P1 | A full Stage-1 rerun inside this package would mix a nine-hour selection change into a bounded producer repair without pre-agreed selection regression criteria. | Defer the full matrix explicitly; rerun only fixed Stage 3/4 to measure the contaminated deployed configuration. | resolved |
| ISSUE-99-R7 | P1 | Correct direction could make risk materially worse, tempting a local consumer patch or threshold relaxation. | Preserve the H4, limit, and exact-binomial implementations; report the observed breach and failed verdict unchanged. | resolved |
| ISSUE-99-R8 | P2 | Reading the emitted `entry` price instead of the report's `entry` side would repeat the name-collision defect in a different form. | Translate the report row before constructing the emitted dictionary and cover the real schema in fixtures. | resolved |
| ISSUE-99-R9 | P2 | Case or whitespace differences could cause valid report values to fail unexpectedly. | Normalize only case and surrounding whitespace, retaining a closed BUY/SELL vocabulary. | resolved |
| ISSUE-99-R10 | P2 | `NaN`, `FLAT`, empty, or a future side value could be coerced to false and recreate the all-short artifact. | The helper raises with the observed value; there is no Boolean default or outcome fallback. | resolved |
| ISSUE-99-R11 | P2 | Per-market aggregate equality could hide row-level reordering or changes to gross trade quantities. | Compare both generated trade CSVs row-for-row on identity, price, stop, PnL, and gross-R columns. | resolved |
| ISSUE-99-R12 | P2 | A producer-only unit test would not prove the P-09 replay consumes the corrected category. | Feed closed BUY/SELL reports through the producer and real synchronized-H4 replay in one integration test. | resolved |
| ISSUE-99-R13 | P2 | A real-artifact check could accidentally query MT5 or touch a running runner. | Reconcile only offline Nautilus backtest reports from the local catalog in an isolated worktree. | resolved |
| ISSUE-99-R14 | P2 | Updating only holdout extraction would leave the full-history tail and operator stream inconsistent. | Confirm all four callers share `timed_trades_from_report`; change that producer once. | resolved |
| ISSUE-99-R15 | P3 | A local Windows mutation invocation could be misreported as equivalent to the required Linux gate. | Register the critical target but record Linux mutation as infrastructure-blocked until quota recovery. | resolved |
| ISSUE-99-R16 | P2 | `_synchronized_h4_minima` retained an unreachable-looking outcome fallback that would silently misclassify cost-sign-flipped trades from a future caller. | Require `is_long`, fail closed when absent, and convert every valid legacy fixture to explicit direction; leave issue #95 untouched. | resolved |

## Dispositions

All sixteen findings have bounded code/test dispositions. The corrected fixed Stage-3/4 rerun
confirms the adverse counterexample: trade identity and gross R stay exact, while corrected
direction worsens holdout H4 max drawdown from `-3.30%` to `-5.09%`, creates a `4.21%` observed
daily loss, and leaves the verdict `FAIL`. No threshold, limit, gate, or downstream consumer was
changed in response.
