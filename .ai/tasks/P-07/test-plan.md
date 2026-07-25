# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_identical_distribution_candidates_remain_in_the_mcs` | RED: MCS module absent | GREEN: deterministic low-information fixture retains the predeclared fraction |
| AC-02 | `test_one_dominant_candidate_reduces_to_a_singleton` | RED: no relative-comparison test | GREEN: only the known dominant candidate has `p >= 0.10` |
| AC-03 | exact range/elimination oracle and repeated-run test | RED: no range rule | GREEN: each removed candidate is the signed range argmax with lexical tie-breaking |
| AC-04 | `test_true_best_coverage_is_at_least_ninety_percent` | RED: no MCS coverage | GREEN: deterministic repeated-experiment coverage meets the declared bound |
| AC-05 | `test_single_candidate_returns_itself` | RED: no singleton behavior | GREEN: one candidate returns with p-value 1 and membership true |
| AC-06 | `test_mcs_is_bit_for_bit_deterministic` | RED: no result | GREEN: repeated objects and dictionaries are exactly equal |
| AC-07 | `test_spa_and_mcs_share_stationary_bootstrap_indices` | RED: no MCS consumer | GREEN: captured day-index matrices are identical |
| AC-08 | `test_edge_publishes_lineage_bound_mcs_evidence` | RED: edge has no MCS output | GREEN: `mcs.json` is atomic and manifest-bound |
| AC-09 | MCS corruption parameterization | RED: no artifact schema | GREEN: malformed order, identities, p-values, steps, and flags fail closed |
| AC-10 | SPA oracle, selection non-consumption, and existing regression suites | RED: no explicit boundary proof | GREEN: SPA is bit-identical and all-in/out membership leaves Stage 2 unchanged |
| AC-11 | all R3 gates | N/A: cumulative workflow criterion | GREEN: every mandatory command exits 0 |
| INV-01 | return-to-loss sign oracle | RED: no loss transform | GREEN: candidate with greater return has smaller loss and survives |
| INV-02 | shared-index capture | RED: no shared path | GREEN: matching matrix/L/B/seed yields identical indices |
| INV-03 | edge family/count tests | RED: no MCS family artifact | GREEN: all 36 identities appear exactly once |
| INV-04 | nested-set oracle | RED: no step sequence | GREEN: each statistic and elimination uses only the recorded current set |
| INV-05 | exact Decimal membership boundary and monotone p-value property | RED: no MCS gate | GREEN: 0.10 is in, the next lower decimal is out |
| INV-06 | lineage mutation and selection non-consumption tests | RED: artifact absent | GREEN: stale bytes fail and Stage 2 ignores verified MCS until P-08 |
| INV-07 | existing no-drift suites and production-path scope audit | N/A: additive boundary | GREEN: no existing number or live path moves |
| INV-08 | tracked-file/security audit | N/A: repository boundary | GREEN: no generated data or secret is tracked |

## Synthetic calibration

- **Low information:** generate eight candidates with equal zero expected return, 500 days,
  within-family correlation 0.919, fixed outer seed, 499 test replications, and block length five.
  Require at least seven of eight candidates in the deterministic 90% MCS; all eight is valid.
- **Dominance:** use one candidate with a clearly positive mean daily return and seven correlated
  zero-mean candidates over 500 days. Require the dominant candidate to be the sole 90% survivor.
- **Coverage:** generate 100 independent experiments with six correlated Gaussian candidates over
  300 days, one predeclared best mean and five inferior means, block length five, and 199 test
  replications. Require the known best retained in at least 90 experiments. With 100 outer
  experiments the one-sided 95% binomial standard error at 90% is about three percentage points;
  the hard 90/100 acceptance follows the issue rather than widening below nominal coverage.
- Production remains 10,000 replications with P-05's P-04-selected block length and seed 20260719.
  Test-only replication reductions never alter production defaults.

## Red-first protocol

Add pure MCS tests and an independently collectable edge-publication test while the implementation
is absent. Record the import/collection failure and missing-artifact failure. Only then add
production code. Run focused mutants on the range, elimination, p-value, and membership kernels;
kill meaningful survivors before accepting the measured Linux baseline.
