# CLAUDE.md

Orientation and the immutable constraints for any AI agent building in this repository. The full
rules live in **[docs/engineering/constitution.md](docs/engineering/constitution.md)** — the shared
source of truth for Claude, Codex, humans, and CI. This file is the short version that must stay in
permanent context; when it and the constitution appear to differ, the constitution wins.

## Project

QPlus Capital's quantitative trading-system framework on
[NautilusTrader](https://nautilustrader.io/). A strategy flows **research** (backtest & validate) →
**live** (execute the frozen config on MetaTrader 5) → **monitoring**. Four flat packages: `core/`
(shared: strategies, instruments, broker, data), `research/`, `live/`, `monitoring/`. No `src/`.
Stack: Python 3.13, `uv`, NautilusTrader, `just` as the command hub.

**Read first:** [docs/architecture.md](docs/architecture.md) — pipeline / live path / monitoring
diagrams and a one-line-per-file module map.

## This repository trades real money

A defect is a loss, not a bug report. The constraints below are non-negotiable and always apply.

- **Never touch a running live trade** — do not place, modify, or close an order, and never restart
  a runner as a side effect. Never run two runners on one account.
- **Internal risk limits stay stricter than the prop firm's** (0.18%/trade, 2.5% daily, 5%
  trailing, 2% open-risk vs. TTP's 3%/6%). Tighten, never loosen past the prop limits. Fail closed.
- **Never `float` for money, prices, or quantities** — `Decimal` or NautilusTrader `Price`/
  `Quantity`/`Money`.
- **The holdout is sacred**, live data is out-of-sample — monitor, never retune from it.
- **Backtest and live share one pure signal engine** (`rsi_wpr_bb_signals.py`); the Nautilus
  backtest wrapper and the live runner are thin adapters over it — never diverge them.
- **Secrets** live in `.env` + the password manager; never commit a credential or account number.
- Everything committed is **English**; docstrings describe the current state, not history.
- **Commit as Jan Cwik; never add an AI co-author** or `Co-Authored-By` trailer.

## Development protocol

Every non-trivial change carries a **risk class R0–R3**
([docs/engineering/risk-classes.md](docs/engineering/risk-classes.md)) that sets its mandatory
gates. The loop:

1. **Specify** — a task spec with acceptance criteria and invariants under `.ai/tasks/<id>/`, and
   the risk class with its reason. Surface genuine business / trading / methodology / live-money /
   architecture / risk decisions to the operator; decide everything else from the constitution.
2. **Analyse impact** — the files, callers, config routes, lifecycle, artifacts, and tests a change
   touches, before writing it. For any coupled quantity (a sizing basis, a risk denominator, a
   cost), enumerate **every** entry point and change them in one pass.
3. **Design tests, then implement** — red tests before the fix where applicable; keep `just check`
   green throughout; keep scope to the spec.
4. **Adversarial review** — a fresh isolated review of the final diff before any PR (see the
   review subagents and skills under `.claude/`, added progressively).
5. **Prepare the PR** — only after the readiness check passes.

**Do not open a pull request until the readiness check for the change's risk class passes** and its
evidence is current for HEAD. R3 changes never merge autonomously — the operator approves.

Feature branch → PR → CI + Codex + adversarial review → operator approves → merge. Only a
**trivial R0** change (docs/comments) may go straight to `main`; every code change goes through a
branch and a PR. A valid issue outside a PR's scope → open a GitHub issue, don't widen the PR.

**Roles:** Claude builds, verifies, and drives the PR loop; the adversarial subagent and Codex
review independently; the operator decides judgment calls and approves merges.

## Environment

- `nautilus_trader` is pinned in `pyproject.toml` / `uv.lock`; `uv sync` installs everything. Always
  use `uv` (`uv sync`, `uv add`, `uv run …`), never bare `pip`.
- Target platforms: Apple Silicon macOS (arm64) and Linux, where wheels exist. Intel macOS is
  unsupported.
- `data/`, `reports/`, `results/` are gitignored: "code in, data and secrets out."
- This repo must run identically on any machine — keep `uv.lock`, `CLAUDE.md`, and `RUN.md` current
  and self-contained; never rely on chat-session context.
