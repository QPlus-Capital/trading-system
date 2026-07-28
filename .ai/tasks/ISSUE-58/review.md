# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| ISSUE-58-R1 | P1 | The fixed-basis return function retained a synthetic compounding-account viability check and converted two valid candidates into generic error rows. | Remove the sole cumulative-equity branch and pin exact/beyond-basis behavior with red-first tests. | resolved |
| ISSUE-58-R2 | P2 | Fixing only the chosen path could leave inner parameter combinations subject to the obsolete boundary, or vice versa. | Both chosen and matrix scoring call the same `window_returns`; focused candidate-matrix tests and real tasks returning all 24 combos prove both execute through the fix. | resolved |
| ISSUE-58-R3 | P2 | Removing the exception could flatten later windows to zero, truncate their trades, or alter their denominator while still avoiding an error row. | Tests assert aggregate and per-trade values after `-110%`, and invariant later `+10%` scores after `-99.5%`, `-100%`, and `-150%` prior histories. | resolved |
| ISSUE-58-R4 | P2 | A synthetic-only test would not prove the two real XAGUSD tasks survive the engine/process orchestration path. | Execute `_run_task` on the frozen config and real data for both exact candidates; each returns 21 windows, all 24 combos, finite scores, and no error. | resolved |

## Dispositions

All four findings are resolved with executable evidence. The generic characterize exception-to-error
row remains intact for genuine task failures; only the inconsistent producer was removed. A full
432-task Stage-1 rerun is deliberately not represented as completed and no downstream selection
number is fabricated.

## Counterexamples attempted

1. Prior cumulative loss remains just above the basis boundary (`-99.5%`).
2. Prior cumulative loss equals the basis exactly (`-100%`).
3. Prior cumulative loss exceeds the basis (`-110%` and `-150%`).
4. A later positive trade retains `+10%` under every prior-loss depth.
5. A later negative trade retains `-20%` after a `-110%` first window.
6. Aggregate and per-trade returns reconcile to the same constant basis.
7. Inner-boundary negative close remains owned once by the later window.
8. Gap and final-boundary attribution remain unchanged.
9. Chosen scheduled path and 24-combination matrix share the corrected scorer.
10. Real `XAGUSD/no_wpr_rsi@36m` completes all 21 windows and 742 trades.
11. Real `XAGUSD/no_confirms@36m` completes all 21 windows and 745 trades.
12. Both real candidates retain negative windows rather than zero-filling.
13. Stage-1 swap/net-return tests remain unchanged.
14. Stage-3/4 deployed artifacts remain byte-identical at zero regression tolerance.
15. No live, signal, order, sizing-limit, or account path changes.

## Live-money review

No live module or deployed trading path changes. Option A affects research candidate evidence only.
Stage-3/4 forced deployment remains unchanged, internal/prop limits remain unchanged, and neither
running live process was invoked or restarted.

## Rebase review

Rebased onto `origin/main` at `82632060223ab83b3ebaa06154f87b00ed7f8c59` after PR #96.
The only conflict was the append-only finding registry. Main's F-034 was preserved and issue #58's
pattern was renumbered to the merge-order-reserved F-036. `git range-diff
8fff632..8631368 8263206..HEAD` shows the issue-58 commits are patch-equivalent apart from retaining
main's F-034 and renumbering this registry entry. No Stage-1 implementation or test behaviour
changed during the rebase, so the earlier review still covers the implementation.

Rebased again onto `origin/main` at `8851b91fbf20469d75cd9c2ee2900ccc05183f20` after PR #97.
The sole conflict was the append-only finding registry; merged F-035 and issue #58's existing F-036
are both retained in ID order. Range-diff shows the issue #58 implementation and tests remain
patch-equivalent, and `.ai/quality/mutation-baseline.toml` is unchanged. This second rebase changes
no behavior, so the earlier review continues to cover the implementation.
