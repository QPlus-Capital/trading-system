---
name: resolve-review
description: Invoke whenever adversarial or pull-request review reports an actionable finding.
---

This skill is mandatory for every actionable P0-P3 review finding selected for resolution.

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
