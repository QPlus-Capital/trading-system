# P-07: Construct a 90% Model Confidence Set

## Problem

The Stage-1 evidence can test the candidate family against zero, but it cannot distinguish which
of the 36 formal candidates are statistically indistinguishable from the best candidate.

## Goal

Implement the Hansen-Lunde-Nason one-sided-loss Model Confidence Set using the range statistic,
and persist lineage-bound 90% membership evidence for P-08 without changing selection yet.

## Non-goals

- Consuming MCS membership in Stage 2; P-08 owns that decision rule.
- Changing SPA, DSR, PBO, candidate ranking, portfolio construction, reporting, or live behavior.
- Changing P-03 candidate-return persistence or P-04 resampling and block selection.
- Substituting the maximum-loss statistic, pairwise tests, Holm, or false-discovery-rate control.
- Forcing a small surviving set when the data support all 36 candidates.

## Statistical specification

- Input is the exact P-03 `candidate_daily_returns.csv` matrix validated by P-05's
  `load_candidate_family`: 36 formal `(variation, train_months)` candidates on one common
  prop-loss-day grid. Loss is the negative of each daily net-R return.
- At every current model set `M`, define `d_ij,t = loss_i,t - loss_j,t`. The observed statistic is
  `t_ij = mean(d_ij) / sqrt(Var_bootstrap(mean(d_ij)))` and
  `T_R,M = max_{i,j in M} abs(t_ij)`.
- Reuse P-05's stationary-bootstrap long-run-variance helper on the pair-difference matrix.
  Because that helper estimates `Var(sqrt(n) * mean(d_ij))`, the denominator above is
  `sqrt(long_run_variance_ij / n)`.
- Reuse P-04's `stationary_bootstrap` through the shared P-05 index helper. The edge stage passes
  P-05's selected block length, production replication count, and seed, so P-05 and P-07 use a
  bit-identical paired day-index draw. Production remains 10,000 replications and seed 20260719.
- For bootstrap replication `b`,
  `t*_b,ij = ((mean*_b(d_ij) - mean(d_ij)) /
  sqrt(Var_bootstrap(mean(d_ij))))`, and `T*_b,R,M` is the maximum absolute pair score over the
  current set. The finite Monte Carlo p-value is
  `(1 + count(T*_b,R,M >= T_R,M)) / (B + 1)`, reusing P-05's conservative tie-inclusive rule.
- The coherent range elimination rule is
  `e_R,M = argmax_i max_j t_ij`: eliminate the candidate with the greatest standardized excess
  loss relative to another survivor. Exact ties are broken by candidate identifier.
- Recompute the bootstrap range null over the remaining candidates after every elimination.
  Continue the nested sequence to the singleton to obtain model-level MCS p-values as required by
  Hansen-Lunde-Nason; the singleton step has p-value 1. Each candidate's MCS p-value is the running
  maximum of the set-level p-values through its elimination step.
- Confidence is exactly 90%, so alpha is `Decimal("0.10")`. A candidate is in the MCS exactly when
  `Decimal(str(mcs_p_value)) >= Decimal("0.10")`. This equals the set remaining at the first
  non-rejection and preserves the paper's monotone p-value interpretation.
- A single candidate returns as the sole survivor with MCS p-value 1. Exact-identical pair streams
  contribute a zero score; an unequal pair with effectively zero long-run variance violates the
  test assumptions and fails closed with the candidate names.

## Behavioural requirements

- Add `research/engine/mcs.py` with pure computation, strict result validation, and deterministic
  serialization.
- Persist `mcs.json` atomically in the edge-stage manifest beside `spa.json`.
- The artifact records schema, method, negative-return loss, range statistic, confidence/alpha,
  block length, replications, seed, candidate/observation counts, every nested step, elimination
  order, model p-values, and membership flags.
- Missing, non-finite, degenerate, incomplete, inconsistent, or malformed evidence fails closed.
- P-07 is additive evidence only. Stage 2 must not read it until P-08.

## Acceptance criteria

- AC-01: Identical-distribution candidates retain essentially all candidates in a deterministic
  low-information fixture.
- AC-02: One strongly dominant candidate reduces the 90% MCS to that candidate.
- AC-03: The elimination order follows the coherent range rule and is reproducible.
- AC-04: Across repeated experiments, the known true-best candidate is retained in at least 90%
  of 90% MCS results within the predeclared calibration tolerance.
- AC-05: A single-candidate input returns that candidate with p-value 1 and never raises.
- AC-06: Identical input, block length, replication count, and seed produce bit-for-bit identical
  results and serialized evidence.
- AC-07: P-05 and P-07 use the same P-04 stationary-bootstrap draw for matching matrix, block
  length, replications, and seed.
- AC-08: The edge stage publishes lineage-bound `mcs.json` with all 36 formal candidates.
- AC-09: Serialized steps, identities, counts, p-value bounds/monotonicity, order, and membership
  flags are verified fail closed.
- AC-10: Existing research and live numbers do not change; Stage 2 does not consume the artifact.
- AC-11: `just check` and every required R3 gate pass.

## Invariants

- INV-01: P-03's daily net-R bytes remain the sole return input; loss is exactly their negation.
- INV-02: P-05 SPA and P-07 MCS share the same paired bootstrap day indices and selected length.
- INV-03: The formal family remains exactly 36 `(variation, train_months)` candidates.
- INV-04: Every range null and elimination score contains only the current surviving set.
- INV-05: MCS p-values are monotone and membership gates at exactly `p >= 0.10`.
- INV-06: The artifact is lineage-bound, deterministic, and not consumed by selection in P-07.
- INV-07: No existing statistic, ranking, trade, portfolio, signal, risk, or live calculation moves.
- INV-08: Generated report artifacts remain gitignored; no data or secret is committed.

## Risk class

R3. The planned-path classifier assigns R3 because this adds critical statistical methodology and
result-integrity evidence under `research/engine/**` and `research/stages/**`.

## Scope

- Add one pure MCS engine module.
- Promote only the existing P-05 bootstrap and variance kernels required for reuse, preserving SPA
  output bit-for-bit.
- Add atomic edge-stage publication without selection consumption.
- Add focused unit, property, calibration, lineage, mutation, and documentation guards.
- Update architecture and methodology documentation, quality configuration, and this task
  artifact.

## Assumptions

- P-03 already enforces the common daily grid, candidate identity, and net-R semantics; P-07
  reuses P-05's strict loader at the stage trust boundary.
- P-04's selected mean block length is the fixed dependence choice for the full MCS sequence.
- P-08 will verify the lineage-bound artifact through `McsResult.from_dict` before consuming
  membership.

## Expected artifacts

- `research/engine/mcs.py`.
- A generated, lineage-bound `mcs.json` in each new complete edge-stage run.
- Shared P-05 bootstrap-kernel API, statistical and stage guards, mutation coverage, updated
  methodology/architecture documentation, and this five-file task artifact.

## Human decisions

Issue #49 and Jan's build instruction fix the family, loss, range statistic, resampling convention,
confidence, elimination rule, persistence boundary, and no-number-change requirement. Jan retains
methodology and merge authority; Claude performs independent review.

## Open questions

None. The complete nested elimination path is computed after the fixed-alpha stopping set solely
to obtain the paper's model-level monotone MCS p-values; it does not change the 90% surviving set.

## Human decisions required

No implementation choice remains open. Jan must approve any later use of membership and every
merge.
