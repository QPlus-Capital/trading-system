# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | real Stage-2 fixture with excellent ranking and failing SPA | RED: current selector lacked the complete family rule | GREEN: no `selection.json`; SPA is named |
| AC-02 | remove/corrupt/stale each family artifact and mismatch one candidate ID | RED: selection did not consume all three artifacts | GREEN: every case fails with the artifact or identity named |
| AC-03 | parameterized intersection where each successive criterion removes the last row | RED: ordered intersection absent | GREEN: failure names the exact emptying criterion |
| AC-04 | real Stage-2 fixtures tied successively through complexity, return, train, and name | RED: complexity-first rule absent | GREEN: exact specified winner at every tie layer |
| AC-05 | DSR below 0.90 and PBO above 0.20 with all decision gates passing | RED: both remained gates | GREEN: selection succeeds and both are failed diagnostics |
| AC-06 | exact independent/correlated 36-column matrices | RED: current DSR used nominal integer trials | GREEN: formula, cap, and monotonicity hold |
| AC-07 | independent DSR diagnostic oracle | RED: synchronized fields absent | GREEN: both DSRs and all inputs/moments match |
| AC-08 | 36-column labelled window matrix with 8, 9, 10, and 11 rows | RED: current PBO separated groups | GREEN: split count is the largest even value at most ten |
| AC-09 | repeat selection from identical artifact bytes | RED: required protocol absent | GREEN: objects, bytes, and selected identity match |
| AC-10 | invoke `research.stages.select.main` against a real lineage fixture | RED: entrypoint used old gates | GREEN: all required behavior runs on the real path |
| AC-11 | forced variation with deliberately failing automatic evidence | RED: new automatic rule absent | GREEN: force bypasses it and stays exploratory |
| AC-12 | forced-path, candidate-stream, and production-scope guards | RED: no P-08 no-drift guard existed | GREEN: no trade-return producer changes; forced path and stream bytes remain stable |
| AC-13 | cumulative R3 commands | RED: implementation absent | GREEN: Linux Critical mutation run `30206406306` passed at 2,828/3,145 killed with 317 exactly classified survivors; redundant resample mutant `mutmut_64` no longer exists and all cumulative R3 gates pass |
| INV-01 | synchronized-input provenance test | RED: obsolete pooled paths remained | GREEN: only P-03 window bytes feed DSR/PBO |
| INV-02 | strict family-identity integration test | RED: all artifacts were not intersected | GREEN: all three families match exactly |
| INV-03 | edge/select/verdict diagnostic-role tests | RED: DSR/PBO remained gates | GREEN: neither diagnostic blocks |
| INV-04 | exact-boundary parameterization | RED: joint thresholds absent | GREEN: every Decimal boundary is exact |
| INV-05 | successive-empty-set test | RED: ordered intersection absent | GREEN: no fallback and exact criterion named |
| INV-06 | four-level tie-break integration fixture | RED: complexity score absent | GREEN: complexity is the first key |
| INV-07 | forced-path and verdict test | RED: new evidence contract absent | GREEN: force bypasses and stays non-deployable |
| INV-08 | no-drift and live-path scope guard | RED: P-08 scope guard absent | GREEN: no trade, portfolio, signal, order, sizing, risk, or live code changed |
| INV-09 | manifest tamper parameterization | RED: all new artifacts were not consumed | GREEN: stale bytes fail before selection |

## Boundary cases

- Candidate count 35/36/37, duplicate IDs, missing training length, and unknown variation.
- Fewer than two windows, odd window counts, non-finite cells, constant streams, and undefined
  correlations.
- Exact Decimal thresholds: SPA/Romano-Wolf `0.05`, MCS `0.10`, positive fraction `0.90`,
  return/drawdown `0.85`, DSR diagnostic `0.90`, and PBO diagnostic `0.20`.
- Equal complexity/return with training lengths 36, 24, and 18, plus an unsupported training
  length that must fail closed rather than acquire an implicit preference.
- Complexity values missing, non-finite, negative if prohibited by Jan's decision, boolean, string,
  partial, extra, or result-derived.
- Empty universe after a valid structure remains an explicit downstream result, not a fallback to
  another structure.

## Statistical validation

- Construct 36 synchronized Gaussian candidate-window streams with controlled equicorrelation and
  independently calculate `rho_bar`, `N_eff`, Sharpe variance, benchmarks, skew, and kurtosis.
- At `rho_bar=0`, require `N_eff=41`; at `rho_bar=1`, require `N_eff=6`; intermediate fixtures must
  follow `41 - 35*rho_bar` within numerical tolerance and never exceed 41.
- PBO uses deterministic matrices with known split count and a dominant/noise ordering; compare
  against the existing `pbo` kernel called on the explicit full 36-column matrix.

## Mutation targets

- Effective-trial formula, correlation clipping, synchronization and candidate-count guards.
- PBO matrix orientation and even split count.
- Eligibility intersection order and emptying-criterion reporting.
- Complexity/return/training/name sort keys and directions.
- Forced-path bypass and verdict deployability re-check.

## Red-first status

The initial focused run failed during collection because `effective_trial_count`,
`SelectionEvidence`, and `choose_automatic_candidate` did not exist. After Jan supplied the exact
complexity mapping, the behavioural tests were implemented and now pass on the production path.
