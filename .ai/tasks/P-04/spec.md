# P-04: Stationary bootstrap and Politis-White block length

## Problem

The repository has no shared resampler for serially dependent daily net returns, so later
statistical packages would either use an invalid IID bootstrap or duplicate an estimator.

## Goal

Provide a pure NumPy corrected Politis-White stationary-bootstrap block-length selector and a
deterministic Politis-Romano stationary bootstrap for future consumers, without wiring a consumer or
moving any reported number.

## Non-goals

- No changes to `research/engine/montecarlo.py`, `research/stages/lineage.py`, any stage, selection,
  verdict, configuration, artifact, CLI, or live path.
- No pipeline wiring, persistence, P-03 coupling, confidence-interval API, or reported-number change.
- No circular/moving-block bootstrap implementation beyond circular indexing inside the stationary
  bootstrap.

## Behavioural requirements

- Accept only one-dimensional, finite, non-empty in-memory NumPy-compatible daily net-return
  streams; candidate streams must share one length and already include zero-return days.
- Compute each raw stationary-bootstrap estimate from the Politis-White (2004) flat-top plug-in with
  the Patton-Politis-White (2009) correction: biased full-sample autocovariances, automatic bandwidth
  from the first run of insignificant autocorrelations, `G` from lag-weighted autocovariances,
  corrected `D_SB = 2 * sigma_hat**4`, and no silent block-length cap.
- Set production `L = max(1, ceil(max(candidate estimates)))`. If `L > floor(T / 10)`, raise an
  explicit exception containing `L`, `T`, and the candidate whose estimate determined `L`.
- Generate stationary-bootstrap samples by starting uniformly, restarting independently with
  probability `1 / L`, otherwise advancing one circular index; geometric blocks therefore have
  mean `L` and every original index has equal marginal weight.
- Default to seed `20260719` through `np.random.default_rng` and 10,000 replications; fixed seed and
  inputs reproduce bit for bit.
- Expose sensitivity at fixed mean block lengths 5, 10, 20, and 60 without pipeline or artifact I/O.

The bandwidth procedure is fixed as follows: `k_n = max(5, floor(log10(T)))`,
`m_max = min(ceil(sqrt(T)) + k_n, T - 1)`, and the insignificance band is
`+/- 2 * sqrt(log10(T) / T)`. The first `k_n` consecutive autocorrelations inside that band chooses
`m_hat`; the flat-top bandwidth is `M = min(2 * max(m_hat, 1), m_max)`, or `m_max` when no run is
found. This is the published reference procedure and corrected stationary constant; the separate
`T/10` rejection replaces any hidden implementation cap.

## Acceptance criteria

- AC-01: A fixed AR(1) fixture matches a hard-coded independently calculated corrected
  Politis-White estimate, and seeded white noise selects a block length near one.
- AC-02: The multi-candidate selector takes the ceiling of the maximum estimate, retains minimum one,
  requires the common daily grid, and fails closed above `floor(T/10)` naming `L`, `T`, and candidate.
- AC-03: Observed non-truncated stationary-bootstrap run lengths match the requested geometric mean
  within simulation error, and invalid lengths/replications/input arrays fail explicitly.
- AC-04: Resampling wraps circularly, does not systematically underweight any observation, preserves
  shape, and is bit-for-bit deterministic for the default and explicit seed.
- AC-05: Sensitivity exposes exactly mean lengths 5, 10, 20, and 60; public defaults remain seed
  20260719 and 10,000 replications.
- AC-06: Across 1,000 seeded IID Gaussian experiments, a nominal 95% studentized interval for the
  mean covers zero within 95% +/- 1.5%.
- AC-07: Across 1,000 seeded stationary AR(1) experiments with phi 0.5, a stationary-bootstrap
  percentile-t interval covers zero within 95% +/- 2%, while the local IID negative control
  under-covers.
- AC-08: Architecture documentation and mutation scope include the new utility; all R3 gates pass.

Calibration uses 299 bootstrap replications per experiment to keep CI bounded. The IID interval is
studentized by the ordinary sample standard error. The AR interval uses stationary mean block length
10 and a local Bartlett-HAC standard error with lag 10 for both original and bootstrap samples; the
IID negative control uses its ordinary standard error. These choices test the resampler rather than
add an unrequested production confidence-interval implementation.

## Invariants

- INV-01: The module is additive and pure: no I/O, global RNG state, pipeline import, or mutation of
  caller-owned arrays.
- INV-02: No reported number, frozen configuration, holdout, stage, lineage, Monte Carlo, selection,
  verdict, live, or monitoring path changes.
- INV-03: Every stochastic test and public default is deterministic; sensitivity keys never drift.
- INV-04: Non-finite, empty, non-1D, mismatched-grid, zero/negative replication, and invalid block
  length inputs fail closed.
- INV-05: Mutation testing covers the estimator/selector and stationary resampler without weakening
  the existing mutation ratchet or another quality gate.

## Assumptions

- Callers provide aligned daily net returns, including zero days; calendar alignment is outside this
  pure utility.
- Floating NumPy arrays are appropriate for dimensionless statistical return streams, not money,
  prices, quantities, or booked P&L.

## Open questions

None. The pinned Claude build contract and the cited primary procedures resolve placement, scope,
constants, defaults, and rejection policy.

## Expected artifacts

- `research/portfolio/resample.py`, focused and property/calibration tests, architecture-map entry,
  mutation target/baseline updates, and the five `.ai/tasks/P-04/` files.

## Risk class

R3 — `scripts/quality/classify.py` classifies `research/portfolio/resample.py` as result-integrity
code under `research/portfolio/**`; the mutation policy and dependency configuration are also R3.

## Human decisions required

Jan retains methodology, scope, risk, and merge authority. No autonomous merge is permitted.
