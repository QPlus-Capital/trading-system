---
name: build-change
description: Invoke only when Jan explicitly assigns Claude the highest-stakes trading builder exception.
---

Claude uses this skill only when Jan explicitly assigns the highest-stakes trading builder
exception. Codex remains the primary builder. This path combines impact analysis, test design,
implementation, verification, and draft-PR preparation without granting Claude any review role.
A fresh independent reviewer other than the builder must review the result.

## Required inputs

- An approved issue in `Ready to Implement`, `approved`, `risk:Rn`, the constitution, architecture,
  repository state, and Jan's explicit assignment of the builder exception.

## Procedure

1. Consume the build permit in the required order and create the issue branch and worktree.
2. Trace affected files, callers, configuration routes, lifecycle, artifacts, tests, and dynamic
   edges into the risk-class task artifacts.
3. Map every acceptance criterion and invariant to one named behavioural test. Add it before the
   implementation and record the actual failing result.
4. Implement the smallest bounded change; update every caller and current-state document it
   affects. Never interact with live trading.
5. Run focused tests, then every cumulative gate required by the effective risk class. Record exact
   command results and current HEAD.
6. Commit and push the verified branch, open a draft pull request, and hand it to a fresh
   independent reviewer.

## Outputs

- A bounded implementation, red/green proof, complete required artifacts, green deterministic
  gates, and a draft pull request ready for independent review.

## Stop conditions

- Stop on a missing permit, unresolved Jan decision, unplanned scope expansion, failed gate, stale
  evidence, or any verification that would touch live trading.

## Prohibited shortcuts

- Never review your own work or invoke a reviewer from the builder's context.
- Do not use this skill unless Jan assigned the explicit highest-stakes trading exception.
- Do not weaken a test, hook, threshold, mutation baseline, or quality policy.
- Do not mark ready, merge, or enable auto-merge.
