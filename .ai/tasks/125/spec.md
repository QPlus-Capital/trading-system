# Spec

The authoritative specification is issue #125. This file carries the schema-required sections.

## Problem

`check_baseline` compares the observed mutant total against the baseline total. The total counts how
much mutable production code exists, so it moves whenever a branch adds or removes a line and cannot
move in response to a defect. The gate is therefore red for the whole life of every branch that adds
code, beside the verdicts that do carry meaning.

## Goal

The mutation ratchet fails when and only when the mutation evidence got worse.

## Non-goals

No change to the unexplained-survivor check, the score comparison, the target-set comparison, the
health checks, the `missing` tightening check, the fast-scope check, `.ai/quality/mutation.toml`, any
target, or any survivor classification. The baseline keeps its recorded total.

## Behavioural requirements

A critical run reports a failure when a surviving mutant is not classified in the baseline, when the
mutation score falls below the baseline score, when the target set differs, or when any mutant ends
in an unhealthy status. A difference in the mutant total alone is reported as information and does
not fail the run.

## Acceptance criteria

- AC-01 A report identical to the baseline except for additional killed mutants passes.
- AC-02 An unclassified surviving mutant still fails, whether or not the total matches.
- AC-03 A mutation score below the baseline still fails, whether or not the total matches.
- AC-04 A differing target set still fails.
- AC-05 The observed and baseline totals appear in the output of a passing and a failing run.

## Invariants

- INV-01 Every report that failed before this change for a reason other than the total alone still
  fails after it.
- INV-02 No survivor that was unexplained before this change becomes accepted by it.
- INV-03 `load_baseline` still rejects a baseline whose per-status counts do not sum to its total.

## Assumptions

The mutant total is a function of the mutable production code selected by the target patterns, not of
test strength. Verified against the two consecutive CI runs on PR #105 recorded in `evidence.md`:
between them the survivor count fell from 53 to 2 while the total moved independently.

## Open questions

None.

## Expected artifacts

`scripts/quality/mutation.py`, `tests/test_quality_mutation.py`, and the five files in this
directory.

## Risk class

R3 — `scripts/quality/**` is a gate path and this removes a condition under which a gate fails.

## Human decisions required

None. Jan directed the change in conversation on 2026-07-29 after being shown the measurement.
