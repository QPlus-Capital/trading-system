# QPlus Capital – Trading System

A quantitative **trading-system framework** for QPlus Capital. It takes a strategy from
idea to deployment along three loosely-coupled stages:

1. **Research** — backtest and validate a strategy on historical data (built on
   [NautilusTrader](https://nautilustrader.io/)), ending in a defensible, risk-sized,
   prop-firm-compliant configuration.
2. **Live** — run that frozen configuration against a broker, one bar at a time, under
   hard risk limits.
3. **Monitoring** — compare live results back against what the backtest predicted.

The framework is deliberately **neutral**: nothing in the core assumes a particular
strategy, instrument, timeframe, or broker. A strategy is one plug-in class; the
venue, timeframe, and cost model are configuration. New strategies and venues are
added alongside the existing ones, never by changing the framework.

> **Current instance:** one mean-reversion strategy on a basket of CFDs (FX, indices,
> metals), executed through MetaTrader 5 on a prop-firm account. This is just the first
> deployment — see `live/config/` for what is actually live.

## Structure — the three worlds + a shared core

```
core/         # shared, strategy-/venue-neutral: strategies, instruments, broker costs, data
research/     # WORLD 1 — the backtesting framework (engine · portfolio · stages · config)
live/         # WORLD 2 — the live runner, broker bridge, risk control (+ its config)
monitoring/   # WORLD 3 — the live-vs-backtest dashboard

tests/        # the guards
docs/         # about the trading system: architecture, methodology, runbook, strategies
workflow/     # about how we build it: the contract, its tooling, its policies
```

Full map with diagrams: **[docs/architecture.md](docs/architecture.md)**.

## Commands

All day-to-day commands live in the **[`justfile`](justfile)** — type `just` to see them:

```
just                 # the full list — the justfile is the authority
just backtest        # run the research pipeline  -> reports/research/run_*/
just report          # open the latest backtest report
just live-ttp        # start the live runner, signal-only (no orders)
just live-ttp-execute  # start the live runner with REAL orders
just monitor         # the monitoring dashboard
just check           # ruff + mypy + vulture + pytest (before every commit)
```

Getting from a fresh clone to a runnable setup: **[RUN.md](RUN.md)**. The shared engineering rules
are the **[development workflow](workflow/workflow.md)**; **[AGENTS.md](AGENTS.md)** is
Codex's builder contract and **[CLAUDE.md](CLAUDE.md)** is Claude's specification and review
contract.

## Tech stack

| Component | Role |
| --------- | ---- |
| **Python 3.13** | Implementation language |
| **uv** | Package & environment management |
| **NautilusTrader** | Event-driven backtesting engine |
| **just** | Command runner (the discoverable command hub) |
| **ruff / mypy / pytest** | Lint & format, type-checking, tests |

Live execution currently runs through **MetaTrader 5** (the interim prop-firm venue);
the execution layer is an adapter and will change as new venues are added.

## Research vs. live: one strategy, two configs

A strategy is **one class** in `core/strategies/`. The *same* class runs under a
research config or a live config — strategy logic is never duplicated. A strategy
only goes live by adding its configuration under `live/config/` once it has been
backtested and approved, so it is always unambiguous which strategies are live.

## Git workflow

Two-person team, lightweight by design:

- Every change reaches `main` through a feature branch and pull request.
- [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `chore:`, `docs:`, `refactor:`, `test:` …).
- **Codex builds, Claude specifies and reviews**, and neither does the other's job. The
  operator decides every business, trading, methodology, live-money, architecture, and risk
  question, and approves every merge. No agent merges.

The full procedure is **[workflow/workflow.md](workflow/workflow.md)**.

## Principle: code in, data and secrets out

- **Code** is versioned (`core/`, `research/`, `live/`, `monitoring/`, `tests/`).
- **Market data** lives in `data/` and the catalog — **never** committed (gitignored).
- **Secrets** live in `.env` (template: `.env.example`) and are **never** committed;
  real credentials additionally go in the shared password manager.
