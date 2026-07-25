# Adversarial review

Fourteen counterexamples were attempted: correlated and independent null families, negative
high-variance contamination, positive scale transformations, a negative-only family, zero
variance, non-finite input, metadata/CSV count mismatch, a missing matrix, stale SPA bytes, a
failed sensitivity hidden by a passing selected length, forced-selection labeling, a missing
verdict gate, and a helper that is correct but never executes on the Stage-1/Stage-2 path.

## Findings

No findings; 14 counterexamples attempted

## Dispositions

The review found and resolved four defects before this final disposition:

- A strict `T_boot > T_observed` comparison let a negative-only family report p=0 because the
  positive-part bootstrap statistic has a point mass at zero. The finite Monte Carlo p-value now
  counts ties and uses the add-one correction; the negative-only guard proves it cannot pass.
- Estimating long-run variance from the same finite bootstrap draws produced 12% rejection in the
  first independent null fixture. Hansen's stationary-bootstrap covariance-weight estimator
  replaced it; the final deterministic independent and measured-correlation calibrations reject
  7.5% and 4.0%, respectively.
- The first Stage-2 wiring did not make the final verdict re-check SPA. `selection_is_gated` now
  cumulatively requires eligibility, DSR, SPA, and a non-forced selection.
- Deriving the family from surviving study rows could shrink it. Edge now derives the complete
  formal family from the anchored config's `VARIATIONS × TRAIN_MONTHS`.

No unresolved P0-P3 finding remains. Claude's independent review is still required after
publication; no live system was invoked.
