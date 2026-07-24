# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | equal-gross, unequal-duration candidates are ranked by net Calmar | RED: `stage1_trade_returns` absent | Longer negative-carry candidate ranks lower |
| AC-02 | positive short-index carry fixture | RED: `stage1_trade_returns` absent | `swap_r > 0` and `net_r > r` |
| AC-03 | one trade spans one window and closes in the next | RED: Stage-1 close-event API absent | No earlier mark; one close-time realization |
| AC-04 | one net fixture feeds training/OOS/summary/Sharpe/WFE/RPD assertions | RED through missing common net stream and unchanged CLI aggregates | All coupled quantities reconcile to `net_r` |
| AC-05 | real `characterize.main` synthetic CLI run with zero versus large swap | RED: both runs report identical 60.11% mean OOS return | Generated `study.csv` changes |
| AC-06 | directly generated provenance before/after snapshot-content change | RED: `_provenance.json` is absent | Snapshot lineage hash changes |
| AC-07 | fixed Stage-3 bypass and existing portfolio regression suites | Invariant baseline | Gross fixed trades and portfolio metrics unchanged |
| AC-08 | `just check` and forbidden-artifact audit | N/A | GREEN; no Stage-1 validation/report artifact |
| INV-01 | trade-frame column assertions | RED: trade-frame API absent | `r` unchanged, separate `swap_r`, exact `net_r` |
| INV-02 | monkeypatch spy on shared broker/swap primitives | RED: real CLI ignores patched shared primitive | No alternate convention executes |
| INV-03 | close-window attribution assertion | RED: close-event API absent | Exactly one swap realization |
| INV-04 | fixed Stage-3 focused suites and production diff audit | N/A | GREEN |
| INV-05 | existing training-boundary and constant-basis suites | Existing GREEN | Remain GREEN |
| INV-06 | type/static checks and source audit | N/A | No new float money boundary |
| INV-07 | `git diff --quiet origin/main -- live core/strategies monitoring` | N/A | GREEN |
