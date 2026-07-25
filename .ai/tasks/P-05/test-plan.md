# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_spa_null_calibration_is_uniform_and_rejects_near_five_percent` | RED: SPA module absent | GREEN: deterministic zero-edge families meet the predeclared p-value and rejection tolerances |
| AC-02 | `test_spa_detects_one_positive_candidate_among_noise` | RED: no family test | GREEN: positive candidate yields `p <= 0.05` |
| AC-03 | `test_consistent_recentering_ignores_strongly_inferior_candidate` | RED: no recentering | GREEN: SPA p-value is unchanged while the least-favourable Reality Check worsens |
| AC-04 | `test_studentization_is_invariant_to_positive_candidate_rescaling` | RED: no studentized statistic | GREEN: statistic and p-value are bit-identical after positive scaling |
| AC-05 | `test_spa_is_bit_for_bit_deterministic` | RED: no deterministic result | GREEN: repeated result objects and dictionaries are exactly equal |
| AC-06 | `test_spa_analysis_uses_p04_selector_and_reports_all_sensitivities` | RED: no P-04 consumer | GREEN: selected L and 5/10/20/60 p-values are present with production defaults |
| AC-07 | `test_edge_publishes_lineage_bound_spa_evidence` | RED: edge stage has no SPA output | GREEN: `spa.json` is atomic and manifest-bound |
| AC-08 | stage auto/forced selection tests | RED: no SPA gate | GREEN: auto aborts; forced selection records `spa_ok=false` as exploratory |
| AC-09 | loader and verified-artifact tests | RED: absent evidence is not checked | GREEN: malformed or absent evidence cannot pass |
| AC-10 | existing research-stage no-drift suites | RED: no explicit P-05 boundary proof | GREEN: existing report bytes and metrics remain unchanged |
| AC-11 | all R3 gates | N/A: cumulative workflow criterion | GREEN: every mandatory command exits 0 |
| INV-01 | `test_spa_loader_reads_the_persisted_daily_matrix_without_recomputation` | RED: no loader | GREEN: parsed values equal P-03 CSV values |
| INV-02 | `test_paired_stationary_bootstrap_preserves_identical_candidate_paths` | RED: no paired bootstrap | GREEN: identical columns retain identical bootstrap scores |
| INV-03 | incomplete-family loader guards | RED: no 36-candidate guard | GREEN: exactly the metadata-declared 36 formal candidates form the family |
| INV-04 | negative-only and benchmark tests | RED: no one-sided test | GREEN: negative-only evidence cannot pass |
| INV-05 | Decimal gate-boundary test | RED: no exact gate | GREEN: exactly 0.05 passes and the next reported decimal fails |
| INV-06 | existing DSR/PBO and stage tests | RED: new integration not yet bounded | GREEN: prior gates retain behavior and values |
| INV-07 | scope diff guard | N/A: repository boundary audit | GREEN: no live, signal, account, order, sizing, or portfolio production file changes |
| INV-08 | generated-artifact ignore guard | N/A: repository boundary audit | GREEN: no report output is tracked |

## Synthetic-null calibration

- Generate 200 independent families, each with 36 zero-mean Gaussian candidates over 500 days.
  Within each family the candidates have correlation 0.919, matching the measured P-03 search
  geometry rather than pretending the heavily overlapping candidates are independent.
- Independently generate 400 eight-candidate zero-mean Gaussian families over 500 days with zero
  cross-candidate correlation, so nominal calibration is not established only on the favorable
  observed correlation structure.
- Use deterministic outer seeds and 249 stationary-bootstrap replications with fixed block length
  five; this is test-only and production remains 10,000.
- Require a rejection rate in `[0.02, 0.08]`, mean p-value in `[0.42, 0.58]`, and empirical p-value
  quartiles that straddle 0.25 and 0.75 within 0.10. These tolerances cover finite outer-sample and
  Monte Carlo error without allowing a grossly anti-conservative or degenerate test.
- The power fixture uses one positive-mean candidate among otherwise identical zero-edge
  candidates and requires `p <= 0.05`; it is not used to tune the production threshold.

## Red-first protocol

Focused tests are added against the absent SPA module and unwired stages, then executed before
production code. Evidence records the collection/import failure and each collected behavioral
failure. Mutation guards are then demonstrated against generated mutants before a survivor
baseline is accepted.
