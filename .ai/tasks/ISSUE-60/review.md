# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| ISSUE-60-R1 | P1 | `_market_trades`' broker-aware branch overwrote the canonical gross component and did not expose either cost component or derived net return. | Preserve `r`, attach explicit zero/non-zero `swap_r`, derive `net_r`, and pin both broker cases at the real helper boundary. | resolved |
| ISSUE-60-R2 | P2 | The sole production caller's `market_swaps` function ignores authoritative `is_long` and can infer the wrong direction when costs flip a small price gain's result sign. | Kept out of this exact-no-drift package because it can move swap-analysis results; filed issue #95 with a concrete failure fixture. | resolved |
| ISSUE-60-R3 | P2 | A syntactically correct helper fix could remain unused while a downstream caller continued reading swap-netted `r` or applied swap twice. | Repository-wide caller audit proves the only production caller requests broker-less gross trades and applies its freshly pulled swap exactly once; Stage 1-4 use different canonical paths. | resolved |

## Dispositions

All three findings have bounded dispositions. R1 is fixed with two red-first execution-path tests.
R2 is a real but separate analysis-report issue whose correction could move a metric and is tracked
in #95 rather than widening this branch. R3 is resolved by a complete call graph and a behavioural
guard that supplies conflicting `r`/`net_r` values and proves the report reads gross `r`.

## Counterexamples attempted

1. Swap-bearing broker with one overnight long cost: gross `r` remains `1.0`, swap is `-0.25`, net
   is `0.75`.
2. Broker object present but market spec absent: explicit zero swap and net-equals-gross.
3. Positive short-index carry: delegated unchanged to signed `swap_r_per_trade`.
4. Broker omitted: legacy gross-only schema remains what `swap_analysis.main` requests.
5. Conflicting gross `r=1.0` and `net_r=0.75`: `market_swaps` books gross PnL from `r`, not net.
6. Potential double charge: the sole caller does not pass a broker before applying its refreshed
   spec.
7. Stage 1: independent canonical `stage1_trade_returns` path already exposes all three columns.
8. Stage 3/4/fact sheet: no `_market_trades` call edge exists.
9. Empty market snapshot: broker-aware output remains algebraically complete through zero carry.
10. Live safety: no live module is imported by tests or changed; both existing runners are left
    untouched.

## Live-money review

No live file, signal, order, position, sizing, account, limit, or gate changes. The fix is confined
to a private full-history analysis helper and its schema. The deployed research pipeline remains on
the existing `continuous.py` and `trades.py` return paths.
