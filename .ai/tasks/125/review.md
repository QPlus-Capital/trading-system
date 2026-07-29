# Review

## Findings

The independent adversarial review is **owed and has not been performed**. Claude built this change,
and constitution §19 and `CLAUDE.md` both forbid the builder from reviewing its own work. Codex must
perform the complete review in fresh context before this branch is marked ready.

The findings below were raised by the builder against its own work during construction. They are
recorded for the reviewer's benefit and are explicitly **not** a substitute for the independent
review.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| 125-B1 | P2 | `test-plan.md` cited `test_a_baseline_whose_counts_do_not_sum_is_refused` for INV-03 as pre-existing. No such test existed: `load_baseline` enforced the sum at `scripts/quality/mutation.py:214` with nothing exercising the rejection. | Wrote `test_a_baseline_whose_counts_do_not_sum_to_its_total_is_refused`. The invariant matters more after this change, not less, because the gate no longer compares the recorded total against anything, so nothing else would notice an incoherent baseline. The plan records the gap instead of quietly citing the new name. | resolved |
| 125-B2 | P2 | `tests/test_quality_mutation.py:200` asserted a `total` or `score` verdict alongside the survivor verdict for a weakened test. It passed on `total`, which weakening a test does not cause; the fixture dropped every baseline survivor and so described deleted code. | The fixture keeps the baseline survivors and adds one, so the total matches the baseline exactly and the assertions are on the two verdicts a weakened test really causes. Strictly stronger: it names the specific mutant instead of matching the substring `surviv`. | resolved |
| 125-B3 | P3 | The first differential case set omitted the target-set axis, so the coverage guard would have asserted a verdict the cases never produced. | `drop_last_target` added as a sixth axis; 128 shapes, and the coverage assertion lists all seven verdict kinds including `targets`. | resolved |
| 125-B4 | P3 | `impact.md` asserted a grep result before it had been run. | The search was run across `justfile`, `scripts`, `.github`, `tests`, `core`, `research`, `live` and `monitoring`; exactly one hit, the definition site. The claim was corrected to the verified result. | resolved |
| 125-B5 | P3 | `summary_lines` gained a critical-scope line with no test that the fast scope stays unchanged, although the fast path never consults a baseline. | Wrote `test_the_fast_scope_summary_is_unchanged_by_the_critical_baseline_line`, asserting exact equality of the fast summary and the absence of the baseline total. | resolved |

## Counterexamples attempted

1. A report that adds killed mutants only — must pass, and does.
2. An unclassified survivor with the total above, below and equal to the baseline — must fail in all
   three, and does.
3. Fewer kills against the unchanged reviewed survivor set — score regression must still fail.
4. A dropped critical target — must still fail.
5. A fast-scope report — must not acquire a critical verdict or a baseline line.
6. An unhealthy mutant status combined with every other axis.
7. Baseline survivors dropped from the report, exercising the untouched `missing` verdict.
8. 128 generated report shapes replayed against a hand-written restatement of the pre-change rule.
9. The real Linux CI artifact of run 30432148064 replayed against the baseline at its own commit.

## Dispositions

All five builder findings are resolved with the executable proof named in the table above; the
resolutions are in the committed tree and covered by `tests/test_quality_mutation.py`.

The independent adversarial review is **unresolved and blocking**. `evidence.md` records the
`adversarial-review` gate at exit 1 for this reason, which is why readiness fails today. That is the
correct state, not a defect to work around.

## What the reviewer should attack

This change removes a condition under which an R3 gate fails, which is adjacent to constitution §15.
The argument is that the removed condition cannot bind against a defect. The reviewer should try to
break that argument, not confirm it. Specifically:

1. **Find a defect whose only observable symptom is a changed mutant total.** The claim is that no
   such defect exists because the total counts mutable production code. A counterexample kills this
   change.
2. **Attack the differential oracle.** `_rule_before_this_change` is a hand-written restatement of the
   pre-change rule. If it does not faithfully reproduce the pre-change source, the differential proves
   nothing. Compare it against `scripts/quality/mutation.py` at `8b75ff0`.
3. **Attack the case generator.** 128 shapes across six axes is not exhaustive. Look for a report
   shape where the old and new rules differ on something other than `total` and that the axes cannot
   express — in particular around `missing`, which is deliberately untouched here, and around the
   interaction between an unhealthy status and the score denominator.
4. **Check the reporting path.** `summary_lines` was extracted from `run` and then extended. Verify
   the extraction was behaviour-preserving for the fast scope, which takes the `_check_fast` path and
   must not gain the critical-scope line.
5. **Check that no consumer parses the summary text**, including anything outside the searched
   directories.
