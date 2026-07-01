# RUN.md — Getting the project running from scratch

This is the bootstrap guide: from a fresh clone to a runnable setup. It is written so
that you can either follow it by hand, or hand it to Claude Code and have it perform
the steps for you.

**Platform requirement:** Apple Silicon macOS (arm64) or Linux, where
`nautilus_trader` wheels exist. Intel macOS (x86_64) has no wheel and cannot run it.

## 1. Prerequisites

- **Python 3.13** (the version is pinned in `.python-version`).
- **uv** — the package/environment manager. Install it if you don't have it:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Verify: `uv --version`.

## 2. Clone and enter the repo

```bash
git clone https://github.com/QPlus-Capital/trading-system.git
cd trading-system
```

## 3. Install dependencies

```bash
uv sync
```

This creates `.venv/` and installs all locked dependencies (dev tooling + the local
`qplus` package in editable mode).

## 4. NautilusTrader

`nautilus_trader` is already pinned in `pyproject.toml` and `uv.lock` (added
2026-07-01, currently v1.230.0), so the `uv sync` above already installed it — no
extra step is needed.

It was originally added with a one-off `uv add nautilus_trader && uv sync` on a
machine that has a wheel (Apple Silicon or Linux). To bump the version later, run
`uv lock --upgrade-package nautilus-trader && uv sync` and commit the updated
`uv.lock`.

## 5. Configure secrets

```bash
cp .env.example .env
```

Fill in the real values in `.env` (IBKR credentials, etc.). `.env` is gitignored and
must never be committed. Also save these credentials in the shared password manager.

## 6. Verify the setup

```bash
uv run ruff check .      # lint
uv run mypy              # type-check
uv run pytest            # tests
```

All three should pass on a clean checkout. Once NautilusTrader is installed (step 4),
you can additionally verify the import:

```bash
uv run python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

## Everyday commands

| Task                | Command                       |
| ------------------- | ----------------------------- |
| Install / update    | `uv sync`                     |
| Add a dependency    | `uv add <package>`            |
| Add a dev dependency| `uv add --dev <package>`      |
| Run a script        | `uv run python <path>`        |
| Lint                | `uv run ruff check .`         |
| Format              | `uv run ruff format .`        |
| Type-check          | `uv run mypy`                 |
| Tests               | `uv run pytest`               |
| Run a backtest      | `uv run python -m qplus.backtest.runner config/backtest/rsi_wpr_bb_xauusd.py` |
| Parameter sweep     | `uv run python -m qplus.backtest.sweep config/backtest/sweep_rsi_wpr_bb_xauusd.py` |
| Monte-Carlo chart   | `uv run python -m qplus.backtest.report config/backtest/rsi_wpr_bb_xauusd.py` |

## Running the strategy

The full workflow (single backtest, parameter sweep, Monte-Carlo report) is
documented step by step in **[docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)**. In short,
everything uses NautilusTrader's high-level API (`BacktestNode`) with three cleanly
separated pieces:

- **Data** lives in a Parquet catalog under `catalog/` (gitignored). It is imported
  from the MetaTrader 5 CSV in `data/` (also gitignored); the runner imports it
  automatically on first use.
- **A run recipe** under `config/backtest/` composes the venue, the data (pointing
  at the catalog) and the strategy (class path + parameters) into one
  `BacktestRunConfig`. This is the file you edit to experiment.
- **The strategy code** lives once in `src/qplus/strategies/` and never changes
  between backtest and live.

```bash
uv run python -m qplus.backtest.runner config/backtest/rsi_wpr_bb_xauusd.py
```
