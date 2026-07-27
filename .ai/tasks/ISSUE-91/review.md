# Adversarial review

## Status

Builder adversarial review complete. Independent Claude review remains external to this artifact and
is required before Jan's merge decision.

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| ISSUE-91-F1 | P1 | Deterministic H4 drawdown used the same day's later close-equity peak for an earlier minimum. | Fixed in the authoritative synchronized H4 replay; two red-first ordering fixtures pass. | resolved |
| ISSUE-91-F2 | P1 | P-11 replay repeated the same minimum/close ordering error. | Compare the minimum before updating the close-equity HWM; red-first path fixtures pass. | resolved |
| ISSUE-91-F3 | P1 | The first chronological H4 implementation could mark a newly opened position at a market close observed before its entry, creating a false peak. | Timestamp the last market close and use entry until a post-entry close is observable; boundary-entry regression passes. | resolved |
| ISSUE-91-F4 | P2 | The requested claim that drawdown should improve is not true for the current baseline once genuine earlier intraday peaks are retained. | Report the adverse direction: holdout drawdown `-3.30% -> -3.35%`; retain the required real pre-trough H4 peak. | resolved |
| ISSUE-91-F5 | P2 | Changing the trailing gate to strict chronology would be an unratified methodology/gate decision. | Preserve the gate, label paired strict chronology diagnostic-only, and escalate the open decision to Jan. | resolved |

## Dispositions

All five findings have a bounded disposition. F1-F3 have executable regressions. F4 records an
unfavourable but correct numerical result. F5 preserves the ratified gate and leaves the broader
methodology choice to Jan; no implementation work is silently deferred inside this package.

## Counterexamples attempted

1. `100000 -> 99000 minimum -> 110000 close`: reports `-1.00%`.
2. First H4 interval closes at `110000`, later interval minimum is `109000`: reports `-0.91%`.
3. Pre-entry market close is above a new trade's entry: cannot create a position HWM.
4. A losing realized close at an H4 boundary: compared with the HWM before the event.
5. A profitable realized close at an H4 boundary: raises the HWM only for following intervals.
6. Position closes exactly at the interval boundary: absent from the next interval and realized once.
7. Position opens exactly at the interval boundary: enters at its own price, not a stale market close.
8. Market closed while another market advances: carries only a post-entry observable close or entry.
9. One P-10 day dips 1% then closes 10% higher: sampled drawdown remains 1%.
10. Prior sampled day closes at a new high, following day dips 1%: following denominator includes
    the prior high.
11. Same-day profitable close raises the established trailing gate floor: existing breach remains.
12. The same scenario under strict trailing chronology: diagnostic may differ but never gates.
13. Random source/path changes: internal daily/trailing/any dominance over prop-hard remains.
14. Random future positive closes: one-day sampled drawdown is invariant to the later close height.
15. Zero H4 trades/days and direct `DailyDiagnostics` fixtures: daily fallback remains
    minimum-before-close chronological.
16. Existing Stage-4 integration fixture: verdict stats/path and trailing comparison use the same
    selected result.
17. Fact-sheet holdout-flat path: reuses the exact Stage-4 `PolicyResult`.
18. Real Stage-3/4 rerun: both trade CSVs and the P-10 scenario artifact are byte-identical.

## Execution-path review

- `research.portfolio.sizing._daily_diagnostics` receives both daily minima and per-day
  chronological drawdown directly from `_synchronized_h4_minima`.
- `DailyDiagnostics.max_drawdown_pct` reads that path; its no-H4 fallback is chronological.
- `evaluate_policy` copies the property into `PolicyResult`; Stage 3 and Stage 4 consume it.
- Stage 4 passes the same holdout-flat `PolicyResult` into `compute_factsheet`.
- `replay_scenario_path` uses a separate equity HWM for drawdown and preserves the established
  balance HWM for the actual trailing gate.
- `internal_breach_gate_passes` still reads only `internal_breach_upper_95`; the new chronological
  upper bound is serialized and printed but has no gate property.

## Live-money review

No `live/**`, signal, order, sizing, limit, or account code changed or ran. Internal `2.5%/5%` and
prop `3%/6%` constants are unchanged. The production verdict remains FAIL because the existing
one-sided 95% upper bound on internal any-limit breach is `1.3091% > 1%`.
