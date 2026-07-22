---
name: create-issues
description: Invoke when valid work is discovered outside the active task scope and needs a separate issue.
---

This skill is mandatory when implementation or review discovers valid out-of-scope work.

## Required inputs

- The observed gap, concrete evidence, affected files, severity, and active task's non-goals.

## Procedure

1. Confirm the work is valid, distinct from the active acceptance criteria, and not required to keep
   the current implementation safe or correct.
2. Search existing issues to avoid duplicates.
3. Create one bounded issue with problem, failure scenario, proposed acceptance criteria,
   dependencies, risk class, and why it is deferred.
4. Link the issue from the active task and PR without changing the active scope.

## Outputs

- A separately scoped, deduplicated issue and a traceable reference from the current work.

## Stop conditions

- Stop and resolve in the current task if the finding is required for safety or an existing AC.
- Stop before issue creation if the evidence is speculative rather than actionable.

## Prohibited shortcuts

- Do not widen the current PR for convenience.
- Do not file vague cleanup or style issues without a concrete failure or outcome.
- Do not duplicate an existing open issue.
