# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository. This file
is the **single source of project context** — it must be self-contained, so that any
machine or account running Claude Code produces the same high-quality results without
relying on prior chat history.

## Project

QPlus Capital's quantitative trading-system framework, built on
[NautilusTrader](https://nautilustrader.io/). A strategy flows through three worlds:
**research** (backtest & validate) → **live** (execute the frozen config) →
**monitoring** (live vs. backtest). The framework is strategy-, venue-, and
timeframe-neutral; the current instance is one detail of configuration, not a constraint.

- **Structure:** four flat packages — `core/` (shared: strategies, instruments, broker,
  data), `research/`, `live/`, `monitoring/`. No `src/` nesting.
- **Stack:** Python 3.13, `uv` for packaging, NautilusTrader (backtest engine), `just`
  as the command hub. Tooling: `ruff`, `mypy`, `pytest`.
- **Orientation:** read [docs/architecture.md](docs/architecture.md) first — diagrams of
  the research pipeline, live path and monitoring, plus a one-line-per-file module map.

## Conventions (always follow)

- **Language:** Everything in the repository — code, identifiers, comments, docs,
  commit messages — is in **English**. (Conversation with the user may be in German;
  the repo is not.)
- **Tests:** Write tests automatically wherever they add value, without being asked.
  Use `pytest`; tests live in `tests/`.
- **Types & lint:** Keep code passing `ruff` and `mypy` (strict). Run them before
  considering a change done.
- **Money & prices:** Never use `float` for prices, quantities, or money — use
  `Decimal` (or NautilusTrader's `Price`/`Quantity`/`Money` types). Floating-point
  rounding is unacceptable in a trading system.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`,
  `test:`). Do **not** add Claude as a co-author.
- **Commit & push when done:** When a unit of work is complete (a feature, a fix, a
  new or updated strategy, etc.), commit it and **push to the remote immediately** —
  do not leave finished work unpushed and do not wait to be asked. Jan does not push
  manually. Only push work that is actually finished and green (`ruff`, `mypy`,
  `pytest` all pass); never push broken or half-done code.
- **Git workflow:** Lightweight — feature branches + PRs are the norm, but direct
  pushes to `main` are fine. `main` is not branch-protected; no mandatory reviews.

## Backtest vs. live

A strategy is **one class** in `core/strategies/`, run with either a backtest or
a live config. Never duplicate strategy logic across backtest and live. Promotion to
live = adding the strategy's config under `live/config/` after it is backtested and
approved. Always keep it unambiguous which strategies are live.

## Secrets

- Secrets go in `.env` (gitignored); `.env.example` holds placeholders only.
- **Never** commit real credentials, API keys, or account numbers.
- **Whenever you introduce or generate new credentials, remind the user to store them
  in the shared password manager** so both teammates can retrieve them later.

## Data

- Market data and the NautilusTrader Parquet catalog live in `data/` (gitignored).
  Backtest outputs go in `results/` or `reports/` (also gitignored).
- Code is versioned; data and secrets never are ("code in, data and secrets out").

## Environment notes

- Target platforms are **Apple Silicon macOS (arm64)** and **Linux**, where
  `nautilus_trader` wheels exist. Intel macOS (x86_64) has no wheel and is
  unsupported; do not add Intel-macOS / Docker workarounds.
- `nautilus_trader` is **pinned in `pyproject.toml` and `uv.lock`** (added 2026-07-01,
  currently v1.230.0), so `uv sync` installs it automatically — no separate setup
  step, and it is safe to import and run NautilusTrader in code.
- Always use `uv` (`uv sync`, `uv add`, `uv run …`), never bare `pip`.

## Reproducibility

This repo must run identically on any machine/account: keep `uv.lock` committed and
current, keep `CLAUDE.md` and `RUN.md` accurate and self-contained, and never rely on
context that exists only in a chat session.
