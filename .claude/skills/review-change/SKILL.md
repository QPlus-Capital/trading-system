---
name: review-change
description: Invoke as Claude's primary review path for a completed draft pull request.
---

This is Claude's primary review skill. It runs in a fresh session, is read-only and independent of
the builder, and delivers its result as a pull-request review.

## Required inputs

- Draft pull request, effective risk class, final touched paths, issue body, constitution, task
  artifacts, final diff, relevant source/tests, and deterministic gate evidence.

## Procedure

1. In a fresh session, run
   `uv run python -m scripts.quality.review_selection <RISK> --base origin/main`.
   Treat its output as the exact subagent set; do not select agents from prose or memory.
2. Invoke each selected read-only subagent with the issue contract, diff, evidence, and relevant
   executing paths. Never pass the builder's private context.
3. Reconcile their counterexamples against every acceptance criterion and invariant.
4. Submit one pull-request review: an inline `file:line` comment per finding and a summary with the
   findings table, contract check, chosen-approach assessment, and Jan-only decisions.
5. Use `Blocker`, `Defect`, `Suspected defect`, or `Note`. The first three block readiness.
6. Record the same findings and dispositions in `review.md`; if none survive, record the exact
   positive counterexample count.

## Outputs

- A read-only, fresh-context pull-request review and matching versioned review artifact.

## Stop conditions

- Stop when inputs or evidence are stale, a selected agent did not run, or any blocking finding
  remains unresolved.

## Prohibited shortcuts

- Do not edit files, commit, push, create or change pull-request state, or interact with live
  trading.
- Do not review your own implementation.
- Do not invent findings or accept narrative reassurance instead of executable evidence.
