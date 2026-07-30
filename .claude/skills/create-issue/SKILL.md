---
name: create-issue
description: Invoke when one valid out-of-scope finding needs a separate issue.
---

Use this skill when implementation or review discovers valid work outside the active issue.

## Required inputs

- The observed gap, concrete evidence, affected files, severity, active scope, and non-goals.

## Procedure

1. Confirm the work is valid, distinct, actionable, and not required for the current change.
2. Search open and closed issues for duplicates.
3. Create one bounded issue with the problem, failure scenario, acceptance criteria, invariants,
   dependencies, risk class, and reason it is deferred.
4. Link it from the active issue or pull request without widening the active change.

## Outputs

- One separately scoped, deduplicated issue with traceable evidence.

## Stop conditions

- Stop and return it to the current builder if it is required for an existing criterion or safety.
- Stop before creation when evidence is speculative.

## Prohibited shortcuts

- Do not file multiple unrelated concerns in one issue.
- Do not create vague cleanup or style issues without a concrete failure.
- Do not duplicate an existing issue or widen the current pull request.
