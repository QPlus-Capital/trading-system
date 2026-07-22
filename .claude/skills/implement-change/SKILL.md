---
name: implement-change
description: Invoke only after specification impact analysis and red-first tests to implement the bounded change.
---

This skill is mandatory for implementation after `specify-change`, `impact-analysis`, and
`design-tests` complete.

## Required inputs

- Valid task artifacts, recorded red-first evidence, impact recommendation, and repository rules.

## Procedure

1. Implement the smallest change that satisfies the mapped tests and preserves every invariant.
2. Update all callers, current-state docstrings, tests, and the architecture map as the diff requires.
3. Run the focused tests after each coherent change; do not run the full suite after every edit.
4. Run the risk class's complete required gates at the implementation boundary.
5. Record any confirmed defect pattern in `.ai/quality/finding-patterns.toml` with its permanent guard.

## Outputs

- A bounded implementation with green focused tests and no stale callers or documentation.

## Stop conditions

- Stop on an unplanned scope expansion or unresolved operator decision.
- Stop if verification requires interacting with live trading.

## Prohibited shortcuts

- Do not bypass a hook, test, type checker, linter, mutation threshold, or baseline.
- Do not duplicate an existing quality policy in a new matcher.
- Do not widen the task to absorb unrelated valid findings.
