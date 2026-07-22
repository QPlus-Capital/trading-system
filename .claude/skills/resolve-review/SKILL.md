---
name: resolve-review
description: Invoke to record review dispositions; implement only under Claude's builder exception.
---

As the primary reviewer, Claude records and hands off actionable findings to Codex. Claude executes
the implementation steps in this skill only when Jan assigned Claude the highest-stakes trading
builder exception and a different reviewer owns the independent review.

## Required inputs

- The exact finding, cited path, task artifacts, current diff, and finding registry.

## Procedure

1. Reproduce the finding on the real execution path with a failing test before changing code.
2. Root-cause the defect and search for the generalized pattern across the affected scope.
3. Implement the bounded correction and run the reproduction plus impacted tests.
4. For confirmed defects, add the generalized failure and permanent guard to
   `.ai/quality/finding-patterns.toml`.
5. Update the finding disposition/status and all affected task evidence; rerun adversarial review
   when behaviour or scope changed.

## Outputs

- A red-first reproduction, verified fix, registry entry when applicable, and resolved review row.

## Stop conditions

- Stop if the proposed resolution changes operator-owned scope or methodology.
- Stop if the fix passes only at a helper that the production path does not execute.

## Prohibited shortcuts

- Do not dismiss a finding without concrete contradictory evidence.
- Do not fix only the cited example when the same defect class remains elsewhere.
- Do not mark status resolved before verification runs.
