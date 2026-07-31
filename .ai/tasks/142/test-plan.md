# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_board_build_permit_is_a_precisely_bounded_mutation_target`; `test_fast_scope_selects_only_a_changed_board_build_permit_target` | RED: no board target exists and selection returns `[]` | GREEN: the exact board target is selected only for its production path |
| AC-02 | `test_board_baseline_records_exact_named_survivors_with_reasons`; native critical report comparison | RED: baseline has no board target or board survivor names | GREEN: every observed survivor is listed by exact name; no threshold or percentage is introduced |
| AC-03 | `test_committed_critical_baseline_is_complete_and_explained` | RED after policy edit: baseline fingerprint differs from the recomputed policy fingerprint | GREEN: the recomputed fingerprint is recorded exactly |
| AC-04 | `test_board_baseline_records_exact_named_survivors_with_reasons` plus source inspection of native survivors | RED: no board survivors can be classified while the target is absent | GREEN: every survivor has a valid classification and non-empty specific reason |
| AC-05 | Native Linux `mutation-fast`/critical report plus named Board behavior tests | RED: board-only change selects no mutants, so guard flips are unmeasured | GREEN: selected guard-predicate mutants report killed; any survivor is explicitly classified |
| AC-06 | `test_mutation_job_runs_for_production_and_direct_critical_test_changes` | RED: production workflow predicate returns false for `scripts/quality/board.py` | GREEN: board-only path selects the critical mutation job |
| AC-07 | `test_a_new_board_guard_survivor_fails_the_exact_ratchet` | RED: the baseline has no board target against which to construct the target-specific regression | GREEN: one synthetic unlisted board survivor produces an unexplained-survivor failure |
| INV-01 | Policy/baseline structural diff and full mutation suite | RED: not applicable; existing entries form the comparison oracle | GREEN: all pre-existing entries remain byte-ordered and unchanged |
| INV-02 | `git diff --exit-code origin/main -- scripts/quality/board.py` | RED: not applicable; production starts unchanged | GREEN: Board production file remains byte-identical |
| INV-03 | `test_native_windows_mutation_fails_with_the_documented_linux_direction`; real Linux tool probe | RED: not applicable; fail-closed behavior already exists | GREEN: Windows refuses and Linux executes the pinned tool |

## Red-first procedure

1. Add only the new target/config/baseline/workflow expectations.
2. Run the named focused tests against the unchanged policy and retain every failure.
3. Add the target and mirrored Mutmut configuration without touching Board production behavior.
4. Push the green non-baseline implementation branch and run native Linux mutation to obtain the
   exact report.
5. Classify every survivor, update the exact baseline and fingerprint, and rerun the ratchet.
