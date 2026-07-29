# Review

## Findings

Codex completed the independent adversarial review of code HEAD
`dd5a3dfe832cd38cc262cf067eb1f5e13fe2a001`. The later branch commit only binds evidence to that
tree. One P1 finding remains unresolved, so the branch is not ready for a pull request.

### Independent findings

| ID | Severity | File:line | Finding | Concrete failure scenario | Proposed regression | Status |
|---|---|---|---|---|---|---|
| 125-R1 | P1 | `scripts/quality/mutation.py:298`, `scripts/quality/mutation.py:455`; exposed by `tests/test_quality_mutation.py:294` | Removing the total check leaves no binding on the full mutation target definitions: the report and baseline compare target IDs only, while `_validate_mutmut_config` checks paths only. A same-ID `mutant_patterns` substitution can silently stop measuring a critical function and still pass. | Keep every target ID and path unchanged; remove a killed-only pattern for a safety function and add a broader trivial pattern that produces 128 additional killed mutants. The reviewed survivor set stays exact, every health count is zero, and the score improves from `0.911752` to `0.914118`. The old rule fails on `expected 4646, observed 4774`; HEAD returns `[]`. The report shape cannot distinguish this coverage defect from the “added production code” case that AC-01 declares safe. | Bind a deterministic fingerprint of each complete target definition `(id, path, mutant_patterns)` into the critical report and baseline, then add a test that changes patterns under an unchanged ID/path and requires `check_baseline` to fail. Retain the total check until that replacement guard exists. | unresolved |

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

## Builder counterexamples (not independent review coverage)

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

The independent adversarial review is complete but **blocking on 125-R1**. The branch must not be
marked ready and no pull request should be opened until the target-definition blind spot is fixed
and independently re-reviewed.

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

## Independent attacks and results

1. **Defect counterexample — failed.** A target-policy coverage substitution is observable to the
   old gate only through the total. The executable report used the exact committed survivor set,
   zero unhealthy statuses, unchanged target IDs, and 128 replacement killed mutants. The old
   function failed on total; HEAD passed. This is finding 125-R1.
2. **Differential oracle — passed.** The function from commit `8b75ff0` was loaded and executed
   directly, not through `_rule_before_this_change`. Across 4,860 shapes, HEAD's exact issue list
   always equalled the old issue list with only the `mutation total changed` line removed. The
   hand-written oracle faithfully represents the old verdict logic.
3. **Case-generator boundaries — passed for the stated rule delta.** The expanded attack covered
   killed counts `0`, `1`, `K-1`, `K`, `K+1`, and `K+128`; exact, empty, missing, truncated,
   replaced, and unexpected survivor sets; every supported unhealthy status; critical, fast, and
   invalid scopes; and exact, empty, truncated, reversed, and extended target-ID tuples. It included
   zero and non-zero score denominators. No second rule difference appeared. The builder's generator
   still cannot express 125-R1 because it models only counts and target IDs, not target definitions.
4. **Reporting extraction — passed.** The first summary line is byte-for-byte the old inline
   string. Critical scope alone receives the additional total line; fast scope retains exactly one
   line. Exit codes, issue printing, the no-target early return, and report writing are unchanged.
5. **Summary consumers — passed.** A tracked-tree `git grep` covered root files, `.ai/**`, `docs/**`,
   `.github/**`, all packages, scripts, tests, and the justfile. Hits outside the definition and its
   tests are documentation/evidence only; no consumer parses the summary text.
6. **`missing`, score, and the corrected §15 fixture — passed.** The production diff leaves the
   survivor-set and score comparisons byte-identical. The corrected weakened-test fixture retains
   all baseline survivors, moves exactly one killed mutant to survived, asserts an unchanged total,
   names the new survivor, and requires a score regression. It removes the fixture-only total
   assertion but replaces it with strictly stronger behavior; no protection was deleted to obtain
   green.
7. **Real-data replay — passed.** The downloaded `mutation-critical-result` from run
   `30432148064` has SHA-256
   `FEC71F6AFA5D32144D3D896651F745FFEDE3CC40368E8A8EE826626D6F8763A2`.
   Against commit `a221985`'s baseline, the old function returned the total issue plus the two
   recorded unexplained survivors; HEAD returned exactly those same two survivors and nothing else.
8. **Executable checks — passed.** `tests/test_quality_mutation.py` reported 155 passed and one
   expected Windows Mutmut skip. Full `just check` reported 1,348 passed, one expected skip, with
   Ruff, strict mypy, and Vulture green.
