# P-13: Forward-test decision protocol

## Problem

`research/forward_test_registry.py` records immutable cohorts and daily net portfolio R but has no
fixed, suppression-safe efficacy or futility decision protocol.

## Goal

Add one read-only decision module that consumes the P-12 registry and P-04 stationary bootstrap,
enforces Jan's Option A daily-series design, and cannot disclose an efficacy verdict before the
fixed endpoint.

## Non-goals

- Adding or changing registry data, cohort enrollment, dashboard wiring, live execution, research
  stages, strategy parameters, risk limits, or reported historical numbers.
- Modifying `research/forward_test_registry.py` or `research/portfolio/resample.py`.
- Retuning the endpoint, trade counts, confidence levels, edge threshold, block lengths, seed, or
  bootstrap replication default.
- Treating an operational hard safety stop as a statistical efficacy decision.

## Behavioural requirements

- Read a cohort and its `ObservationSeries` through `ForwardTestRegistry`; cumulative realized
  trade count and the as-of date are explicit caller inputs.
- Use observations through the as-of date only and reject invalid dates, counts, non-finite daily
  values, source/cohort mismatches, or observations before the cohort start.
- The efficacy endpoint is both the 30-calendar-month anniversary and 2,400 realized trades.
- Before that endpoint, return `NO_DECISION` without exposing efficacy bounds, except that the
  separately named `FUTILITY_STOP` is permitted at both 18 calendar months and 1,400 trades when
  the one-sided 99% upper bound is strictly below zero.
- At the endpoint, return `PASS` only when the one-sided 95% lower bound is strictly greater than
  the daily threshold, `FAIL` only when the one-sided 95% upper bound is strictly less, and
  `INCONCLUSIVE` otherwise.
- Compute `daily_threshold` exactly as
  `Decimal("0.10") * realized_trade_count / observation_day_count`.
- Select the production block length with P-04 `select_block_length`, resample with P-04
  `stationary_bootstrap`, use P-04 `DEFAULT_SEED`, retain the 10,000 production default, and report
  sensitivity at every P-04 `SENSITIVITY_BLOCK_LENGTHS` value.
- Bootstrap resampling uses integer observation indices; bootstrap means, empirical percentile
  ranks, thresholds, and comparisons are computed with `Decimal`. This consumes P-04 without
  converting the exact registered R values into binary floating-point statistics.
- One-sided bounds use the literal empirical percentile construction: the lower bound is the
  `(1-confidence)` nearest-rank bootstrap-mean quantile and the upper bound is the `confidence`
  nearest-rank quantile. This is the direct non-studentized interpretation of the issue's
  stationary-bootstrap bound; strict comparisons make equality inconclusive.
- Calendar anniversaries clamp month-end to the last valid day of the target month.

## Acceptance criteria

- AC-01: A cohort below either 30 calendar months or 2,400 trades returns only `NO_DECISION` and
  exposes no efficacy bounds, even when its data would pass or fail.
- AC-02: At the endpoint, lower 95% above threshold yields `PASS`, upper 95% below threshold yields
  `FAIL`, and overlap or equality yields `INCONCLUSIVE`.
- AC-03: `FUTILITY_STOP` occurs only at both 18 months and 1,400 trades and only when the 99% upper
  bound is strictly below zero; all other interim cases remain suppressed.
- AC-04: The daily threshold is exact `Decimal("0.10") * trades / observed days`, with zero and
  invalid denominators rejected.
- AC-05: Production uses P-04's selected block length, fixed default seed and 10,000 default
  replications, and returns 5/10/20/60-day sensitivity results.
- AC-06: Realized trade count and as-of date are mandatory explicit inputs; observations after the
  as-of date cannot enter a bound.
- AC-07: An operational stopped cohort produces the same statistical result as an otherwise
  identical active cohort, and evaluation does not rewrite either registry artifact.
- AC-08: No public result path or dashboard consumer exposes `PASS` or `FAIL` before the endpoint.
- AC-09: A deterministic clustered power fixture reproduces approximately 1.1-1.2 calendar years
  for a 0.15R edge and 2.5-2.7 years for a 0.10R edge.
- AC-10: Full R3 checks, deterministic properties, focused decision mutation, security, and
  readiness pass without changing any recorded research number.

## Invariants

- INV-01: P-12 registry and P-04 resampling code and their persisted artifacts remain unchanged.
- INV-02: Every efficacy verdict requires both endpoint conditions; neither condition substitutes
  for the other.
- INV-03: Pre-endpoint public results contain no efficacy bound or PASS/FAIL-shaped state.
- INV-04: Daily-R values, means, bounds, thresholds, and trade-count arithmetic remain `Decimal`;
  binary floats never carry a statistical value in the decision module.
- INV-05: Futility is a distinct early safety decision and cannot be relabelled as efficacy
  `FAIL`.
- INV-06: Fixed-block sensitivity is diagnostic only; the selected production block alone governs
  the verdict.
- INV-07: Evaluation is read-only and does not alter cohort status, observations, live safety, or
  any trading process.

## Assumptions

- The registry producer appends the complete daily grid, including zero-return days, as required
  by P-04; P-13 counts the observations supplied and does not invent missing days.
- The caller supplies a cumulative realized trade count corresponding to the same as-of cutoff.
- Bootstrap percentile bounds are the intended literal construction because the build contract
  specifies stationary-bootstrap one-sided bounds without studentization or BCa adjustment.

## Open questions

The P-12 schema stores generic named thresholds and a minimum duration in days, but the build
contract does not define an enrollment key for P-13's per-trade threshold or a day count equivalent
to 30 calendar months. P-13 therefore applies the fixed protocol constants and reports the
immutable registered values without guessing a mapping. An operational cohort-enrollment package
must specify those registry names/values before wiring a caller.

Option A, endpoint, decision thresholds, confidence levels, seed, sensitivity lengths, and
suppression behaviour are otherwise fixed by Jan and Claude's pinned build contract.

## Expected artifacts

- `research/forward_decision.py`, focused behavioural/property/power tests, one architecture-map
  entry, focused mutation policy and ratchet entries, and this five-file task artifact.

## Risk class

R3 by semantic upgrade: `research/forward_decision.py` has an R2 path minimum, but it governs
methodology and forward-test result integrity. Mutation-policy, baseline, and `pyproject.toml`
changes also classify R3. Full cumulative R3 gates apply.

## Human decisions required

Option A is already decided by Jan. Jan approves the merge; Claude independently reviews this R3
P-package. No autonomous merge is permitted.
