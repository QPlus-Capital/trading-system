# Research configs

Configuration files for the research world. A strategy's code lives once in
`core/strategies/`; a file here only wires that strategy to parameters — never a
code change is needed to backtest it.

- **`robustness.py`** — the **study** config the staged framework runs on: the
  instruments, the parameter grid, the strategy variations, the account, and the
  walk-forward sizing (train/test/holdout months). This is the config that matters;
  the staged CLI (`research.stages`) reads it.
