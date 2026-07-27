# P-11: Gate on loss-day path breach probabilities

## Problem

`research/stages/verdict.py::main` gates deployment on `P(profit) >= 0.60`, a statistic that has
been 100% in every completed run and does not measure the probability of violating either the
internal or prop-firm account limits. Claude's independent review additionally found that the first
P-11 implementation replayed compounded Stage-3 absolute money changes against unrelated path
balances, inflating daily-breach probabilities from zero observed breach days.

## Goal

Replay every complete P-10 stationary-bootstrap path through the internal and prop-firm daily and
trailing limits, then replace the probability-of-profit gate with exact one-sided binomial bounds
on any internal breach and on a negative final return. Persist each scenario day's source opening
balance and replay every money delta as a fraction of that source scale.

## Non-goals

- Rebuilding P-10 source indices, stationary bootstrap, or block-length selection.
- Changing P-09 H4 diagnostics, trade extraction, sizing, signals, selection, costs, return
  calculations, tail caps, account limits, confidence levels, or gate thresholds.
- Removing `P(profit)` as a reported diagnostic.
- Changing Stage 1 or Stage 2, or changing Stage-3 trades, sizing, or reported metrics.

## Behavioural requirements

- P-11 consumes `research.portfolio.scenarios.sample_scenario_paths`,
  `scenario_bootstrap_choices`, and `scenario_path_probability_of_profit`; it does not implement
  another scenario, bootstrap, block-choice, or profit convention.
- The loss-day CSV schema is version 2 and carries each day's positive source opening balance.
  Readers reject old, unversioned, and unsupported artifacts instead of assuming a denominator.
- Each sampled path starts from the configured account start balance. Opening-to-minimum,
  closing-balance, and close-equity changes are divided by the source opening balance and scaled by
  the path day's opening balance. Balance therefore compounds multiplicatively.
- Each day's synthetic minimum uses its source-scaled opening-to-minimum fraction. Daily breaches
  use that minimum, so a positive close cannot erase an intraday breach.
- Daily limits are inclusive: equity at or below the corresponding floor is a breach, matching
  `live.risk_control.RiskController.must_flatten`.
- The realized-balance high-water mark includes the same day's close before the trailing floor is
  checked, matching P-09's deliberately conservative `drawdown.trailing_floor` semantics.
- Four path-level breach flags are retained: internal daily `2.5%`, internal trailing `5%`, prop
  daily `3%`, and prop trailing `6%`. The corresponding any-limit flags are their unions.
- P-11 asserts at both path and aggregate level that internal daily, trailing, and any-limit
  breaches cannot be less frequent than their prop-hard counterparts.
- The plug-in block result gates. Fixed 5/10/20/60 results remain sensitivity diagnostics.
- Gate 1 passes only when the exact one-sided 95% Clopper-Pearson upper bound on the probability
  of any internal-limit breach is at most `0.01`.
- Gate 2 passes only when the exact one-sided 95% Clopper-Pearson upper bound on the probability
  of a negative final balance return is at most `0.05`.
- Clopper-Pearson is computed by monotone bisection of the exact Decimal binomial CDF. Returning
  the upper bracket makes the numerical result conservative at finite precision.
- `P(profit)` is persisted and printed as a diagnostic but is absent from the verdict checks.
- Final-return and maximum-drawdown 5th/median/95th percentiles use empirical nearest ranks.
  Expected shortfall at 5% is the exact mean of the worst `ceil(0.05 * replications)` returns.
- Time under water is the fraction of path days whose close equity is below its running close-
  equity high-water mark; its 5th/median/95th percentiles are reported.

## Acceptance criteria

- AC-01: A deterministic no-loss fixture reports zero raw breach frequency and a strictly
  positive one-sided 95% Clopper-Pearson upper bound.
- AC-02: With one 3% breach day among ten and independent one-day blocks, the simulated internal
  and prop daily-breach probabilities agree with `1 - (9/10)^10` within pre-declared Monte-Carlo
  tolerance.
