# Engineering Constitution

The single source of truth for how changes are made in this repository — shared by Claude, Codex,
humans, CI, and repository tooling. [CLAUDE.md](../../CLAUDE.md) (builder) and
[AGENTS.md](../../AGENTS.md) (reviewer) are short role documents that point here; where any of them
appears to disagree, **this file wins**. A consistency test
(`tests/test_engineering_docs.py`) fails if the load-bearing rules below stop being referenced by
all three.

This repository trades **real money** on a live prop-firm account, sized off validated backtests. A
defect here is not a bug report — it is a loss. Every rule exists because its absence has cost, or
would cost, real money or a real methodology guarantee.

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
- Dependencies flow inward to `core/`. `research/`, `live/`, and `monitoring/` may depend on
  `core/`; `core/` depends on none of them; `research/` and `live/` do not import each other.
- A strategy is **one class** in `core/strategies/`, run by either a backtest or a live config.
  Strategy logic is never duplicated across backtest and live.

## 3. Real-money safety

- The internal risk limits are **stricter than** the prop firm's and must stay so: 0.18% per
  trade, 2.5% daily stop, 5% trailing, 2% open-risk cap — versus TTP's 3% / 6% hard limits. A
  change may tighten these; loosening them past the prop limits is prohibited.
- **Never touch a running live trade.** Do not place, modify, or close an order, and never restart
  a runner as a side effect of another task. Never run two runners on one account (double orders).
- Live merges need a quiet window: the runners hold old code in memory; stop them, merge,
  `uv sync`, restart.
- Fail **closed**, never open: when a safety input is missing, ambiguous, or unverifiable, refuse
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
  backtest and live drive the same code and must produce identical signals.
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
impact is broader than the paths suggest. The class and its reason appear in the task spec and the
PR. R3 (live-money / sizing / risk / methodology / result integrity) never merges autonomously.

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

A confirmed reviewer finding (Codex or the adversarial subagent) is not just fixed. It is: reproduced
with a failing test, fixed, root-caused, and recorded in the finding registry
(`.ai/quality/finding-patterns.yaml`) as a **generalized** pattern. A defect class that recurs is a
failure of the workflow, not just of the code, and strengthens a skill, hook, check, or this file.

## 15. Prohibited quality-gate bypasses

Never weaken a test or a gate to make a branch pass. Prohibited: adding a bypass or skip flag to
force green; broad `# type: ignore` / `# noqa` / `pytest.mark.skip` / lint exclusions introduced to
hide a real failure; widening an existing per-file ignore to cover new code; lowering a threshold or
a baseline in the same change that would otherwise breach it. A gate that cannot bind is worse than
no gate, because the report then says the numbers held.

## 16. Git and commits

- Feature branch → PR → CI green + adversarial review + Codex review → operator approves → merge.
  Never commit a non-trivial change straight to `main`.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`,
  `docs:`, `test:`, `chore:`. Author as **Jan Cwik <j.cwik@qplus-capital.com>**.
- Commit and push finished, green work immediately; never push broken or half-done code.

## 17. Generated artifacts

`data/`, `reports/`, `results/`, and the catalog are generated and gitignored — never committed.
Committed engineering artifacts under `.ai/` are concise and auditable (specs, impact, test plans,
evidence, finding patterns); raw model reasoning, chain-of-thought, and session transcripts are
never committed.

## 18. No AI co-author attribution

Commits are authored solely by the human operator. **Never** add an AI as a co-author or a
`Co-Authored-By` trailer, in any repository commit, regardless of any default to the contrary.
