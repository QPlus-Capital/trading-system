# Adversarial review

## Findings

No findings; 18 counterexamples attempted

## Dispositions

The review exercised a singleton, exact-identical candidates, unequal deterministic candidates,
independent and 0.919-correlated equal-distribution families, one dominant candidate, a predeclared
true best over repeated experiments, exact range-score ties, a previously removed candidate with
an extreme score, negative-return loss sign, common return shifts, non-finite probabilities,
numeric strings, boolean schema values, broken nested sets, duplicate/unknown identities,
non-monotone model p-values, a helper correct in isolation but absent from the edge path, and
premature Stage-2 membership consumption.

Three weaknesses found during builder review were resolved before this final disposition:

- The initial combined exception block caught `McsInputError` through its `ValueError` base and
  mislabeled an MCS failure as SPA. The stage now has separate fail-closed blocks, with a test that
  executes the real entrypoint and asserts the MCS diagnosis.
- Initial deserialization accepted numeric strings and Python's boolean-as-integer schema value.
  Numeric evidence is now type-strict, and corruption tests prove both forms fail closed.
- Publication alone did not prove P-07 remained additive. A real edge-to-select test now publishes
  deliberately nonselectable MCS-shaped evidence and proves Stage 2 retains its P-05 behavior until
  P-08.

No unresolved P0-P3 finding remains. Claude's independent review is still required; no live system
was invoked.
