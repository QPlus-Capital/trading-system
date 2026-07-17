# AGENTS.md

Instructions for AI agents (Codex and others) working in this repository. Codex reads this file
automatically. It is a peer to [CLAUDE.md](CLAUDE.md) — the two carry the same conventions.

## Project

QPlus Capital's quantitative trading-system framework, built on
[NautilusTrader](https://nautilustrader.io/). A strategy flows through three worlds: **research**
(backtest & validate) → **live** (execute the frozen config on MetaTrader 5) → **monitoring**. The
framework is strategy-, venue- and timeframe-neutral; the current instance is one configuration,
not a constraint.

**Orientation — read this first:** [docs/architecture.md](docs/architecture.md) — diagrams of the
pipeline / live path / monitoring, plus a one-line-per-file module map of the whole system.

**Structure:** four flat packages — `core/` (shared: strategies, instruments, broker, data),
`research/`, `live/`, `monitoring/`. No `src/` nesting. Day-to-day commands live in the `justfile`
(`just` lists them; `just check` runs the gates).

## Review guidelines

Your primary role here is **critical reviewer**. This repo trades **real money** — a live prop-firm
account, sized off validated backtests. On every pull request, and whenever asked directly, review
the change **critically** across:

- **Correctness / logic.** Does it do what it claims? Look for edge cases, off-by-one, sign errors,
  unit mix-ups (money vs R-multiples), and NaN / empty-input handling. Trace the data flow, don't
  skim.
- **The live money path — highest scrutiny.** Anything touching `live/risk_control.py`, the sizing
  in `live/runner.py`, the account identity `guard` (`live/accounts.py`), or backtest↔live parity
  (`core/strategies/rsi_wpr_bb_signals.py` is the shared source of truth). A bug here loses real
  money. The internal risk limits must stay **stricter than** the prop firm's — 0.18% per trade,
  2.5% daily stop, 5% trailing, 2% open-risk cap, versus TTP's 3% / 6% hard limits.
- **Security.** No credential / login / token / API key ever committed; secrets live in `.env` +
  the shared password manager. No secrets in logs or URLs.
- **Consistency (the anti-cruft check).** When code changes, did its **callers**, its
  **docstrings**, the **`docs/architecture.md` module map**, and the **tests** get updated too?
  Flag stale references, dead code, orphaned files, and docs that no longer match the code.
- **Methodology discipline.** No overfitting, no gold-plating; parameter changes go through the
  staged walk-forward + an untouched holdout (see [docs/methodology.md](docs/methodology.md)). Live
  data is out-of-sample — monitor & calibrate, never retune parameters from it.
- **Honesty of the numbers.** `r` is gross; swap is a separate realized cost (`swap_r`); the
  holdout is sacred. Don't let a change quietly flatter a metric.

Be specific and cite `file:line`. Rank findings by severity — treat anything on the live money
path, a correctness bug, or a leaked secret as **P0/P1**; stale docs/cruft and style as lower.
Saying "this looks correct" when it does is valuable — do not invent problems to seem thorough.

## Conventions (always follow)

- **Language:** everything in the repo — code, comments, docs, commit messages — is **English**.
  (Conversation with the user may be in German.)
- **Describe the current state, not history.** No "formerly / previously / used to / ported from"
  narrative in docstrings; no dead code kept "just in case".
- **Gates:** a change is not done until `just check` is green — `ruff` + `mypy` (strict) + `pytest`
  + `vulture`. CI enforces this on every PR.
- **Money & prices:** never `float` for prices, quantities, or money — use `Decimal` or
  NautilusTrader's `Price` / `Quantity` / `Money`.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `refactor:`, `docs:`, `test:`, `chore:`). Author commits as
  **Jan Cwik <j.cwik@qplus-capital.com>**; never add an AI as co-author.
- **Never touch running live trades.** The live runners trade a real account; do not place, modify,
  or close trades, and never restart a runner as a side effect of another task.
- **Secrets** stay in `.env` (gitignored) + the password manager; never commit real credentials or
  account numbers.

## Definition of Done (the anti-drift checklist)

A change is complete only when ALL of these hold — this is how we avoid ever needing a big cleanup
again:

1. **Callers updated** everywhere (no broken or dangling references).
2. **Docstrings** describe the new current state (no leftover history).
3. **`docs/architecture.md`** module map + diagrams match reality — a deleted, renamed, or added
   file is reflected there (`tests/test_docs_architecture_map.py` enforces that every path named in
   the map exists).
4. **Tests** updated/added, and **`just check` is green** (ruff + mypy + pytest + vulture).
5. **No stale cruft** introduced — no dead code, orphaned files, or docs/paths that no longer match.
