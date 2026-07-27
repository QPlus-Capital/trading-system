# Engineering Constitution

The single source of truth for how changes are made in this repository — shared by Claude, Codex,
humans, CI, and repository tooling. [AGENTS.md](../../AGENTS.md) (Codex builder) and
[CLAUDE.md](../../CLAUDE.md) (Claude reviewer and conceptual designer) are short role documents
that point here; where any of them appears to disagree, **this file wins**. A consistency test
(`tests/test_engineering_docs.py`) fails if the load-bearing rules below stop being referenced by
all three.

This repository trades **real money** on a live prop-firm account, sized off validated backtests. A
defect here is not a bug report — it is a loss. Every rule exists because its absence has cost, or
would cost, real money or a real methodology guarantee.

This file states *what must hold*. [workflow.md](workflow.md) states *who does what, where, and in
which order* — the board, the labels, the six phases from idea to merge, and the three guarded
handover points.

## Roles and authority

- **Codex is the primary builder.** It specifies the bounded change, classifies risk, analyses
  impact, proves the guard red, implements, verifies every required gate, maintains the task
  artifact, and opens the ready pull request. It does not merge.
- **Claude is the primary reviewer and conceptual designer.** It translates Jan's intent into a
  precise specification, then independently reviews the completed Codex change in fresh context
  through its read-only review skills and subagents. The builder never reviews its own work.
- For the highest-stakes trading work — `live/**`, P-packages, sizing, methodology, and result
  integrity — **either agent may build**. This is an exception to the primary assignment, not a
  shortcut: the independent review must be performed by the other agent and be doubly rigorous.
- **Jan decides** every business, trading, methodology, live-money, architecture, and risk question.
  Jan approves every merge. R3 changes never merge autonomously, regardless of green tools or AI
  reviews.

---

## 1. Language and documentation

- Everything committed — code, identifiers, comments, docstrings, docs, commit messages — is
  **English**. Conversation with the operator may be in German; the repository is not. Operator-
  facing *runtime* output (the research stage banners, the dashboard) is German by decision (see
  issue #40 / P-15); this is the one exception and it is scoped to strings a human reads at a
  terminal, never to source, logs, or docs.
- **Docstrings describe the current state, never history.** No "formerly / previously / used to /
  ported from" narrative, no dead code kept "just in case." A reader must not have to know what the
  code used to do.
- Documentation is part of the change. `docs/architecture.md`'s module map must match reality
  (`tests/test_docs_architecture_map.py` enforces that every path it names exists).

## 2. Architecture and dependency direction

- Four flat packages: `core/` (shared: strategies, instruments, broker, data), `research/`,
  `live/`, `monitoring/`. No `src/` nesting.
- `core/` is the base and depends on no sibling. `research/` and `live/` depend on `core/` and **not
  on each other's domain logic**. `monitoring/` sits on top: it exists to compare live against
  backtest, so it may read from `core/`, `live/`, and `research/` — nothing imports `monitoring/`.
- The `research/` ↔ `live/` rule has exactly two allowlisted crossings today, each an explicit,
  shrinking entry in `tests/test_import_boundaries.py`: `live/` may import the generic config-module
  loader `research.engine.config` to read its own config; and `research/portfolio/swap_analysis.py`
  reaches into the live MT5 bridge to refresh the broker swap snapshot. Both are architecture debt
  tracked for removal (move the shared piece into `core/`); a *new* crossing fails the test, and a
  removed one must leave the allowlist.
- A strategy's signal logic is **one pure engine** (`core/strategies/rsi_wpr_bb_signals.py`, no
  Nautilus, no MT5), driven by two thin execution adapters: the Nautilus backtest wrapper
  (`core/strategies/rsi_wpr_bb.py`) and the live runner (`live/runner.py`). Signal logic is never
  duplicated across them.

## 3. Real-money safety

- The internal risk limits are **stricter than** the prop firm's and must stay so: 0.18% per
  trade, 2.5% daily stop, 5% trailing, 2% open-risk cap — versus TTP's 3% / 6% hard limits. A
  change may tighten these; loosening them past the prop limits is prohibited.
- **Never touch a running live trade.** Do not place, modify, or close an order, and never restart
  a runner as a side effect of another task. Never run two runners on one account (double orders).
