# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01, INV-01, INV-02 | `test_market_trades_preserves_gross_and_separate_swap` | RED: gross assertion received `0.75` instead of `1.0`; `swap_r`/`net_r` were absent | GREEN: gross `1.0`, swap `-0.25`, and net `0.75` agree |
| AC-02, INV-01 | `test_market_trades_records_zero_swap_when_broker_has_no_market_spec` | RED: `KeyError: 'swap_r'` | GREEN: explicit zero swap and net-equals-gross pass |
| AC-03 | repository-wide `rg` caller audit plus `test_market_swaps_direction_and_sign` | RED: broker-aware schema was mislabelled | GREEN: sole production caller remains explicitly gross and applies swap once |
| AC-04, INV-03, INV-05 | import/call-graph audit, focused stage tests, and `git diff` over forbidden paths | RED: convention violation exists in an analysis branch | GREEN: deployed path is untouched and no live code is invoked |
| AC-05, INV-03 | exact regression and SHA-256 comparison of both trade CSVs | RED: no ISSUE-60 comparison artifact existed | GREEN: zero unexpected changes and byte identity |
| AC-06 | local cumulative R3 commands and truthful mutation blocker | RED: task/evidence absent | GREEN: every runnable local gate passes; Linux mutation states quota blocker |
| INV-04 | strict mypy, Ruff, and full suite | RED: task not yet implemented | GREEN: no new money float boundary and all checks pass |
