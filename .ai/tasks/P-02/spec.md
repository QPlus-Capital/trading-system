# P-02: Exclude training-window stop-time liquidations

## Problem

The training selectors in `research/portfolio/trades.py::_optimize` and
`research/engine/walkforward_runner.py::run_walkforward.optimize` inherit
`RsiWprBbConfig.flatten_on_stop=True`, so an engine-stop liquidation can enter Calmar parameter
selection as if it were a strategy exit.

## Goal

Set `flatten_on_stop=False` on both training-run configurations so a position still open at a
training boundary remains unrealized and is excluded by `extract_trade_pnls`.

## Non-goals

- Running Stage 1, creating or filling a `research/regression.py` comparison artifact, selecting
  regression thresholds, or reporting any research-number movement.
- Changing continuous OOS execution, full-history tail/statistics runs, the strategy default,
  signal logic, sizing, costs, walk-forward windows, selection metrics, live code, or monitoring.
- Claiming the methodology change is validated or merge-ready before Claude and Jan agree the
  regression thresholds and the deferred validation run passes.

## Behavioural requirements

- The Stage-1 training path passes `flatten_on_stop=False` in the parameter mapping supplied to
  `recipe.build_run_config`.
- The Stage-3 re-optimization training path passes the same explicit value.
- The value must override a recipe/base default if one is present; no global default changes.
- `extract_trade_pnls` continues to score only rows with a realized close, so an open position has
  no artificial training PnL.

## Acceptance criteria

- AC-01: A behavioral test drives the Stage-1 `run_walkforward` training optimizer and observes
  `flatten_on_stop is False` in every captured training config.
- AC-02: A behavioral test drives `research.portfolio.trades._optimize` and observes the same
  explicit value in every captured training config.
- AC-03: Existing continuous-OOS, window attribution, strategy stop behavior, and selection tests
  remain green without changing their production code.
- AC-04: `just check` passes, while Stage 1 and the regression artifact remain absent from this
  branch.

## Invariants

- INV-01: Only the two training selectors change production behavior.
- INV-02: `research/engine/continuous.py` remains the OOS source of
  `flatten_on_stop=False` and is not modified.
- INV-03: `research/regression.py`, reports, results, and Stage-1 artifacts are not modified or
  generated.
- INV-04: No live, monitoring, strategy, sizing, cost, signal, or risk-limit behavior changes.
- INV-05: No money value or numeric representation changes; existing Decimal money boundaries
  remain intact.

## Assumptions

- `extract_trade_pnls` already excludes positions whose `ts_closed` is missing; this package
  changes the training configuration that reaches that extraction rather than duplicating its
  filtering.
- The engine and existing strategy tests establish that `flatten_on_stop=False` leaves an open
  position unliquidated at `on_stop`.

## Open questions

Claude and Jan must agree the allowed Stage-1 regression thresholds for chosen parameters and
rankings before the approximately nine-hour validation run. The run and its
`research/regression.py` artifact are a separate remaining step and are deliberately not guessed
or executed here.

## Expected artifacts

- Two production mapping changes, one focused behavioral test module, and this task artifact.
- A draft pull request whose description names the deferred validation and regression artifact.

## Risk class

R3. Both production paths classify R3 because they govern training selection and the OOS trade
stream. The change can move selected parameters and every downstream research number.

## Human decisions required

Jan and Claude decide the regression thresholds and whether the later validation evidence is
acceptable. Jan alone approves any merge. This code-only draft must not merge or enable
auto-merge.
