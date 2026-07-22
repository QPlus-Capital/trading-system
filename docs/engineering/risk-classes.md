# Change risk classes

Every non-trivial change carries a risk class. The class controls which quality gates are mandatory
before the change can reach a pull request, and whether it may merge autonomously. This is the prose
companion to the machine-readable model in
[`.ai/quality/risk-classes.toml`](../../.ai/quality/risk-classes.toml); the two must agree, which
`tests/test_engineering_docs.py` checks.

## How the class is decided

1. **Safe by default.** Each changed path is matched against the rules in the TOML; the class is the
   **highest** among the matched rules. An explicit rule always wins. A path that matches **no** rule
   is `R0` only if it is a plain, non-governance document (the docs-only fallback); otherwise it
   falls back to **`R2`** — never `R1`. Governance and methodology documents (`docs/engineering/**`,
   `docs/methodology.md`, `docs/live-runbook.md`, `docs/strategies/**`, `CLAUDE.md`, `AGENTS.md`)
   carry explicit R3 rules, so they never take the docs-only R0 path.
2. **Semantic upgrade (mandatory).** The author raises the class when the real impact is broader
   than the paths suggest — e.g. a helper that a sizing function calls, or a config value that flows
   into live. Path matching may never *lower* the class below the matched minimum.

The class and the one-line reason go in the task spec and the PR.

## The classes

| Class | What it is | Mandatory gates (beyond the lower classes) |
|-------|------------|---------------------------------------------|
| **R0** | Documentation or comments only; no behaviour change. | format check, docs consistency |
| **R1** | Local non-financial code (tooling, scripts) with no financial, methodology, or result-integrity impact. | `just check`, impacted tests |
| **R2** | Shared core, research orchestration, artifact schema, configuration, or monitoring semantics — depended on widely, but not on the money or methodology path. | property tests where applicable, integration tests, artifact/schema checks, adversarial review |
| **R3** | The live-money path, position sizing, risk control, account identity, order placement, signal parity, broker/instrument conversion, money calculations, trading methodology, holdout handling, selection logic, or result integrity. | explicit invariants, mutation testing on touched critical functions, parity checks where applicable, adversarial review, **live-money review**, human decision escalation for ambiguous domain choices, and **no autonomous merge** |

Gates are cumulative: R2 includes R1's, R3 includes R2's.

Codex is the primary builder and Claude is the primary conceptual designer and independent
reviewer. For highest-stakes trading work, either agent may build, but the other agent must perform
the independent review. Jan decides business, trading, methodology, live-money, architecture, and
risk questions and approves every merge. An R3 change never merges autonomously.

`pr-ready` binds those cumulative gate IDs to the task's `evidence.md`. Every required gate must
have a record with exit status 0, and any non-zero record for a required gate blocks readiness even
when another attempt passed. Before-fix failures use the non-gate label `red-first`. For R3, the
review must contain at least one finding row or explicitly record `No findings; N counterexamples
attempted` with `N >= 1`; an empty review is not evidence that adversarial review ran.

## R3 — the paths that are always at least R3

The **authoritative, exhaustive list is the model** (`.ai/quality/risk-classes.toml`); this prose
deliberately does not repeat it, so the two cannot drift. By category, R3 covers:

- the whole **live trading package** (`live/**`) — orders, sizing, risk control, account identity,
  the broker bridge, and signal-parity checks;
- the **shared strategy signals**, **broker**, and **instrument** definitions in `core/`, plus the
  **broker cost/swap snapshots** that feed net returns;
- the whole **research engine and portfolio** (`research/engine/**`, `research/portfolio/**`) and
  the **stages** and **config** — selection, methodology, money, holdout, and reported results;
- the **regression gate** and the **quality model itself** (`.ai/quality/**`).

A change to any of these ranks parameters, sizes a position, moves money, decides selection, or
guards result integrity. It gets the full R3 treatment and a human approves the merge. The concrete
globs and their reasons live in the model; `tests/test_engineering_docs.py` asserts real production
paths on these categories resolve to R3.

## Why the upgrade rule matters

The most expensive defects this repository has seen were **coupled-quantity** changes: a value
(a sizing basis, a risk denominator, a cost) was changed at one call site while other consumers were
left inconsistent. Path matching cannot see that. Before changing such a value, enumerate every
place it enters the pipeline and raise the class to cover all of them. See the finding registry
(`.ai/quality/finding-patterns.toml`) for the recorded instances.
