# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | synthetic P-09 diagnostics with three consecutive days | RED: scenario module absent | GREEN: exactly three ordered source dates |
| AC-02 | exact accounting fixture and CSV round-trip | RED: no schema existed | GREEN: all fields and both balance identities hold |
| AC-03 | replace only supplied `minimum_equity` | RED: no diagnostic consumer existed | GREEN: only opening-to-minimum changes |
| AC-04 | zero-trade middle day plus dropped-row CSV | RED: trade-slot path omitted it | GREEN: row retained; a missing date fails closed |
| AC-05 | generated paths over uniquely tagged rows | RED: old output length was trade slots | GREEN: every path has exactly `T` days |
| AC-06 | independent close-equity-field shuffle | RED: old representation could not check bundles | GREEN: joint oracle rejects the invented row |
| AC-07 | repeat paths and summaries at one seed | RED: no scenario result existed | GREEN: dataclasses and JSON are identical |
| AC-08 | summary labels with possible duplicate length | RED: only fixed 5-day trade blocks existed | GREEN: plug-in plus fixed 5/10/20/60 all appear |
| AC-09 | real Stage-3/4 wiring guard plus integration rerun | RED: Stage 4 called `monte_carlo_paths` | GREEN: Stage 3 publishes, Stage 4 requires, seed recorded |
| AC-10 | source boundary and verdict regression | RED: old source fed the threshold | GREEN: exact `prob_profit >= 0.60` check is unchanged |
| AC-11 | real Stage-3/4 run plus issue-51 regression | RED: no P-10 comparison existed | Pending real rerun |
| AC-12 | zero-tolerance regression and SHA-256 comparison | RED: no P-10 parity artifact existed | Pending real rerun |
| AC-13 | cumulative R3 commands | RED: implementation absent | Pending final gates |
| INV-01 | known timestamps mapped through `to_day` and diagnostic dates | RED: no scenario axis existed | GREEN: source dates match the P-09 grid |
| INV-02 | changed-minimum behavioural test and stage source guard | RED: no scenario builder existed | GREEN: no H4/path input accepted |
| INV-03 | uniquely tagged source and independent-field corruption | RED: old fields were not bundled | GREEN: all sampled rows are observed bundles |
| INV-04 | property over sample sizes, lengths, replications, and seeds | RED: old horizon was `n_trades` | GREEN: all paths retain calendar horizon |
| INV-05 | zero-trade source-identity test | RED: old padding invented zero slots | GREEN: every zero row names an observed zero day |
| INV-06 | Decimal construction/CSV/path-sum tests | RED: no scenario money path existed | GREEN: float is confined to P-04 indexing/estimation |
| INV-07 | default and sensitivity constant assertions | RED: Stage 4 used 1,000/seed 42 | GREEN: P-04 10,000/20260719/5-10-20-60 |
| INV-08 | diff audit, threshold guard, and regression | RED: no P-10 scope guard existed | Pending final no-drift audit |

## Properties and calibration

- For generated finite Decimal scenarios, CSV round-trip preserves all values and accounting
  identities exactly.
- For generated source lengths and valid block lengths, every source index is in `[0, T)` and
  every path length is exactly `T`.
- Production defaults remain 10,000 replications and seed `20260719`; tests use reduced counts.

## Integration and parity

- Copy the current P-09 baseline, rerun only Stage 3/4 with the pre-registered command line, and
  generate issue 51's regression artifact with both tolerances at zero.
- Hash both trade CSVs before and after.
- Compare portfolio/verdict/fact-sheet non-Monte-Carlo statistics exactly and record the sole
  permitted `P(profit)` delta.

## Mutation focus

Mutate scenario construction, accounting validation, source-index sharing, horizon validation,
zero-day preservation, block-length labels, seed handling, and the Stage-4 probability boundary.
Any unexplained survivor blocks readiness.