- AC-03: Internal daily, trailing, and any-limit breach probabilities are always greater than or
  equal to the corresponding prop-hard probabilities; an impossible result fails closed.
- AC-04: A path that breaches at its intraday minimum and closes profitably remains breached.
- AC-05: Exact-binomial fixtures for `x=0,1,5` successes out of `n=10` match trusted
  Clopper-Pearson upper limits within `1e-12`.
- AC-06: Stage 4 has no `P(profit)` gate and instead applies both exact upper-bound gates at
  `0.01` and `0.05`; `P(profit)` remains a labelled diagnostic.
- AC-07: Median, 5th/95th final return, ES(5%), drawdown percentiles, all four breach
  probabilities, any-limit probabilities, and time-under-water percentiles are serialized.
- AC-08: Fixed-seed path-risk results are bit-for-bit deterministic, and all five P-10 block
  choices remain present.
- AC-09: An integration test invokes the real `research.stages.verdict.main` path and proves the
  new gates, artifact, and diagnostic wiring execute.
- AC-10: Rerun the affected stages on the current baseline and write
  `reports/research/regression/52-comparison.json` with zero trade-count and annual-return
  tolerances and no unexpected changes.
- AC-11: `portfolio_trades.csv` and `full_history_trades.csv` remain byte-identical; trade count,
  return, expectancy, Sharpe, and tail cap remain exact. Record old/new path estimates and verdict.
- AC-12: Every cumulative R3 gate passes with current-HEAD evidence.
- AC-13: A day with a fixed source loss fraction produces the same daily-breach decision at two
  different path balances.
- AC-14: Bootstrap paths made only from observed sub-limit days have zero raw daily-breach
  frequency, while the exact upper confidence bound remains positive.
- AC-15: Stage 3 emits schema version 2 with source opening balances; the reader rejects the
  previous unversioned schema and every unsupported explicit version.

## Invariants

- INV-01: The P-10 scenario rows and P-04 stationary-bootstrap implementation remain authoritative.
- INV-02: Intraday breach tests use P-09's synchronized H4 opening-to-minimum field, never a close-
  only proxy or reconstructed price path.
- INV-03: Internal limits stay strictly tighter than prop limits: `2.5% < 3%` and `5% < 6%`.
- INV-04: A prop-hard breach without its corresponding internal breach raises and cannot produce a
  verdict.
- INV-05: Gate bounds and money arithmetic use `Decimal`; no normal approximation is accepted.
- INV-06: Zero observed events produce a positive Clopper-Pearson upper bound.
- INV-07: Only the plug-in result gates; sensitivity results and `P(profit)` are diagnostics.
- INV-08: No trade, return, expectancy, Sharpe, tail-cap, P-09 diagnostic, selection, or live path
  changes.
- INV-09: No absolute scenario money change is applied to a path until it is normalized by the
  same row's positive source opening balance.
- INV-10: Scenario artifacts without an explicit supported schema version fail closed.

## Assumptions

- P-10's complete daily deltas plus their source opening balances are the registered resampling
  unit and are sufficient to replay balance, close equity, and intraday minima in a synthetic order.
- The P-09 trailing-floor convention deliberately includes the same day's realized close in its
  high-water mark and is retained for exact parity.
- A final return of exactly zero is not negative; `P(profit)` continues to require strictly
  positive final return.

## Open questions

None.

## Expected artifacts

- `research/portfolio/path_risk.py`.
- Version-2 `loss_day_scenarios.csv` from the unchanged Stage-3 account path.
- Extended `path_bootstrap.json` and `verdict.json` path-risk evidence.
- Focused unit, property, mutation, and real-verdict integration tests.
- `reports/research/regression/52-comparison.json`.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because the work changes account-limit probability
math and replaces a Stage-4 deployability gate.

## Human decisions required

Jan fixed all four limit levels, the exact one-sided 95% Clopper-Pearson construction, the `1%` and
`5%` gate thresholds, the requirement that `P(profit)` cease gating, the zero-tolerance regression,
the source-relative replay and fail-closed schema migration, and Jan-only merge authority. No
unresolved methodology or risk decision is delegated to the implementer.
