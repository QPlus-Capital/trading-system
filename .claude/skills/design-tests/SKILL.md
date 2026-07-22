---
name: design-tests
description: Invoke to design acceptance tests for Codex or Claude's trading-work build exception.
---

Use this skill during Claude's conceptual design to specify executable acceptance tests for Codex.
It is mandatory before Claude changes code under the highest-stakes trading-work builder exception.

## Required inputs

- The task spec, impact artifact, constitution test dimensions, and current implementation/tests.

## Procedure

1. Map every AC and invariant to an executable behavioural test in `test-plan.md`.
2. Include relevant lifecycle, configuration propagation, unclassified outcome, boundary, numeric,
   reconciliation, parity, and fail-closed counterexamples.
3. Add the tests before the implementation and execute the focused command.
4. Record the exact failing result as red-first evidence; distinguish expected missing behaviour
   from an invalid test setup.
5. Use the existing property and mutation tooling when the changed behaviour falls within its scope.

## Outputs

- Complete AC/INV test traceability and reproducible red-first evidence.

## Stop conditions

- Stop if a new test passes before the change without proving an existing defect by another means.
- Stop if a test would need live account or order interaction.

## Prohibited shortcuts

- Do not assert implementation text when observable behaviour can be asserted.
- Do not weaken, skip, or broadly suppress a test to force green.
- Do not claim red-first without recording the actual command and non-zero result.
