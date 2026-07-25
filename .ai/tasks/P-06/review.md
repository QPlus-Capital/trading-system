# Adversarial review

## Findings

No findings; 16 counterexamples attempted

## Dispositions

The review exercised a 36-candidate correlated global null, one edge among exact zero-mean
candidates, two correlated edges at the single-step/stepdown boundary, exact statistic ties,
negative and zero observed statistics, positive unit rescaling inherited from P-05, non-finite
probabilities, adjusted p-values below unadjusted values, non-monotone adjusted p-values, duplicate
candidate identities, broken rank order, wrong candidate counts, stale eligibility flags, a
string-valued seed, a helper correct in isolation but absent from the edge path, and premature
Stage-2 consumption.

Three weaknesses found during builder review were resolved before this final disposition:

- The initial 160-family/300-day null fixture measured 8.125%, too close to its loose upper bound.
  It was replaced with 200 families, 500 days, 249 resamples, and a tighter 2%-8% interval; the
  deterministic rejection rate is 5.0%.
- Deserialization initially coerced candidate names and seeds with `str`/`int`, allowing malformed
  types to become plausible evidence. It now requires the declared types and corruption tests
  prove fail-closed behavior.
- Publication was tested without proving the artifact remained additive. A real edge-to-select
  integration test now forces every Romano-Wolf candidate ineligible and proves Stage 2 still
  behaves unchanged until P-08.

The P-05 refactor was executed against the `origin/main` implementation on a fixed family and
produced bit-identical SPA dictionaries. No unresolved P0-P3 finding remains. Claude's independent
review is still required; no live system was invoked.
