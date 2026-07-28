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
artifact, and opens the **draft** pull request the independent review runs on. Mark it ready for
review only once that review is clean. Do not merge.

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

Jan starts you with nothing but an issue number: `implement #101`. Everything you need is in the
issue body, the labels, and this file. The full procedure is
[docs/engineering/workflow.md](docs/engineering/workflow.md).

Every non-trivial change carries a risk class R0–R3, defined in
[docs/engineering/risk-classes.md](docs/engineering/risk-classes.md). The class sets its cumulative
mandatory gates, which task artifacts exist as files, how many PR sections are required, and which
review subagents run.

**0. Check the permit — before anything else.** Two disjoint guards, because the first start
consumes the permit and resuming therefore cannot demand it.

- **Starting new work.** Refuse unless the board card is in `Ready to Implement`, the label
  `approved` is present, and a `risk:Rn` label is present. Then move the card to `Implementing` and
  **only afterwards** remove `approved` — the reverse order would destroy the permit if the status
  update failed.
- **Resuming.** Resume **without** a permit when the card is in `Implementing` or `Reviewing` **and**
  a branch exists in this repository whose name is `codex/<issue>-…` or `claude/<issue>-…` for this
  issue number. That is the normal state after an interruption or after a review sent the change
  back, and demanding the already-consumed permit there would lock you out of your own branch.

Any other combination is a refusal: report the actual status and stop. A card in `Backlog`,
`Specifying` or `Blocked` is never built, with or without a branch. A branch whose name does not
carry this issue number is never resumed, and neither is a branch from a fork or from outside this
repository — ownership is decided by the branch name and its origin, not by the card, because the
card cannot tell you who wrote the code.

1. **Specify** — the specification is the issue body; Claude wrote it and Jan approved it. Do not
   restate it in a file and do not extend it. If it is wrong, incomplete, or unbuildable, do not
   guess: move the card back, state the concrete gap in an issue comment, and stop.
2. **Analyse impact** — trace files, callers, configuration routes, lifecycle, artifacts, and tests
   before implementation. Enumerate every consumer of a coupled quantity in one pass.
3. **Design tests, then implement** — map every `AC-nn` and `INV-nn` to exactly one named test, add
   the red-first behavioural guard, record its failure, implement the smallest bounded change, and
   keep `just check` green. Clean up nothing on the side; the non-goals bound the diff.
4. **Prepare independent review** — complete current evidence and hand the final diff to Claude's
   fresh reviewer path; resolve every blocking finding with executable proof. You fix every finding,
   including trivial ones, so the reviewer never reviews its own code.
5. **Open a draft PR** — with `Closes #<issue>` in the body, once implementation and deterministic
   verification are complete. Then move the card to `Reviewing`. The draft is what the independent
   review is performed on, so findings land inline at the lines they concern.
6. **Mark it ready for review** — only after the review is clean and the readiness check passes for
   current HEAD. Do not merge or enable autonomous merge.

Work in **one git worktree per issue** on branch `codex/<issue>-<slug>`, so the main checkout stays
clean and a running live runner never sees half-finished code.

**Do not mark a pull request ready for review until the readiness check for the change's risk class
passes.** A draft carries the review; only a ready pull request asks for a merge. R3
changes never merge autonomously. Only a **trivial R0** change may go straight to `main`; every R1+
change uses a feature branch and pull request. Valid out-of-scope work becomes a separate issue —
evidenced only, never speculative, and you return to the task at hand immediately.

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
