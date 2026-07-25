# Adversarial review

Fourteen counterexamples were attempted: correlated and independent null families, negative
high-variance contamination, positive scale transformations, a negative-only family, zero
variance, non-finite input, metadata/CSV count mismatch, a missing matrix, stale SPA bytes, a
failed sensitivity hidden by a passing selected length, forced-selection labeling, a missing
verdict gate, and a helper that is correct but never executes on the Stage-1/Stage-2 path.

## Findings

| ID | Severity | Finding | Executable proof |
|---|---|---|---|
| F-01 | P1 | A strict `T_boot > T_observed` comparison gave a negative-only family an observed statistic of zero and p-value zero because the positive-part bootstrap statistic also had a point mass at zero. | `test_negative_only_family_cannot_pass_positive_edge_gate` |
| F-02 | P1 | Estimating long-run variance from the same finite bootstrap draws made the independent null calibration materially anti-conservative (12% rejection in the first 200-family fixture). | `test_spa_independent_null_calibration_is_not_anti_conservative` |
| F-03 | P1 | The first wiring made Stage 2 fail closed but left the final deployable verdict re-checking only eligibility and DSR. | `test_verdict_selection_gate_requires_spa_and_prior_candidate_gates` |
| F-04 | P2 | Deriving the expected SPA family from surviving `study.csv` rows could silently shrink the tested family after an incomplete study. | Stage-lineage fixture plus config-derived family validation |

## Dispositions

| ID | Disposition |
|---|---|
| F-01 | Fixed. The finite Monte Carlo p-value counts ties and uses the add-one correction; zero observed superiority therefore cannot pass. |
| F-02 | Fixed. Studentization now uses Hansen's stationary-bootstrap covariance-weight variance estimator. The deterministic independent null rejects 7.5% and the measured-correlation 36-candidate null rejects 4.0%, both inside the predeclared simulation intervals. |
| F-03 | Fixed. `selection_is_gated` cumulatively requires `eligible`, `dsr_ok`, `spa_ok`, and a non-forced selection on the real verdict path. |
| F-04 | Fixed. Edge derives the formal candidate set from `VARIATIONS × TRAIN_MONTHS` in the anchored config and requires the CSV and metadata to match it exactly. |

No unresolved findings; 14 counterexamples attempted.
