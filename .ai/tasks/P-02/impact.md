# Impact analysis

## Coupled training-run paths

1. Stage 1: `research/stages/edge.py` consumes the study produced by
   `research/engine/characterize.py::run_one`; that creates a `SweepRecipe` and calls
   `research/engine/walkforward_runner.py::run_walkforward`. Its nested `optimize` builds every
   per-window training config. P-02 adds `flatten_on_stop=False` to that mapping before
   `recipe.build_run_config`.
2. Stage 3 re-optimized extraction: `research/stages/portfolio.py` calls
   `research/portfolio/trades.py::make_extract_fn`, then `extract_market_trades`, then
   `_optimize`. `_optimize` independently builds every per-window training config. P-02 adds the
   same explicit value there.

These are the complete training-selector config paths found by auditing every
`build_run_config` call. Both currently inherit the strategy default
`RsiWprBbConfig.flatten_on_stop=True`; after P-02 both explicitly override it.

## Deliberately unchanged config paths

- `research/engine/continuous.py::run_continuous_oos` already passes
  `flatten_on_stop=False` for continuous OOS execution and candidate-matrix scoring.
- `research/portfolio/stats.py` and `research/portfolio/tail.py` build full-history runs, not
  per-window training selectors; their defaults remain unchanged.
- `research/engine/recipe.py::SweepRecipe.build_run_config` remains a neutral composition
  boundary. Changing its global default would silently affect every caller and is out of scope.

## Direct impact

- The final open position of each training run is no longer force-realized at the artificial
  engine boundary. Its unrealized PnL does not enter `calmar_score`.
- Candidate rankings can change at window seams. A changed selected parameter can move OOS
  returns by more than the omitted boundary trade, so no magnitude is asserted without Stage 1.

## Transitive impact

- Stage-1 study values, rankings, selected parameters, DSR/PBO inputs, and all later selection and
  portfolio artifacts may change when validation is eventually rerun.
- Stage-3 re-optimized trade extraction can choose different window parameters. Fixed-parameter
  extraction skips `_optimize` and is unaffected.

## Unknown or dynamic edges

- The direction and magnitude of result movement are intentionally unknown until the deferred
  Stage-1 comparison.
- Regression thresholds are a methodology decision pending Claude and Jan; no default is inferred.

## Critical dependencies

- `research.engine.recipe.scoring_params` composes the constant-basis training parameters. The
  explicit `flatten_on_stop=False` entry is applied after that mapping so neither a recipe default
  nor a stale candidate parameter can restore boundary liquidation.
- `research.engine.grid.extract_trade_pnls` is the shared realized-trade extractor. Its existing
  closed-trade filter is relied on rather than duplicated.
- `research.engine.continuous.run_continuous_oos` already owns the identical OOS setting and
  remains unchanged; the focused regression suite guards selection/execution parity.
- The deferred Stage-1 study and regression thresholds are critical to methodology acceptance but
  are not code dependencies and are outside this draft's execution scope.

## Tool result

`just impact origin/main` classifies the committed change R3 and identifies both production files,
the new behavioral test, three existing direct tests, and twelve transitive research/monitoring
tests. It reports no critical-path escalation, unknown/dynamic edge, or additional possibly
affected test, while retaining the mandatory full-suite warning.
