# Issue 73: Swap Codex and Claude workflow roles

## Problem

The tool-to-file binding is fixed, but `AGENTS.md`, `CLAUDE.md`, and related governance surfaces
still assign Claude the builder role and Codex the reviewer role.

## Goal

Make Codex the primary builder through `AGENTS.md`, Claude the primary conceptual designer and
reviewer through `CLAUDE.md`, and make that assignment executable and regression-proof.

## Non-goals

- Changing any hook, quality-gate, classifier, readiness, CI, or trading behaviour.
- Changing the live configuration, methodology, risk limits, or merge authority.
- Rewriting historical task artifacts, issues, or pull-request records.

## Behavioural requirements

- `AGENTS.md` is the builder contract and `CLAUDE.md` is the reviewer contract.
- Both contracts retain the immutable real-money safety constraints and link the constitution.
- Claude's review skills/subagents are the primary review path; its builder skills are reserved for
  the highest-stakes trading exception.
- Jan owns business, trading, methodology, live-money, architecture, risk, and every merge decision.

## Acceptance criteria

- AC-01: Root contracts carry the swapped role markers and reject the old assignment.
- AC-02: The constitution and all current contributor/runtime docs state the same roles and authority.
- AC-03: Claude review skills/subagents are primary, while builder skills state the exception scope.
- AC-04: A focused guard is red against the old `AGENTS.md` role and green after the swap.
- AC-05: The full R3 gate set passes with no tool, gate, CI, or trading behaviour change.

## Invariants

- INV-01: Both root contracts retain live-trade, risk, numeric, holdout, parity, secret, language,
  and authorship constraints inline.
- INV-02: Either agent may build highest-stakes trading work, but independent review remains mandatory.
- INV-03: Jan approves every merge and R3 never merges autonomously.
- INV-04: No production, trading, hook, quality-tool, workflow, or TOML behaviour changes.

## Assumptions

Claude auto-reads `CLAUDE.md` and Codex auto-reads `AGENTS.md`; the file binding cannot be changed.

## Open questions

None.

## Expected artifacts

- Swapped root role contracts, reconciled governance/runtime documentation, executable guard tests,
  this five-file task artifact, and one ready-for-review pull request.

## Risk class

R3 — governance contracts and their executable guard determine every repository change.

## Human decisions required

Jan retains all business, trading, methodology, live-money, architecture, risk, and merge decisions.