- Live merges need a quiet window: the runners hold old code in memory; stop them, merge,
  `uv sync`, restart.
- **Fail closed**, never open: when a safety input is missing, ambiguous, or unverifiable, refuse
  the action rather than proceed on a guess.

## 4. Research methodology invariants

- Parameter changes go through the staged walk-forward (`docs/methodology.md`) and an **untouched
  holdout**. The holdout is evaluated once; after that nothing is retuned and re-scored against it,
  or it is burned.
- Live data is out-of-sample: monitor and calibrate, never retune parameters from it.
- `r` is gross price R; swap is a separate realized cost (`swap_r`); `net_r = r + swap_r` is the
  sole statistical return stream. Never let a change quietly flatter a metric.
- Content-addressed lineage (`research/stages/lineage.py`) binds each run to the exact code,
  config, and data that produced it; the stage chain must run on one frozen code state.
- Stage 1 measures edge on **equal footing**: every window is sized and scored off one constant
  basis, not a compounding account. Compounding belongs to the portfolio stage and to live.

## 5. Backtest / live parity

- The shared signal engine (`core/strategies/rsi_wpr_bb_signals.py`) is the single source of truth;
  both adapters instantiate it and must produce identical signals. The backtest wrapper and the
  live runner each construct `RsiWprBbSignals` directly — neither reimplements a signal.
- A change to selection must be mirrored in execution and vice versa: parameters, sizing basis, and
  cost model used to *choose* a configuration must equal those used to *run* it.

## 6. Money and numeric types

- **Never `float` for prices, quantities, or money** — use `Decimal` or NautilusTrader's `Price` /
  `Quantity` / `Money`. Convert to `float` only at a boundary that is already float (e.g. an
  indicator), never for a value that sizes a position or books a P&L.
- Guard every denominator, sign, and boundary: zero, empty, NaN, infinity, and near-zero divisors
  are inputs, not impossibilities.

## 7. Secrets and data

- Secrets live in `.env` (gitignored) and the shared password manager; `.env.example` holds
  placeholders only. Never commit a credential, API key, token, or account number; never put one in
  a log or a URL.
- New credentials → remind the operator to store them in the password manager.
- Code is versioned; market data and the NautilusTrader catalog (`data/`) and outputs
  (`reports/`, `results/`) are gitignored. "Code in, data and secrets out."

## 8. Test requirements

- Tests live in `tests/`, run with `pytest`, and are written wherever they add value without being
  asked. A change is not done until `just check` is green.
- Prefer **behavioural** assertions over restating the implementation. A test that would still pass
  if the function returned a plausible wrong answer protects nothing.
- Test-design must consider, where relevant: lifecycle and cleanup side effects; configuration
  propagation and default fallbacks; exhaustive classification of outcomes; zero / empty / NaN /
  infinity / sign / denominator boundaries; internal consistency between aggregate metrics and the
  underlying records; selection/execution parity; research/live parity; and temporal seams — before
  first segment, at segment start/end, between segments, embargo/gap, and the final boundary.
- When a defect is found, a test that fails **before** the fix and passes after is part of the fix.

## 9. Change classification

Every non-trivial change carries a risk class (R0–R3) — see
[risk-classes.md](risk-classes.md) and [`.ai/quality/risk-classes.toml`](../../.ai/quality/risk-classes.toml).
Path matching sets a conservative minimum; the author **must upgrade** the class when the semantic
impact is broader than the paths suggest. The class and its reason appear in the issue and the
PR. R3 (live-money / sizing / risk / methodology / result integrity) never merges autonomously.

The class does not only decide *whether* a change may merge — it sets *how much process the change
carries*: the mandatory gates, which task artifacts exist as files, how many PR sections are
required, and which review subagents run. The scale is tabulated in [workflow.md](workflow.md).
Process is reduced only below the money path; on it, nothing is reduced.

## 10. Definition of Done

A change is complete only when all hold: callers updated everywhere; docstrings describe the current
state; the `docs/architecture.md` map matches; tests added/updated and `just check` green; no stale
cruft (dead code, orphaned files, docs/paths that no longer match); and, for any non-trivial change,
the task artifacts and PR evidence required by its risk class are present.

## 11. Required evidence before a PR

