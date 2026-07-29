# Spec

The authoritative specification is issue #125. This file carries the schema-required sections.

## Problem

`check_baseline` compares the observed mutant total against the baseline total. The total primarily
counts how much mutable production code exists, so ordinary additions and removals move it without
describing test quality. The accepted review finding proved one narrower exception: changing
`mutant_patterns` also moves the total, while target IDs and paths, survivors, health, and score can
all remain acceptable. Removing the broad total comparison without a specific target-definition
binding left mutation-policy coverage unguarded.

## Goal

The mutation ratchet fails when and only when the mutation evidence got worse.

## Non-goals

No change to the unexplained-survivor check, the score comparison, the target-set comparison, the
health checks, the `missing` tightening check, the fast-scope verdict, `.ai/quality/mutation.toml`,
any target, pattern, threshold, or survivor classification. The baseline keeps its recorded total
and gains only the required policy fingerprint.

## Behavioural requirements

A critical run reports a failure when a surviving mutant is not classified in the baseline, when the
mutation score falls below the baseline score, when the target set differs, or when any mutant ends
in an unhealthy status. It also fails when the deterministic fingerprint of all policy targets'
`(id, path, mutant_patterns)` definitions differs. A difference in the mutant total alone is
reported as information and does not fail the run.

## Acceptance criteria

- AC-01 A report identical to the baseline except for additional killed mutants passes.
- AC-02 An unclassified surviving mutant still fails, whether or not the total matches.
- AC-03 A mutation score below the baseline still fails, whether or not the total matches.
- AC-04 A differing target set still fails.
- AC-05 The observed and baseline totals appear in the output of a passing and a failing run.
- AC-06 A same-ID/path substitution of one killed-only safety pattern for a broader trivial pattern
  fails even with exact survivors, clean health, and an improved score.
- AC-07 Reordering targets or patterns leaves the policy fingerprint unchanged; changing an ID,
  path, pattern content, or pattern multiplicity changes it.
- AC-08 `load_baseline` refuses a missing or malformed policy fingerprint.
- AC-09 Every critical and fast report serializes the fingerprint of the complete policy, never only
  the selected scope.

## Invariants

- INV-01 Every report that failed before this change for a reason other than the total alone still
  fails after it.
- INV-02 No survivor that was unexplained before this change becomes accepted by it.
- INV-03 `load_baseline` still rejects a baseline whose per-status counts do not sum to its total.
- INV-04 The total comparison remains absent; policy coverage is bound by the specific fingerprint
  comparison without changing `missing`, score, health, target-ID, or fast-scope verdicts.

## Assumptions

The mutant total is a function of both mutable production code and the policy that selects it; it is
not a measure of test strength. The two consecutive CI runs on PR #105 still show why total alone is
not a useful quality verdict, but they do not justify leaving policy changes unbound. The replacement
guard hashes the complete policy definitions and compares that exact, scope-independent identity.

## Open questions

None.

## Expected artifacts

`scripts/quality/mutation.py`, `tests/test_quality_mutation.py`,
`.ai/quality/mutation-baseline.toml`, `.ai/quality/finding-patterns.toml`, and the five files in this
directory.

## Risk class

R3 — `scripts/quality/**` is a gate path and this removes a condition under which a gate fails.

## Human decisions required

Jan accepted finding 125-R1 and ratified the complete target-definition fingerprint as the specific
replacement for the incidental policy protection formerly supplied by the mutant-total comparison.
