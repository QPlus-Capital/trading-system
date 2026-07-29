# Test plan

All tests are in `tests/test_quality_mutation.py` and run against the production `check_baseline`
and the committed baseline, not against a fake.

| Requirement | Test | Before-fix | After-fix |
|---|---|---|---|
| AC-01 | `test_added_production_code_alone_no_longer_fails_the_ratchet` | RED: `['mutation total changed: expected 4646, observed 4774; …']` | GREEN: no issue |
| AC-02 | `test_an_unexplained_survivor_fails_whatever_the_total_is` (3 cases) | GREEN | GREEN |
| AC-03 | `test_a_score_regression_fails_although_the_total_is_no_longer_compared` | GREEN | GREEN |
| AC-04 | `test_a_changed_target_set_still_fails` | GREEN | GREEN |
| AC-05 | `test_both_totals_stay_visible_on_a_passing_and_a_failing_run` (2 cases) | RED: baseline total absent from the summary | GREEN |
| INV-01, INV-02 | `test_the_rule_changes_only_where_the_total_alone_differed` (128 cases) | GREEN, vacuously — the two rules were identical | GREEN, and now load-bearing |
| INV-03 | `test_a_baseline_whose_counts_do_not_sum_to_its_total_is_refused` (new) | N/A: untested before | GREEN |
| AC-06 | `test_policy_substitution_fails_with_exact_survivors_and_an_improved_score` | RED: same IDs/paths, exact survivors, clean health, and improved score returned no issue | GREEN: explicit policy-fingerprint failure |
| AC-07 | `test_policy_fingerprint_ignores_only_target_and_pattern_order`; `test_policy_fingerprint_binds_every_target_field_and_pattern_multiplicity` | RED: no policy fingerprint existed | GREEN: order is cosmetic; ID, path, content, and multiplicity are binding |
| AC-08 | `test_baseline_without_a_policy_fingerprint_is_refused` | RED: missing key loaded successfully | GREEN: missing or malformed SHA-256 identity refuses |
| AC-09, INV-04 | `test_report_serializes_its_required_policy_fingerprint`; `test_fast_report_fingerprints_the_whole_policy` | RED: report omitted the key | GREEN: both scopes serialize the complete-policy identity |

## What each test is for, and what it is not

**AC-02, AC-03 and AC-04 are preservation criteria and were green before the change.** They are
recorded here as green-before-and-after rather than dressed up as red-first proofs. Their purpose is
to fail if this change had reached further than intended; a red-first version would require breaking
the gate first, which proves nothing about this change.

**The differential oracle is what justifies removing a gate condition.**
`_rule_before_this_change` restates the five pre-change comparisons from the pre-change source rather
than calling the production function, so the test compares two implementations instead of comparing
one with itself. It generates 128 report shapes across six axes — killed count (4 values), an
unclassified survivor, dropped baseline survivors, a dropped target, scope, and an unhealthy mutant —
and asserts for each that the new verdict set is a subset of the old one, that the only verdict it
may drop is `total`, and that an `unexpected` verdict is never lost.

`test_the_differential_cases_actually_exercise_every_verdict` guards the oracle itself: a differential
proves nothing if the generated cases never trigger the verdicts being compared. It asserts that the
128 cases collectively produce all seven verdict kinds.

## Independent-review regression

The accepted 125-R1 counterexample keeps all target IDs and paths unchanged, removes the
killed-only `RiskController.trailing_floor` selector, and adds a broader trivial selector. Its
synthetic report preserves every reviewed survivor, has no unhealthy outcome, adds 128 killed
mutants, and improves the aggregate score. Before the fingerprint comparison,
`check_baseline` returned no issue; after it, the policy mismatch is the sole verdict.

The digest oracle is independent of production: it sorts targets by ID and patterns within each
target, serializes the exact `(id, path, patterns)` tuples, and hashes that representation. A mirrored
test reverses both orders and requires equality. Separate variants change each target field and add
duplicate pattern content so the implementation cannot canonicalize away any other policy fact.

`test_fast_report_fingerprints_the_whole_policy` drives the real `run("fast", ...)` report path with
a two-target policy and a one-target selected scope. The artifact must contain the two-target policy
fingerprint, proving the guard is not accidentally scope-dependent.

## Corrected fixture

`test_a_weakened_test_creates_a_survivor_and_the_ratchet_rejects_it` asserted that a weakened test
produces a `total` or `score` issue alongside the survivor issue. That held only because the fixture
built a report containing one new survivor and **no** baseline survivors at all — a report that could
only arise from deleting most of the production code, not from weakening a test. Weakening a test
moves one mutant from killed to survived and leaves the total unchanged.

The fixture now keeps the baseline survivors and adds one, so the total matches the baseline exactly
and the assertion is on the two verdicts a weakened test really causes: the named new survivor and
the score regression. The test is strictly stronger than before — it now names the specific mutant
rather than matching the substring `surviv`.

## A gap this plan found in itself

The first version of this table cited `test_a_baseline_whose_counts_do_not_sum_is_refused` for INV-03
as pre-existing. No such test existed: `load_baseline` enforces the sum at
`scripts/quality/mutation.py:214` but nothing exercised the rejection. The invariant that the
baseline's own recorded total stays coherent matters more after this change, not less, because the
gate no longer compares that number against anything. The test was written and is listed above as
new.

## Real-data replay

The synthetic cases are complemented by a replay of the actual CI artifact from the failing run on
PR #105 (`mutation-critical-result` of run 30432148064, report total 5106) against the baseline
committed at that run's commit `a221985` (total 4978). Recorded in `evidence.md`.
