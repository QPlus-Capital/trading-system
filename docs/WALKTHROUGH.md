# Walkthrough — backtesting the RSI/Williams %R/Bollinger strategy

This guide explains what the project does today and how to use it: run a single
backtest, sweep many parameters, and produce a Monte-Carlo robustness chart. It is
written to be read top to bottom by someone new to the repo.

> **Prerequisites:** you have followed [RUN.md](../RUN.md) (uv, `uv sync`,
> NautilusTrader installed). All commands are run from the repo root.

---

## 1. The big picture

The pipeline has three cleanly separated layers. Data flows in one direction:

```
data_ingest  ->  catalog/        ->  a recipe (config/)      ->  runner / sweep / report
(import CSV)     (Parquet data)      (venue + data + params)     (run + analyse)
```

- **Strategy code** lives once in [src/qplus/strategies/](../src/qplus/strategies/)
  and never changes between experiments.
- **Recipes** in [config/backtest/](../config/backtest/) are where you turn the
  knobs (which instrument, which parameters). Editing numbers here is all you need
  to experiment — no code changes.
- **Data** lives in `catalog/` (a Parquet store, gitignored). It is imported once
  from a MetaTrader 5 CSV in `data/` (also gitignored).

Only two "config" concepts exist, both from NautilusTrader: `RsiWprBbConfig` (the
strategy's own parameters) and `BacktestRunConfig` (a whole run: venue + data +
strategy). See the diagram-style explanation in the strategy docstring.

---

## 2. What is where

| Path | What it is |
| --- | --- |
| [src/qplus/strategies/rsi_wpr_bb.py](../src/qplus/strategies/rsi_wpr_bb.py) | The strategy: signals (Williams %R / RSI / Bollinger), plus stop-loss, take-profit and risk-based position sizing. |
| [src/qplus/instruments.py](../src/qplus/instruments.py) | The XAUUSD (gold) instrument definition matching The Trading Pit's broker spec. |
| [src/qplus/data_ingest/mt5_csv.py](../src/qplus/data_ingest/mt5_csv.py) | Imports MetaTrader 5 "Export Bars" CSVs into the catalog. |
| [src/qplus/data_ingest/synthetic.py](../src/qplus/data_ingest/synthetic.py) | Generates deterministic synthetic bars (used by the tests, no real data needed). |
| [src/qplus/backtest/runner.py](../src/qplus/backtest/runner.py) | Runs one recipe and prints a result summary. |
| [src/qplus/backtest/sweep.py](../src/qplus/backtest/sweep.py) | Runs one strategy across a grid of parameter combinations and ranks them. |
| [src/qplus/backtest/montecarlo.py](../src/qplus/backtest/montecarlo.py) | Monte-Carlo maths (equity curve, drawdown, bootstrapped paths). |
| [src/qplus/backtest/report.py](../src/qplus/backtest/report.py) | Runs a recipe and saves the Monte-Carlo fan chart + stats. |
| [config/backtest/rsi_wpr_bb_xauusd.py](../config/backtest/rsi_wpr_bb_xauusd.py) | The main recipe: RsiWprBb on real XAUUSD H4. **Edit this to experiment.** |
| [config/backtest/sweep_rsi_wpr_bb_xauusd.py](../config/backtest/sweep_rsi_wpr_bb_xauusd.py) | The sweep study: which parameters and ranges to test. |
| `data/` | Raw MT5 CSV exports (gitignored). |
| `catalog/` | The Parquet data catalog (gitignored, built automatically). |
| `reports/` | Sweep CSVs and Monte-Carlo PNGs (gitignored). |

---

## 3. Getting the data

The strategy runs on real gold (XAUUSD) H4 bars exported from The Trading Pit's
MetaTrader 5 (broker: MEX Atlantic). The export lives at `data/XAUUSD_H4.csv`.

You do not need to import it by hand: the first time you run a backtest, the runner
sees the catalog is missing XAUUSD and imports the CSV automatically. To re-import
after replacing the CSV, delete the `catalog/` folder.

To export fresh/other data from MT5: **View → Symbols (Ctrl+U) → Bars tab**, pick the
symbol and timeframe, set the date range, **Request**, then **Export Bars** to a
`.csv` in `data/`.

---

## 4. Run a single backtest

```bash
uv run python -m qplus.backtest.runner config/backtest/rsi_wpr_bb_xauusd.py
```

This runs the strategy once and prints a summary at the very end (scroll to the
bottom):

```
===== Backtest result =====
total orders:    ...
total positions: ...
PnL [USD]:       ...  (...%)
```

The engine also logs a detailed statistics table above the summary (PnL stats,
returns, Sharpe, etc.).

---

## 5. Experiment: change parameters

Open [config/backtest/rsi_wpr_bb_xauusd.py](../config/backtest/rsi_wpr_bb_xauusd.py)
and edit the `config={...}` block of `STRATEGY`. The tunable knobs include:

- `stop_loss_pct`, `take_profit_pct` — the exit distances (percent of entry price).
- `risk_per_trade_pct` — how much account equity to risk per trade (drives size).
- `wpr_length`, `ema_length`, `rsi_length`, `bb_length`, `bb_mult` — indicator periods.
- `buy_rsi_threshold`, `buy_wpr_threshold`, etc. — signal filters.

Save, re-run the backtest command, and compare the numbers. The strategy code never
changes — only these values.

---

## 6. Sweep many parameter combinations

Instead of changing one value at a time, the sweep tests a whole grid automatically.
Edit the `PARAM_GRID` in
[config/backtest/sweep_rsi_wpr_bb_xauusd.py](../config/backtest/sweep_rsi_wpr_bb_xauusd.py)
(the grid size is the product of the list lengths), then:

```bash
uv run python -m qplus.backtest.sweep config/backtest/sweep_rsi_wpr_bb_xauusd.py
```

It prints progress, then a **Top 10 ranking**, and writes the full results table to
`reports/sweep_rsi_wpr_bb_xauusd.csv` (open it in Excel or any viewer). The run is
resumable: results are written after every combination.

---

## 7. Monte-Carlo robustness chart

For a chosen recipe, this bootstraps the trade sequence many times to show how much
the result depends on luck, and saves the "many lines" fan chart:

```bash
uv run python -m qplus.backtest.report config/backtest/rsi_wpr_bb_xauusd.py
```

It prints a summary (probability of profit, drawdown percentiles) and saves
`reports/montecarlo_rsi_wpr_bb_xauusd.png`. Open that PNG to see:

- **grey lines** — many simulated equity paths (resampled trades),
- **blue** — the median and 5th/95th-percentile band,
- **black** — the actual equity curve.

The key figures to watch are the **max-drawdown** percentiles: a high return with a
huge drawdown is not tradeable.

---

## 8. Honest caveats

- Results so far are **in-sample**: the "best" parameters were chosen on this exact
  history of one instrument, which risks overfitting. They are not a forecast.
- The current best combination shows a large drawdown — promising as a mechanism,
  not yet a usable strategy.
- Sensible next steps: out-of-sample / walk-forward validation, lowering the risk
  per trade to tame drawdown, and testing more instruments.

---

## 9. Quality gates

Before committing, everything must be green:

```bash
uv run ruff check .   # lint
uv run mypy           # type-check (strict)
uv run pytest         # tests
```
