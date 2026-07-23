# Impact analysis

## Direct impact

- Adds one isolated `research/forward_decision.py` read-only consumer of the P-12 registry and P-04
  bootstrap.
- Adds focused behavioural, deterministic property, suppression, and clustered-power tests.
- Adds the decision/bound functions to the existing Linux focused-mutation policy and ratchet.
- Adds one module-map line; no stage, live, monitoring, registry, or resampler behaviour changes.

Initial `just impact` is expected to report no committed changes because the command compares
commits. The explicit intended-path classifier is R3 due to `pyproject.toml` and `.ai/quality/**`;
the new research module alone is R2 and is manually upgraded to R3 for methodology/result integrity.
Final `just impact` against `origin/main` reports R3, selects the two focused decision test modules
plus deterministic properties, applies the configured forward-decision critical escalation, and
finds no transitive, dynamic, or possibly affected tests.

## Transitive impact

Nothing consumes the new decision module in this package. It reads `ForwardTestRegistry.cohort`,
`ForwardTestRegistry.observations`, P-12 cohort/observation domain types, and P-04
`select_block_length`, `stationary_bootstrap`, constants, and sensitivity lengths.

## Critical dependencies

- P-12 remains the only persistence, cohort identity, source-isolation, and exact daily-R boundary.
- P-04 remains the only Politis-White selection and stationary-bootstrap implementation.
- The explicit as-of/trade-count inputs must refer to one cutoff; P-13 cannot infer execution
  counts from daily observations.
- Focused mutation must bind the threshold, bound, calendar, suppression, futility, and endpoint
  decision functions.

## Unknown or dynamic edges

- No current monitoring/dashboard caller exists. Operational wiring and the source of the
  cumulative trade count are deliberately outside P-13.
- The complete-zero-day-grid guarantee is an upstream producer responsibility; the registry
  records observations but does not prove grid completeness.
- Static impact analysis is conservative and cannot prove the absence of future dynamic importers;
  the full suite remains mandatory.
