# Impact analysis

## Direct impact

- Add pure path-risk replay and exact-binomial bound calculations under `research/portfolio/`.
- Version P-10's scenario CSV and add the source opening balance needed to normalize compounded
  money deltas before resampling.
- Stage 4 consumes P-10's existing bootstrap paths, replaces one non-discriminating check with two
  exact probability-bound checks, and expands its JSON/terminal diagnostics.
- Update methodology, architecture, critical dependency, mutation scope, and test maps.

## Transitive impact

The coupled quantity is the sampled loss-day path. Its complete producer/consumer chain is:

Every producer and consumer is handled in one pass:

1. `research/portfolio/sizing.py::DailyDiagnostics` creates the synchronized H4 daily minimum.
2. `research/stages/portfolio.py` and `research/portfolio/scenarios.py` persist one complete P-10
   day containing that minimum, the same day's balance/equity changes, and their source opening
   balance under an explicit schema version.
3. `research/portfolio/resample.py` owns Politis-White selection and stationary-bootstrap indices.
4. `research/portfolio/scenarios.py::sample_scenario_paths` applies those indices to indivisible
   scenario rows and remains the only path sampler.
5. `research/portfolio/path_risk.py` normalizes every money delta by its row's source opening
   balance, replays the relative path through all four limits, and derives final-return, drawdown,
   and time-under-water summaries.
6. `research/stages/verdict.py::main` consumes only the plug-in path's exact bounds for the two new
   gates, prints `P(profit)` as a diagnostic, and persists all risk evidence.
7. `path_bootstrap.json`, `verdict.json`, terminal output, and Stage-4 lineage expose the same
   selected result and sensitivities.
8. `research/regression.py` proves all trade and non-path portfolio quantities remain exact.

## Critical dependencies

- P-09 `DailyDiagnostics` is the sole source of synchronized H4 minimum equity.
- P-10 `LossDayScenario`, `scenario_bootstrap_choices`, and `sample_scenario_paths` remain the sole
  scenario schema, block-selection, and path-sampling implementations. Schema version 2 adds the
  denominator required by P-11; old artifacts are intentionally invalid.
- P-04 `select_block_length` and `stationary_bootstrap` remain transitively authoritative through
  P-10; P-11 does not duplicate either.
- `live.risk_control.RiskController.must_flatten` defines the inclusive limit boundary used by the
  research replay, but no live module is modified or invoked.

## Unknown or dynamic edges

`just impact origin/main` reported no unknown or dynamic edges. Runtime report consumers outside the
repository must regenerate the Stage-3 scenario CSV because the former unversioned format is
rejected. The existing top-level P-10 bootstrap fields remain present.

## Stage and artifact impact

- Stages 1-2 remain valid and cached. Stage 3 must rerun only to emit the version-2 scenario
  artifact; its trade streams, sizing path, and portfolio metrics must remain byte/exact identical.
- Stage 4 must be rerun because its gate and output schemas change.
- `path_bootstrap.json` retains P-10's seed, horizon, selected length, `P(profit)`, and five block
  choices while adding path-risk metrics and exact bounds.
- `verdict.json.passed` and its reason list may change by design.

## Numerical impact

Must remain exact:

- both trade CSV byte streams and trade count;
- total/annual return, hit rate, profit factor, payoff, expectancy, and Sharpe;
- P-09 realized path statistics, worst-day R, stress multiplier, and tail cap.

May move:

- bootstrap breach probabilities and bounds, final-return distribution, drawdown distribution,
  time under water, and the overall verdict;
- diagnostic `P(profit)` may move because it now uses compounded relative balance changes.

## Live and security impact

No `live/**`, signal, order, account, secret, credential, position-sizing, or execution path
changes. The four limits are read-only research replay constants and do not alter live controls.

## Failure modes

- Correct helper code that Stage 4 never calls.
- Persisting a source balance but continuing to add the absolute fields during replay.
- Scaling the daily minimum but leaving balance or equity additive, retaining the same distortion
  in final-return, drawdown, or time-under-water output.
- Accepting an old/unversioned CSV and silently assigning a start balance.
- Reimplementing P-10 source-index sampling or independently resampling scenario fields.
- Using close loss instead of opening-to-minimum loss, erasing recovered intraday breaches.
- Updating the trailing high-water mark in a convention different from P-09.
- Applying the 1% threshold to raw frequency rather than its upper confidence bound.
- Using a Wald/normal interval, which returns zero upper risk for zero events.
- Inverting the binomial tail or returning the lower bisection bracket, understating risk.
- Treating zero return as negative or as profitable.
- Gating on a fixed-block sensitivity or leaving `P(profit)` in the check list.
- Reporting prop breach frequency above internal without failing closed.
- Allowing a verdict change to mask drift in trades, returns, Sharpe, expectancy, or tail cap.

## Initial classification and impact

The explicit planned-path classifier command over `research/portfolio/scenarios.py`,
`research/stages/verdict.py`, and `docs/methodology.md` returned R3 with all fourteen cumulative
gates. The final `just impact origin/main` result will be recorded after the complete path and test
set exists.
