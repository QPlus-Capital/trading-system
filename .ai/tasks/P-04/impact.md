# Impact analysis

## Direct impact

- Add `research/portfolio/resample.py` with pure estimator, selector, stationary resampler, and
  fixed-length sensitivity functions.
- Add focused behavioural/calibration/property tests and one architecture module-map row.
- Extend only mutation target inventory and its measured ratchet to cover the two new critical
  statistical functions; no gate threshold or execution rule changes.

## Transitive impact

Nothing imports the new module in this package. Future P-05 through P-08, P-10, and P-13 may consume
it, but no current stage, report, artifact, or live path does. The only current transitive consumers
are pytest, mypy, Ruff, vulture, documentation-map validation, and mutation tooling.

The final explicit impact run identifies `tests/test_research_resample.py`,
`tests/test_research_resample_calibration.py`, and `tests/test_research_resample_properties.py` as
direct tests, with no transitive test, critical-path escalation, or dynamic consumer.

## Critical dependencies

- NumPy `Generator` supplies uniform starts, Bernoulli restarts, and deterministic seeded draws.
- `scripts/quality/classify.py` sets R3; the existing mutation orchestrator reads the existing TOML
  policy and runs on Linux.
- The corrected constant follows Patton, Politis, and White (2009); the bandwidth and flat-top
  formula follow Politis and White (2004).

## Unknown or dynamic edges

None. There is no reflection, dynamic import, artifact lookup, configuration consumer, or pipeline
wiring. A final repository search and `just impact` must confirm no consumer was introduced.
