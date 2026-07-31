# Issue 142: Mutate the board build-permit service

## Problem

`scripts/quality/board.py` is R3 and owns every build permit, but it is absent from the mutation
policy. A board-only change therefore selects no mutation target and cannot prove that its permit
guards are exercised.

## Goal

Make the board permit service a configured, precisely bounded mutation target whose complete native
Linux survivor set is recorded and ratcheted by exact mutant name.

## Acceptance criteria

- AC-01: The fast selector returns only the board target for a changed board module and omits it for
  unrelated paths.
- AC-02: The baseline records the exact board survivor names, never a count threshold or percentage.
- AC-03: The policy fingerprint changes with the target and the baseline records the recomputed
  value.
- AC-04: Every recorded board survivor has a classification and a non-empty observability reason.
- AC-05: Native mutation kills a flipped build-permit guard predicate.
- AC-06: The production mutation workflow selects a board-only change.
- AC-07: An unexplained new board survivor fails the exact ratchet.

## Invariants

- INV-01: Existing targets, patterns, baseline survivors, and comparison rules remain intact and in
  their current order.
- INV-02: `scripts/quality/board.py` remains byte-identical to `origin/main`.
- INV-03: Missing or unsupported Mutmut execution remains a failure, never a reported pass.

## Scope

Mutation policy, matching Mutmut configuration and test selection, exact baseline data, new
behavioral mutation-policy tests, and R3 task artifacts.

## Non-goals

No mutation-runner, fingerprint-algorithm, Board behavior, workflow, existing test assertion,
threshold, percentage, tolerance, or additional production target change.

## Risk class

R3. The mutation policy decides whether future R3 changes prove their tests can fail.

## Human decisions required

None. Jan approved issue #142 after #136's review findings were resolved and merged.
