---
name: resolve-findings
description: Invoke to verify and hand off review findings without editing the builder's change.
---

This is a read-only reviewer skill. Claude verifies findings, generalizes confirmed defects, and
hands executable remediations to the builder. The builder alone changes the branch.

## Required inputs

- Exact finding, cited path, issue contract, final diff, relevant execution path, tests, and finding
  registry.

## Procedure

1. Reproduce or falsify the finding on the real execution path with a concrete counterexample.
2. Root-cause confirmed defects and search the affected scope for the generalized pattern.
3. Specify the failing behavioural regression and the smallest bounded correction for the builder.
4. Require a new content-addressed finding-pattern file for every confirmed defect, naming the
   permanent executable guard.
5. After the builder pushes a correction, verify the regression and rerun the complete
   `review-change` path in fresh context.
6. Update only the pull-request review disposition through the review interface; the builder owns
   repository artifact edits.

## Outputs

- Verified finding dispositions and an executable remediation handoff to the builder.

## Stop conditions

- Stop if the correction needs an operator decision, expands scope, or passes only at a helper the
  production path does not execute.

## Prohibited shortcuts

- Do not edit files, commit, push, implement the fix, or interact with live trading.
- Do not dismiss a finding without concrete contradictory evidence.
- Do not mark a finding resolved before executing its permanent guard.
