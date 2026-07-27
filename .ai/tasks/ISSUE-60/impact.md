# Impact analysis

## Direct impact

- `research/portfolio/stats.py::_market_trades` changes its broker-aware output schema from a
  mislabelled swap-netted `r` to gross `r`, separate `swap_r`, and derived `net_r`.
- `core/broker.py` changes only the swap helper's algebraic docstring from the obsolete
  `r += swap_r` notation to the canonical `net_r = r + swap_r`; runtime behaviour is unchanged.
- `.ai/quality/finding-patterns.toml` records the generalized confirmed-defect pattern required by
  constitution section 14.
- `tests/test_research_stats.py` gains execution-path guards using a real `BrokerProfile` and
  `SwapSpec` with only the engine boundary replaced by deterministic fakes.

## Transitive impact

Repository-wide caller enumeration for `_market_trades`:

1. `research/portfolio/swap_analysis.py::main` is the only production caller. It deliberately calls
   `_market_trades(..., broker=None)`, because it first refreshes swap terms from MT5 and then
   `market_swaps` applies that newly pulled `SwapSpec`. It wants gross `r`; its current `trades["r"]`
   read is correct and must remain gross. Passing the broker here or reading `net_r` would charge
   swap twice.
2. The new behavioural tests call `_market_trades` with a broker specifically to exercise the
   defective dormant branch. They require both gross and net columns.
3. No other production, test, script, or dynamic caller exists. `rg` finds only the definition,
   the `swap_analysis.main` call, and the new tests.

Reconciliation with deployed reporting:

- Stage 1 uses `research.engine.continuous.stage1_trade_returns`, which already emits gross `r`,
  separate `swap_r`, and derived `net_r`.
- Stage 3 uses `research.portfolio.trades.make_extract_fn` /
  `extract_market_trades`, attaches `swap_r` in `research.stages.portfolio`, and never imports or
  calls `_market_trades`.
- Stage 4 reads Stage-3 artifacts and `research.portfolio.risk.net_r`; it does not call
  `_market_trades`.
- `factsheet.py` and `verdict.py` import only `edge_stats` and `risk_stats` from `stats.py`; neither
  calls `_market_trades`.
- Live execution imports no research portfolio statistics.

Therefore the defect is an analysis-helper schema violation on a currently dormant broker-aware
branch. Correcting it changes no existing report number. The operator-only swap report continues to
produce the same gross/swap/net values because its sole caller intentionally requests gross trades
and applies the freshly pulled swap exactly once.

## Critical dependencies

- `core.broker.swap_r_per_trade` remains the sole swap calculator for this helper.
- `research.portfolio.trades.timed_trades_from_report` remains the sole closed-trade extractor.
- Constitution section 4 and the Stage-1 `stage1_trade_returns` schema define the gross/separate/net
  convention.
- `research.portfolio.trades.py`, all stages, `live/**`, and both persisted trade CSV schemas are
  outside the change.

## Unknown or dynamic edges

`_market_trades` accepts arbitrary factories and executes a Nautilus backtest, so the engine boundary
is dynamic. Its repository call graph is nevertheless statically complete: there are no callback
registrations, string imports, or exported plugin entry points for this private helper. External
Python callers of the private function could observe the corrected broker-aware schema; they must
use `net_r` for statistical return rather than the now-correct gross `r`.

The caller audit also found that `swap_analysis.market_swaps` ignores the available `is_long`
column. That is a separate direction-attribution defect capable of moving the operator-only report,
so it is not folded into this exact-no-drift package; issue #95 tracks it.

## Coupled quantity

The coupled quantity is per-trade return attribution:

1. engine realized PnL -> `r_multiples` -> gross `r`;
2. closed trade timestamps, direction, stop distance, and broker spec -> `swap_r_per_trade` ->
   realized `swap_r`;
3. statistical return -> exact vector sum `net_r = r + swap_r`;
4. analysis caller explicitly chooses gross and swap separately.

All consumers are reconciled in one pass; none is silently left reading a newly changed semantic.

## Expected numerical impact

- Existing Stage-1 through Stage-4 metrics: exactly none.
- `portfolio_trades.csv` and `full_history_trades.csv`: byte-identical.
- `swap_analysis` output: exactly unchanged.
- Direct callers that previously passed a broker: `r` increases/decreases back to its gross value
  by `-swap_r`; their intended statistical return is preserved in `net_r`.

## Initial classification and impact

The explicit planned-path classifier returns R3 with all fourteen cumulative gates. Before changes,
`just impact origin/main` reports R0 because there is no diff; final impact evidence is recorded
after the implementation exists.
