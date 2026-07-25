# Test plan

| Requirement | Red-first guard | Expected green result |
|---|---|---|
| AC-01 | production candidate-definition test imports the absent module | 36 unique IDs; 36 formal and 5 manual trials |
| AC-02 | Chicago-boundary fixture has two events around 16:15 and a missing middle day | correct consecutive loss days and explicit zero row |
| AC-03 | exact Decimal totals over non-associative values | daily total equals window total for every candidate |
| AC-04 | multi-market, multi-window fixture | market net R/return/trades sum exactly to each window cell |
| AC-05 | rows arrive shuffled with unequal spans | one sorted common date grid and window grid |
| AC-06 | one candidate lacks one configured market | candidate omitted everywhere and listed as excluded |
| AC-07 | persisted daily CSV passed to P-04 input shape | `select_block_length` accepts all candidate arrays |
| AC-08 | mutate one CSV byte after metadata creation | lineage-format hash differs and provenance detects drift |
| AC-09 | Stage-1 copy followed by universe logic | four byte-identical run artifacts remain unchanged |
| AC-10 | capture existing report bytes before persistence | study/ranking/overfitting bytes remain identical |
| AC-11 | regression CLI compares the unchanged baseline to itself at zero thresholds | zero metric drift and identical full-history hash |
| INV-01 | canonical payload is spied from `stage1_trade_returns` output | no PnL/cost recomputation path executes |
| INV-03 | inner combo payload contains 24 entries | persisted IDs remain only variation x train length |
| INV-04 | missing-market fixture | no zero-filled column for the incomplete candidate |
| INV-06 | downstream selection pass | pre-filter bytes unchanged |
| INV-08 | production diff audit | no `live/**`, signal, sizing, risk, or account file changes |

Every new guard is run before implementation and its failing output is recorded in
`evidence.md`. Focused tests remain synthetic and fast; no live system is invoked.
