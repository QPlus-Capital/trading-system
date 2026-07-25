# P-06: Identify significant candidates with Romano-Wolf

## Problem

P-05 establishes whether the 36-candidate family contains edge, but Stage 1 has no
familywise-error-controlled evidence identifying which individual candidates have positive mean
daily net R.

## Goal

Implement Romano-Wolf's one-sided studentized max-t stepdown procedure over the canonical P-03
candidate matrix and persist lineage-bound per-candidate adjusted p-values and eligibility for
P-08.

## Non-goals

- Consuming the new eligibility in selection; P-08 owns that decision rule.
- Changing SPA, DSR, PBO, ranking, portfolio, reporting, or live behavior.
- Changing P-03 return persistence or P-04 resampling and block selection.
- Adding a single-step, Holm, false-discovery-rate, or two-sided procedure.
- Making any observed candidate eligible by changing the fixed threshold.

## Statistical specification

- The input is the exact P-03 `candidate_daily_returns.csv` matrix validated through P-05's
  `load_candidate_family`: 36 formal `(variation, train_months)` candidates, common prop-loss-day
  grid, daily net R, and zero benchmark.
- For candidate `k`, use `T_k = sqrt(n) * mean_k / sqrt(long_run_variance_k)`. Expose and reuse
  P-05's matrix validation, stationary-bootstrap index, long-run-variance, and studentized-score
  kernels in `research/engine/spa.py`; P-06 must not implement a second bootstrap or variance.
- The edge stage passes P-05's selected block length, production replication count, and seed to
  P-06. Because both analyses call the same index kernel with the same matrix shape and parameters,
  their selected-length bootstrap day-index matrix is bit-identical. Production remains 10,000
  replications with seed 20260719.
- The Romano-Wolf bootstrap null score is
  `T*_bk = sqrt(n) * (bootstrap_mean_bk - mean_k) / sqrt(long_run_variance_k)`.
  This is the one-sided zero-null statistic; Hansen's inferior-candidate recentering remains
  specific to SPA and is not applied to individual Romano-Wolf hypotheses.
- Order hypotheses by descending observed `T_k`, breaking exact ties by candidate identifier.
  At ordered rank `j`, calculate
  `raw_step_p_j = (1 + count(max_{l >= j}(T*_{b,r_l}) >= T_{r_j})) / (B + 1)`.
  Enforce stepdown monotonicity with
  `adjusted_p_j = max(adjusted_p_{j-1}, raw_step_p_j)`.
  This is the adjusted-p-value dual of recomputing the max-null over the unrejected family after
  each rejection.
- The unadjusted one-sided p-value uses the same finite Monte Carlo rule against candidate `k`'s
  own bootstrap scores. Each adjusted p-value must be at least its unadjusted p-value.
- Eligibility is exactly `Decimal(str(adjusted_p)) <= Decimal("0.05")`; serialized flags are
  re-derived and verified on read.

## Behavioural requirements

- Add `research/engine/romano_wolf.py` with pure computation, strict result validation, and
  deterministic serialization.
- Persist `romano_wolf.json` atomically in the edge-stage manifest beside `spa.json`.
- The artifact records schema, method, zero benchmark, positive one-sided tail, exact alpha,
  block length, replications, seed, counts, ordered candidate statistics, unadjusted and adjusted
  p-values, and eligibility.
- Missing, non-finite, degenerate, incomplete, inconsistent, or malformed inputs fail closed.
- P-06 is additive evidence only. Stage 2 must not read it until P-08.

## Acceptance criteria

- AC-01: Under a global null of 36 noise candidates, probability of at least one eligibility flag
  is approximately 5% within the predeclared synthetic tolerance.
- AC-02: Adjusted p-values are nondecreasing in descending observed-statistic order, including
  deterministic ties.
- AC-03: Every adjusted p-value is greater than or equal to its corresponding unadjusted p-value.
- AC-04: One strongly positive candidate is eligible while all zero-edge candidates are not.
- AC-05: Two correlated positive candidates are both eligible in a deterministic fixture where
  the second candidate's single-step max-t p-value exceeds 0.05.
- AC-06: Identical input, block length, replications, and seed produce bit-for-bit identical
  results and serialized evidence.
- AC-07: P-05 and P-06 use the same P-04 stationary-bootstrap draw for matching matrix, block
  length, replications, and seed.
- AC-08: The edge stage publishes lineage-bound `romano_wolf.json` with all 36 formal candidates.
- AC-09: Serialized flags, ordering, counts, p-value bounds, monotonicity, and adjusted-versus-
  unadjusted constraints are verified fail closed.
- AC-10: Existing research and live numbers do not change; Stage 2 does not consume the artifact.
- AC-11: `just check` and every required R3 gate pass.

## Invariants

- INV-01: P-03's daily net-R bytes remain the sole return input.
- INV-02: P-05 SPA and P-06 Romano-Wolf share the same paired bootstrap day indices at the selected
  block length.
- INV-03: The formal family remains exactly 36 `(variation, train_months)` hypotheses against zero.
- INV-04: Stepdown maxima contain only the current hypothesis and hypotheses not yet stepped down.
- INV-05: Adjusted p-values are monotone, dominate unadjusted p-values, and gate at exactly 0.05.
- INV-06: The artifact is lineage-bound, deterministic, and not consumed by selection in P-06.
- INV-07: No existing statistic, ranking, trade, portfolio, signal, risk, or live calculation moves.
- INV-08: Generated report artifacts remain gitignored; no data or secret is committed.

## Risk class

R3. The planned-path classifier assigns R3 because this adds a critical statistical methodology
and result-integrity artifact under `research/engine/**` and `research/stages/**`.

## Scope

- Add one pure Romano-Wolf engine module.
- Promote only the existing P-05 statistical kernels needed for reuse; preserve SPA behavior.
- Add atomic edge-stage publication without selection consumption.
- Add focused unit, property, calibration, lineage, mutation, and documentation guards.
- Update architecture and methodology documentation, quality configuration, and this task
  artifact.

## Assumptions

- P-03 has already enforced the common daily grid, candidate identity, and net-R semantics; P-06
  reuses P-05's strict loader at the stage trust boundary.
- P-04's selected mean block length and deterministic stationary bootstrap are valid inputs to
  both P-05 and P-06 under the fixed package design.
- P-08 will verify the lineage-bound artifact through `RomanoWolfAnalysis.from_dict` before using
  candidate eligibility.

## Expected artifacts

- `research/engine/romano_wolf.py`.
- A generated, lineage-bound `romano_wolf.json` in each new complete edge-stage run.
- Shared P-05 bootstrap-kernel API, focused statistical and stage guards, mutation coverage,
  updated methodology/architecture documentation, and this five-file task artifact.

## Human decisions

Issue #48 and Jan's build instruction fix the family, null, tail, statistic, resampling convention,
stepdown procedure, threshold, persistence boundary, and no-number-change requirement. Jan retains
methodology and merge authority; Claude performs independent review.

## Open questions

None. The paper notes that block size can be recalibrated at each step, but this package
deliberately uses P-05's one selected P-04 length at every step because issue #48 requires one
coherent shared bootstrap draw.

## Human decisions required

No implementation choice remains open. Jan must approve any later use of this artifact and every
merge.
