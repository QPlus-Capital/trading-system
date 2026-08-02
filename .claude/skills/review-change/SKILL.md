---
name: review-change
description: Invoke as Claude's primary review path for a completed pull request.
---

This is Claude's primary review skill. It runs in a fresh session, is read-only and independent of
the builder, and delivers its result as a pull-request review. The orchestrator starts it with the
issue number; the branch and its pull request follow from that.

## Required inputs

- The issue number, its contract, the effective risk class, the final diff and touched paths, the
  gate results, and the relevant source and tests.

## Procedure

1. In a fresh session, read the agent selection from the `[review]` table of `.ai/workflow.toml`
   for the effective risk class and the touched paths. Do not select agents from prose or memory.
2. Invoke each selected read-only subagent with the issue contract, the diff, the gate results, and
   the executing paths. Never pass the builder's private context.
3. Reconcile their counterexamples against every acceptance criterion and invariant.
4. Submit one pull-request review: an inline `file:line` comment per finding, and a summary with the
   findings table, the contract check, an assessment of the chosen approach, and the decisions that
   belong to the operator.
5. Use `Blocker`, `Defect`, `Suspected defect`, or `Note`. Only the first two block and trigger a
   fix round; the other two are collected for the operator.
6. If no finding survives, record the exact number of counterexamples attempted.

## Outputs

- A read-only, fresh-context pull-request review that names its severities and its counterexamples.

## Stop conditions

- Stop when inputs or gate results are stale, or when a selected agent did not run.
- Stop and escalate to the operator when a finding needs a decision only the operator can make.

## Prohibited shortcuts

- Do not edit files, commit, push, change pull-request state, merge, or interact with live trading.
- Do not review your own implementation. You never build.
- Do not invent findings, and do not accept narrative reassurance instead of executable evidence.
