# P-05: Add Hansen's SPA family gate

## Problem

Stage 2 has no decision-grade family-level test of whether any of the 36 correlated formal
candidates has positive expected daily net R relative to zero.

## Goal

Implement Hansen's one-sided, studentized Superior Predictive Ability test with consistent
recentering over the canonical P-03 daily candidate matrix, report dependence sensitivity, and
make it a fail-closed Stage-2 auto-selection gate.

## Non-goals

- Replacing or weakening the existing DSR, PBO, eligibility, consistency, or risk gates.
- Changing candidate identity, Stage-1 scoring, return persistence, rankings, portfolio
  construction, any reported trading number, or any live path.
- Implementing White's Reality Check or reporting SPA lower/upper recentering diagnostics as the
  decision test.
- Changing P-03 candidate streams or P-04 resampling APIs.
- Making the current research run pass.

## Behavioural requirements

- The family is the 36 P-03 formal `(variation, train_months)` candidates. Each observation is a
  shared prop-loss day and each value is the persisted flat-risk daily net-R return; the benchmark
  is exactly zero.
- For candidate `k`, the observed statistic is
  `sqrt(n) * mean_k / sqrt(long_run_variance_k)`. The family statistic is the positive part of
  the maximum candidate statistic.
- One paired Politis-Romano stationary-bootstrap row-index path is shared across all candidates.
  The selected mean block length comes from P-04 `select_block_length` on the same matrix; P-04
  `stationary_bootstrap` generates the paths. Production uses 10,000 replications and seed
  20260719.
- The long-run variance is Hansen's stationary-bootstrap covariance-weight estimator for
  `Var(sqrt(n) * mean_k)` at the same mean block length. This avoids a second nested simulation
  while preserving the Politis-Romano dependence kernel used for the p-value resamples.
- Hansen's consistent recentering retains a candidate's sample mean in the bootstrap null only
  when `mean_k <= -sqrt((variance_k / n) * 2 * log(log(n)))`; otherwise its bootstrap mean is
  recentered to zero. This prevents a clearly inferior candidate from enlarging the null maximum.
- The one-sided p-value uses the finite Monte Carlo form
  `(1 + count(T_bootstrap >= T_observed)) / (B + 1)`. Including ties is necessary because the
  positive-part statistic has a point mass at zero, and the add-one correction avoids impossible
  zero-probability claims. The exact gate comparison converts that probability to `Decimal` and
  requires `p <= Decimal("0.05")`.
- The selected block length and fixed 5/10/20/60-day sensitivity are all reported. Auto-selection
  passes the SPA family gate only when the selected-length result and every fixed sensitivity
  result pass at 0.05; significance at only one dependence choice is a finding, not a pass.
- A missing, malformed, non-finite, incomplete, non-common-grid, or non-36-candidate input fails
  closed. A forced variation may remain an explicitly exploratory selection only after SPA was
  successfully computed and reported; it does not turn a failed SPA result into a pass.

## Statistical specification

The equations, estimator, resampling convention, threshold, and sensitivity decision declared
under behavioural requirements are normative and must not be substituted during implementation.

## Acceptance criteria

- AC-01: Pure zero-edge candidate families produce approximately uniform SPA p-values and a
  5% false-positive rate within the predeclared synthetic calibration tolerance.
- AC-02: One genuinely positive candidate among zero-edge candidates produces a small one-sided
  p-value and passes the 0.05 gate.
- AC-03: Adding a strongly negative, high-variance candidate does not degrade a good candidate's
  consistent-recentered SPA p-value, while the equivalent least-favourable Reality Check does.
- AC-04: Positive rescaling of one candidate leaves the studentized statistic and p-value
  unchanged.
- AC-05: Identical input, block length, replication count, and seed produce bit-for-bit identical
  results.
- AC-06: The production analysis selects its block length with P-04 and reports p-values for that
  length and 5/10/20/60 days using 10,000 replications by default.
- AC-07: Stage 1 writes a lineage-bound `spa.json` beside the immutable P-03 evidence, and Stage 2
  reads that verified artifact instead of recomputing or accepting an unverified value.
- AC-08: Auto-selection aborts when SPA exceeds 0.05 at the selected length or any sensitivity;
  forced selection remains visibly exploratory and records the failed gate.
- AC-09: Missing or unreadable `candidate_daily_returns.csv`, inconsistent metadata, missing
  `spa.json`, and malformed SPA evidence all fail closed.
- AC-10: Existing study, ranking, return, drawdown, portfolio, and full-history numbers do not
  change.
- AC-11: `just check` and every required R3 gate pass.

## Invariants

- INV-01: P-03's daily net-R bytes are the sole return input; SPA never recomputes trade returns.
- INV-02: Candidate rows remain paired by the same bootstrap day indices.
- INV-03: Candidate identity remains `(variation, train_months)`; the 24 inner stop/target
  combinations and five manual trials are not promoted into this family.
- INV-04: The benchmark is zero and only positive edge can pass.
- INV-05: The gate threshold is exactly 0.05 and is never relaxed because current data fails.
- INV-06: DSR, PBO, candidate eligibility, and all trading metrics retain their existing values and
  logic.
- INV-07: No live, order, sizing, account, strategy-signal, holdout, or portfolio path is touched.
- INV-08: Generated run artifacts remain gitignored; only implementation, tests, docs, quality
  configuration, and task evidence are committed.

## Risk class

R3. Planned-path classification assigns R3 because this adds a Stage-2 selection gate, modifies
result-integrity lineage, and changes trading methodology documentation.

## Scope

- Add one pure SPA engine module.
- Compute and publish `spa.json` in the Stage-1 edge run from P-03 evidence.
- Require verified SPA evidence in Stage-2 selection and add the family gate.
- Add focused statistical calibration, corruption, determinism, stage-integration, mutation, and
  documentation guards.
- Update the architecture map, methodology, mutation scope, and this task artifact.

## Assumptions

- P-03 has already enforced the common date grid and exact net-R semantics. P-05 validates the
  serialized matrix and metadata again at its trust boundary.
- Bootstrap p-value Monte Carlo resolution is `1 / replications`; production's 10,000 draws are
  sufficient for a 0.05 gate, while tests use smaller deterministic samples.

## Open questions

None. The family, benchmark, test, recentering rule, dependence estimator, seed, production
replications, sensitivity lengths, and threshold are fixed by issue #47.

## Human decisions

Jan retains methodology, risk, go-live, architecture, and merge authority. A failed SPA gate is an
outcome and must not be converted into an implementation exception. Claude performs the
independent doubly rigorous review.

## Expected artifacts

- `research/engine/spa.py`.
- A generated, lineage-bound `spa.json` in each new complete edge-stage run.
- Stage integration, statistical calibration, corruption, determinism, mutation, and
  documentation guards.
- Updated architecture/methodology documentation and this five-file task artifact.

## Human decisions required

No implementation choice remains open. Jan retains merge and methodology authority; Claude owns
the independent review.
