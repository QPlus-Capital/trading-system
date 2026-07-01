# QPlus Capital – Trading System

Quantitative trading system for **QPlus Capital**, built on
[NautilusTrader](https://nautilustrader.io/). It is used first for **backtesting**
strategies on historical data, then **paper trading**, and finally **live trading**.

Primary markets are **CFDs** via Interactive Brokers (FX, indices such as US30,
and commodities), starting with daily/swing timeframes and moving to intraday later.

> New here? Read **[RUN.md](RUN.md)** — it gets you from a fresh clone to a runnable
> setup. Working with Claude Code? See **[CLAUDE.md](CLAUDE.md)** for the project
> conventions every session must follow.

## Tech stack

| Component         | Role                                                   |
| ----------------- | ------------------------------------------------------ |
| **Python 3.13**   | Implementation language                                |
| **uv**            | Package & environment management                       |
| **NautilusTrader**| Event-driven engine for backtesting & live trading     |
| **IBKR**          | Interactive Brokers – broker and data source           |
| **ruff / mypy / pytest** | Linting & formatting, type checking, tests      |

## Repository layout

```
trading-system/
├── src/qplus/              # Python package (versioned source code)
│   ├── strategies/         # Strategy classes — single source of truth,
│   │                       #   shared by both backtest and live
│   ├── backtest/           # Backtest runners & wiring
│   ├── live/               # Live trading runners & wiring
│   └── data_ingest/        # Data acquisition & preparation (IBKR -> catalog)
├── config/
│   ├── backtest/           # Backtest configurations
│   └── live/               # Live configurations (only approved strategies)
├── tests/                  # Test suite (pytest)
├── data/                   # Market data / Parquet catalog (NEVER versioned)
├── .env.example            # Secrets template (committed, placeholders only)
├── pyproject.toml          # Project & dependency definition
└── uv.lock                 # Pinned dependencies (committed for reproducibility)
```

The structure is intentionally lean and will grow as NautilusTrader is integrated.

## Setup

Requires Apple Silicon (arm64) or Linux. Full step-by-step instructions are in
**[RUN.md](RUN.md)**. Short version:

```bash
uv sync                # install dependencies into .venv
uv add nautilus_trader && uv sync   # first time only (see RUN.md)
cp .env.example .env   # then fill in real values in .env
```

## Backtest vs. live

Strategy code lives once in `src/qplus/strategies/`. The same strategy class is run
with a **backtest config** or a **live config** — code is never duplicated between
the two. A strategy only moves to live by adding its configuration under
`config/live/` once it has been backtested and approved, so it is always clear which
strategies are live and which are not.

## Git workflow

Two-person team. Lightweight by design:

- Feature branches + pull requests are the norm; direct pushes to `main` are allowed
  when it makes sense.
- No mandatory reviews. `main` is not branch-protected.
- [Conventional Commits](https://www.conventionalcommits.org/) for commit messages
  (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:` …).

## Principle: code in, data and secrets out

- **Code** is versioned (everything under `src/qplus/`, `config/`, `tests/`).
- **Market data** belongs in `data/` (and `catalog/`) and is **never** committed —
  both are gitignored.
- **Secrets** belong in `.env` (template: `.env.example`) and are **never** committed.
  Real credentials are additionally stored in the shared password manager.
