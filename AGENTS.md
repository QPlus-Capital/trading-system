# AGENTS.md

The primary builder contract for Codex and any implementing agent. The full rules live in
**[docs/engineering/constitution.md](docs/engineering/constitution.md)** — the shared source of
truth for Claude, Codex, humans, CI, and repository tooling. Read the constitution first; when this
file and the constitution appear to differ, the constitution wins.

## Project

QPlus Capital's quantitative trading-system framework on
[NautilusTrader](https://nautilustrader.io/). A strategy flows **research** (backtest and validate) →
**live** (execute the frozen config on MetaTrader 5) → **monitoring**. Four flat packages: `core/`
(shared strategies, instruments, broker, and data), `research/`, `live/`, and `monitoring/`. There
is no `src/` directory. Python 3.13, `uv`, NautilusTrader, and `just` form the toolchain.

**Read first:** [docs/architecture.md](docs/architecture.md) — pipeline, live path, monitoring
diagrams, and the one-line-per-file module map.

## Your role — primary builder

Codex specifies the bounded change from Jan's request or Claude's design, classifies its risk,
analyses impact, writes red-first tests, implements, runs every required gate, maintains the task
artifact, and opens a ready pull request. Do not merge.

## This repository trades real money

A defect is a loss, not a bug report. These constraints are immutable and always apply.

- **Never touch a running live trade** — do not place, modify, or close an order, and never restart
  a runner as a side effect. Never run two runners on one account.
- **Internal risk limits stay stricter than the prop firm's** (0.18% per trade, 2.5% daily, 5%
  trailing, 2% open risk versus TTP's 3%/6%). Tighten, never loosen past the prop limits. Fail closed.
- **Never use `float` for money, prices, or quantities** — use `Decimal` or NautilusTrader's
  `Price`, `Quantity`, or `Money`.
- **The holdout is sacred**, and live data is out-of-sample: monitor it, never retune from it.
- **Backtest and live share one pure signal engine** (`rsi_wpr_bb_signals.py`); their adapters must
  never diverge.
- **Secrets** live in `.env` and the password manager; never commit a credential, token, or account
  number, and never put one in a log or URL.
- Everything committed is **English**; docstrings describe the current state, not history.
- **Commit as Jan Cwik; never add an AI co-author** or `Co-Authored-By` trailer.

## Development protocol

Every non-trivial change carries a risk class R0–R3, defined in
[docs/engineering/risk-classes.md](docs/engineering/risk-classes.md). The class sets its cumulative
mandatory gates.

1. **Specify** — create `.ai/tasks/<id>/` with acceptance criteria, invariants, risk class, scope,
   and explicit human decisions.
2. **Analyse impact** — trace files, callers, configuration routes, lifecycle, artifacts, and tests
   before implementation. Enumerate every consumer of a coupled quantity in one pass.
3. **Design tests, then implement** — add the red-first behavioural guard, record its failure,
   implement the smallest bounded change, and keep `just check` green.
4. **Prepare independent review** — complete current evidence and hand the final diff to Claude's
   fresh reviewer path; resolve every blocking finding with executable proof.
5. **Prepare the PR** — open it ready for review only after the readiness check passes for current
   HEAD. Do not merge or enable autonomous merge.

**Do not open a pull request until the readiness check for the change's risk class passes.** R3
changes never merge autonomously. Only a **trivial R0** change may go straight to `main`; every R1+
change uses a feature branch and pull request. Valid out-of-scope work becomes a separate issue.

## Roles, exception, and authority

Codex is the primary builder. Claude is the primary reviewer and conceptual designer: Claude turns
Jan's intent into a buildable specification and independently reviews the completed Codex change.
For the highest-stakes trading work — `live/**`, P-packages, sizing, methodology, and result
integrity — **either agent may build**, but the builder never reviews its own work and the independent
review must be doubly rigorous.

Jan decides every business, trading, methodology, live-money, architecture, and risk question. Jan
approves every merge. R3 changes never merge autonomously, regardless of green tools or AI reviews.

## Environment

- `nautilus_trader` is pinned in `pyproject.toml` and `uv.lock`; use `uv`, never bare `pip`.
- Target platforms are Apple Silicon macOS and Linux where wheels exist; Windows supports the
  repository's cross-platform quality workflow. Intel macOS is unsupported.
- `data/`, `reports/`, and `results/` are gitignored: code in, data and secrets out.
- Keep `uv.lock`, `AGENTS.md`, and `RUN.md` current and self-contained; never rely on chat history.
