# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_romano_wolf_global_null_controls_familywise_error` | RED: module absent | GREEN: deterministic 36-family null calibration stays within tolerance |
| AC-02 | `test_adjusted_p_values_are_monotone_in_statistic_order` | RED: no stepdown | GREEN: serialized order has nondecreasing adjusted p-values |
| AC-03 | `test_adjusted_p_values_dominate_unadjusted_p_values` | RED: no adjusted values | GREEN: every candidate satisfies the inequality |
| AC-04 | `test_one_strong_candidate_is_the_only_eligible_hypothesis` | RED: no eligibility | GREEN: strong edge eligible, zero-edge candidates ineligible |
| AC-05 | `test_stepdown_finds_two_correlated_edges_that_single_step_misses` | RED: no remaining-family recomputation | GREEN: both stepdown p-values pass while candidate two's single-step p-value fails |
| AC-06 | `test_romano_wolf_is_bit_for_bit_deterministic` | RED: no result | GREEN: objects and dictionaries are exactly equal |
| AC-07 | `test_spa_and_romano_wolf_share_the_selected_bootstrap_draw` | RED: no P-06 consumer | GREEN: matching calls observe bit-identical indices and variance inputs |
| AC-08 | `test_edge_publishes_lineage_bound_romano_wolf_evidence` | RED: edge has no artifact | GREEN: all 36 candidates are atomically manifest-bound |
| AC-09 | serialized corruption parameterization | RED: no schema | GREEN: every malformed invariant fails closed |
| AC-10 | existing stage and no-drift suites | RED: additive boundary unguarded | GREEN: Stage 2 does not read the artifact and existing outputs retain behavior |
| AC-11 | cumulative R3 commands | N/A | GREEN: all required gates exit 0 |
| INV-01 | family-loader stage integration | RED: no P-06 path | GREEN: the loaded P-03 arrays are passed through unchanged |
| INV-02 | shared-draw spy/oracle | RED: separate construction absent | GREEN: P-05/P-06 use the same paired row-index matrix |
| INV-03 | 36-candidate stage guard | RED: no P-06 artifact | GREEN: artifact count and names equal the formal family |
| INV-04 | two-edge stepdown oracle | RED: no remaining set | GREEN: max-null columns shrink exactly in rank order |
| INV-05 | exact boundary and property tests | RED: no gate | GREEN: monotonicity, dominance, and exact 0.05 hold |
| INV-06 | lineage plus selection-spy tests | RED: no artifact | GREEN: evidence is bound and remains unconsumed |
| INV-07 | scope and regression audit | N/A | GREEN: no existing numerical or live path changes |
| INV-08 | tracked-file and security audits | N/A | GREEN: no generated data or secret is tracked |

## Synthetic-null calibration

- Generate 200 independent outer families of 36 zero-mean Gaussian daily candidates over 500
  observations with within-family equicorrelation 0.919, matching the measured search geometry.
- Use deterministic outer seeds, fixed block length five, and 249 bootstrap replications in this
  test only; production remains 10,000.
- Define familywise rejection as at least one adjusted p-value at or below 0.05.
- Require the empirical rejection rate in `[0.02, 0.08]`. With 200 outer families this interval
  covers finite Monte Carlo and binomial error while rejecting gross anti-conservatism or a
  degenerate never-reject implementation.

## Red-first protocol

Add the pure statistical tests against the absent `research.engine.romano_wolf` module and run
them to record collection failure. Add the edge-path guard before wiring and record the missing
artifact failure. Only then add production code. Generated critical mutants must be killed by
focused semantic tests before the mutation baseline changes.