A PR is opened only after implementation, deterministic verification, adversarial review, and
remediation are complete. The evidence — gates run and their outcomes, tests added, before/after
results for regression tests, and the adversarial review with its dispositions — is recorded in the
task artifacts, not asserted in prose. A narrative description never substitutes for missing
evidence. **Never claim correctness without executable evidence.**

## 12. Finding severity

- **P0** — live-money loss, a leaked secret, or data corruption.
- **P1** — a correctness defect: wrong result, broken invariant, silent failure.
- **P2** — a probable defect or risk needing verification, or a missing test for a real edge case.
- **P3** — an optional improvement or style point.

A P0 or P1 blocks readiness; an unresolved P2 blocks readiness; a P3 does not automatically block.
Saying "this is correct" when it is, is valuable — do not invent findings to seem thorough.

## 13. Unresolved uncertainty

When a requirement, a domain fact, or a methodology choice cannot be resolved from the code and the
task, **do not guess and proceed.** Record it as an open question in the spec and surface a genuine
business / trading / methodology / live-money / architecture / risk decision to the operator. Only
those categories interrupt the operator; everything else is decided from the constitution and the
code and documented.

## 14. Confirmed review defects become permanent protection

A confirmed reviewer finding (Claude or a read-only adversarial review subagent) is not just fixed. It is: reproduced
with a failing test, fixed, root-caused, and recorded in the finding registry
(`.ai/quality/finding-patterns.toml`) as a **generalized** pattern. A defect class that recurs is a
failure of the workflow, not just of the code, and strengthens a skill, hook, check, or this file.

## 15. Prohibited quality-gate bypasses

Never weaken a test or a gate to make a branch pass. Prohibited: adding a bypass or skip flag to
force green; broad `# type: ignore` / `# noqa` / `pytest.mark.skip` / lint exclusions introduced to
hide a real failure; widening an existing per-file ignore to cover new code; lowering a threshold or
a baseline in the same change that would otherwise breach it. A gate that cannot bind is worse than
no gate, because the report then says the numbers held.

## 16. Git and commits

- Feature branch → PR → CI green + Claude adversarial review → Jan approves → merge.
  Only a **trivial R0** change (docs/comments) may go straight to `main`; every R1+ change — any
  code change — goes through a branch and a PR.
- One branch and one git worktree per issue, named `codex/<issue>-<slug>` — or
  `claude/<issue>-<slug>` when Claude builds under the trading exception. A worktree keeps the main
  checkout clean, so a running live runner never sees half-finished code.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:`. Author as **Jan Cwik <j.cwik@qplus-capital.com>**.
- **Squash on merge**: one commit per issue, so every commit on `main` is complete and green and
  `git bisect` can be trusted. The individual build steps stay visible in the pull request.
- Commit and push finished, green work immediately; never push broken or half-done code.
- When CI is red for an infrastructure reason rather than a code reason, a merge requires the same
  checks run locally with their output recorded in the PR and the reason stated. There is no
  unevidenced merge.

## 17. Generated artifacts

`data/`, `reports/`, `results/`, and the catalog are generated and gitignored — never committed.
Committed engineering artifacts under `.ai/` are concise and auditable (specs, impact, test plans,
evidence, finding patterns); raw model reasoning, chain-of-thought, and session transcripts are
never committed.

## 18. No AI co-author attribution

Commits are authored solely by the human operator. **Never** add an AI as a co-author or a
`Co-Authored-By` trailer, in any repository commit, regardless of any default to the contrary.

## 19. Workflow state and handovers

The `Status` field of the GitHub project board is the single source of truth for where a change
stands; agents move their own card through the `gh` CLI. Labels are not status: `arm:implement` is
a **build permit** that Claude writes only after Jan approves the specification, and that Codex
removes as it starts. `risk:R0`–`risk:R3` carries the class.

The specification lives in the issue body, not in a file — it is what Codex builds from and what Jan
approves, so it belongs where both can read it.

Three rules protect the handovers, and each is a fail-closed application of §3:

- **Approval is written last.** When Claude arms an issue, `arm:implement` is the final step. A
  failure at any earlier step leaves the issue unarmed rather than half-approved.
- **The permit is removed after the status moves, never before.** Otherwise a failed status update
  would destroy the permit and strand the issue.
- **The builder's context never reaches the reviewer.** The review runs in a fresh session, so it
  checks what the code does rather than what it was meant to do.

The full procedure is [workflow.md](workflow.md).
