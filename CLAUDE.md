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
- **Gates:** a change is not done until **`just check`** is green — `ruff` + `mypy`
  (strict) + `pytest` + `vulture`. CI runs the same on every PR (see `.github/workflows/ci.yml`).
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
- **Git workflow:** feature branch → PR → CI green + Codex review → merge to `main`.
- **Definition of done (anti-drift):** a change is complete only when its callers,
  docstrings, the `docs/architecture.md` module map, and tests are all updated to match,
  `just check` is green, and no stale cruft (dead code, orphaned files, stale docs/paths)
  is left behind. `tests/test_docs_architecture_map.py` enforces that the map stays honest.
  See [AGENTS.md](AGENTS.md) for the full reviewer checklist (shared with Codex).

## Development workflow — the standard for larger changes

Bundle related work into a coherent theme, then run it through this loop (this is the default
for any feature/refactor of more than trivial size; small self-contained fixes may still go
straight to `main` when it clearly makes sense):

1. **Claude implements on a feature branch** — never commit a larger feature straight to `main`;
   keep `just check` green throughout.
2. **Claude opens the PR** (`gh pr create`) when the theme is done — proactively, without being asked.
3. **CI + Codex review run automatically** on the PR (CI = ruff / mypy / pytest / vulture;
   Codex = the independent reviewer, per [AGENTS.md](AGENTS.md)).
4. **Claude drives the review loop via `gh`** (`gh pr view --comments`, `gh api .../pulls/N/reviews`
   and `/comments`): read Codex's findings **directly** — never make Jan copy-paste them — then
   triage: fix the valid ones and push, dismiss the wrong ones with a one-line reason. Surface to
   Jan **only** genuine decision topics (a design / logic / methodology choice, or anything on the
   live money path where a *choice* — not just an obvious bug fix — is needed). A valid issue
   that is outside the theme's scope → open a GitHub issue rather than widen the PR.
5. **Merge** once CI is green, Codex's findings are resolved, and Jan approves.

**Roles:** Claude = builder/fixer **and** PR driver; Codex = independent reviewer (correctness,
methodology, security, the money path); Jan = decides the judgment calls and approves the merge,
otherwise stays out of the loop. Codex reads AGENTS.md on every review, so its role is
self-documented; Claude drives everything else.

**Live merges need a quiet window:** the running MT5 runners hold the old code in memory. Merge
+ `uv sync` + restart the runners only when they are **stopped** — and never start a second runner
on an account that already has one (double orders on real money).

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
