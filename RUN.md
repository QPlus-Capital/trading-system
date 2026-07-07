# RUN.md — Getting the project running from scratch

This is the bootstrap guide: from a fresh clone to a runnable setup. It is written so
that you can either follow it by hand, or hand it to Claude Code and have it perform
the steps for you.

**Platform:** live/paper trading runs on **Windows** (MetaTrader 5 is Windows-only). The
backtest also runs on macOS (Apple Silicon) / Linux, wherever `nautilus_trader` wheels exist.

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

## 4. NautilusTrader & MetaTrader5

Both `nautilus_trader` (backtest engine) and `MetaTrader5` (live bridge) are pinned in
`pyproject.toml` / `uv.lock`, so the `uv sync` above already installed them — no extra
step. To bump a version later, run `uv lock --upgrade-package <name> && uv sync` and
commit the updated `uv.lock`.

## 5. Configure secrets (optional)

```bash
cp .env.example .env
```

The live MT5 bridge needs **no** broker credentials in code — it attaches to an
already-logged-in MetaTrader 5 terminal. `.env` is only for the optional Telegram
notification token. It is gitignored and must never be committed; store any real
credentials in the shared password manager.

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
| Single backtest     | `uv run python -m qplus.backtest.config config/backtest/rsi_wpr_bb_xauusd.py` |
| Robustness study (Stage 1) | `uv run python -m qplus.backtest.edge.characterize config/study/overnight.py` |
| Selection + validation (Stage 2–5) | `uv run python -m qplus.backtest.pipeline config/study/overnight.py <study.csv>` |
| Equity report / charts | `uv run python -m qplus.backtest.portfolio.equity_report` |
| Live / paper trading | `uv run python -m qplus.live.run` (add `--mode execute` for real orders) |

## The workflow

The methodology (the staged funnel from raw edge to a tradeable, prop-firm-compliant
config) is documented in **[docs/backtesting-framework.md](docs/backtesting-framework.md)**;
the live/paper wiring is in **[docs/mt5-bridge-plan.md](docs/mt5-bridge-plan.md)**. In short:

- **Data** lives in a Parquet catalog under `catalog/` (gitignored), imported from the
  MetaTrader 5 CSVs in `data/` (also gitignored); the backtest seeds it on first use.
- **The strategy code** lives once in `src/qplus/strategies/` — the same pure signal
  engine drives both the backtest and the live MT5 runner, so **live == backtest**.
- **Configs** under `config/` are where you turn the knobs: `study/` for the research
  sweep, `live/` for the frozen tradeable config.
