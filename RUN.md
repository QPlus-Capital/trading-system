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

## 5. Configure live account identity and secrets

```bash
cp .env.example .env
```

The live MT5 bridge needs no broker password in code: it attaches to an already-logged-in terminal.
Fill all four required `MT5_*_LOGIN` / `MT5_*_TERMINAL_PATH` placeholders in `.env`; the account
guard refuses missing, malformed, or mismatching identity. Telegram values remain optional. `.env`
is gitignored and must never be committed; store every real account value in the shared password
manager. The live-facing `just` recipes load this file explicitly through `uv run --env-file .env`.

On Windows, keep each `.env` value in **single quotes**, especially terminal paths containing
backslashes, for example `MT5_TTP_TERMINAL_PATH='C:\MT5\TTP\terminal64.exe'`. An unquoted or
double-quoted backslash path can make `uv` warn while returning success and discard that line and
everything after it; forward slashes are also safe.

An already-exported PowerShell variable takes precedence over the same key in `.env`;
`uv run --env-file` does not override it. Before starting a live-facing command, use a fresh shell or
inspect and clear stale `MT5_*` and `TELEGRAM_*` variables. Otherwise the runner may use old
identity/path values while the optional remote alert configuration from `.env` is not loaded.

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

**All day-to-day commands live in the [`justfile`](justfile).** Type `just` to see the
full list. (One-time: install `just` — `winget install --id Casey.Just`.)

| Task | Command |
| ---- | ------- |
| List all commands | `just` |
| Run the backtest pipeline | `just backtest` → `reports/research/run_*/` (open with `just report`) |
| Live — real TTP account | `just live-ttp-execute` |
| Live — demo account | `just live-demo` |
| Pre-flight before going live | `just preflight` (TTP) |
| Monitoring dashboard | `just monitor` |
| Quality gates (before every commit) | `just check` (ruff + mypy + vulture + pytest) |

Under the hood these are plain `uv run python -m <world>.<module>` calls — the
`justfile` is just the discoverable front door. The three worlds are `research`,
`live`, `monitoring`; shared code is in `core`.

| Raw tooling | Command |
| ----------- | ------- |
| Install / update | `uv sync` |
| Add a dependency | `uv add <package>` |
| Lint / format / type-check / test | `uv run ruff check .` · `uv run ruff format .` · `uv run mypy` · `uv run pytest` |

## The workflow

The methodology (the staged funnel from raw edge to a tradeable, prop-firm-compliant
config) is documented in **[docs/methodology.md](docs/methodology.md)**; the live
operations guide is **[docs/live-runbook.md](docs/live-runbook.md)**. In short:

- **Data** lives in a Parquet catalog under `catalog/` (gitignored), imported from the
  MetaTrader 5 CSVs in `data/` (also gitignored); the backtest seeds it on first use.
- **The strategy code** lives once in `core/strategies/` — the same pure signal
  engine drives both the backtest and the live MT5 runner, so **live == backtest**.
- **Configs** are where you turn the knobs: `research/config/` for the research sweep,
  `live/config/` for the frozen tradeable config.

How a change travels from an idea to `main` — the board, the risk classes, the gates — is
**[workflow/workflow.md](workflow/workflow.md)**.
