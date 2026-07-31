# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_board_build_permit_is_a_precisely_bounded_mutation_target`; `test_fast_scope_selects_only_a_changed_board_build_permit_target` | RED: no board target exists and selection returns `[]` | GREEN: both pass; the exact Board target is selected alone for `scripts/quality/board.py` and unrelated paths select none |
| AC-02 | `test_board_baseline_records_exact_named_survivors_with_reasons`; native critical report comparison | RED: baseline has no Board target or Board survivor names | GREEN: run `30618204290` reports exactly the three names recorded in the baseline; no threshold or percentage exists |
| AC-03 | `test_committed_critical_baseline_is_complete_and_explained` | RED after policy edit: old fingerprint `8de068…` differs from recomputed `5783b1…` | GREEN: the baseline records `5783b118651992534d0c08801ce8e11407ed7059618e47baa92440a8b78b64c5` exactly |
| AC-04 | `test_board_baseline_records_exact_named_survivors_with_reasons` plus generated-source inspection | RED: no Board survivors can be classified while the target is absent | GREEN: all three survivors share one specific equivalent classification that proves both reachable input partitions |
| AC-05 | Native Linux critical reports plus the new named Board behavior tests | RED: first run `30616591967` reported 42 Board survivors | GREEN: the same 314 Board mutants in `30617552213` report 311 killed and only three equivalent survivors; the final exact ratchet passes in `30618204290` |
| AC-06 | `test_mutation_job_runs_for_production_and_direct_critical_test_changes` | RED: production workflow predicate returns false for `scripts/quality/board.py` | GREEN: the unchanged production workflow predicate selects a Board-only path |
| AC-07 | `test_a_new_board_guard_survivor_fails_the_exact_ratchet` | RED: the baseline has no Board target against which to construct the target-specific regression | GREEN: a synthetic unlisted Board survivor produces the exact unexplained-survivor failure |
| INV-01 | Policy/baseline structural diff and final native critical report | RED: not applicable; existing entries form the comparison oracle | GREEN: the prior 27 targets and 410 exact survivors remain in order and unchanged; the new target and group are appended |
| INV-02 | `git diff --exit-code origin/main -- scripts/quality/board.py` | RED: not applicable; production starts unchanged | GREEN: exit 0; Board production is byte-identical |
| INV-03 | `test_native_windows_mutation_fails_with_the_documented_linux_direction`; native Linux run `30618204290` | RED: not applicable; fail-closed behavior already exists | GREEN: Windows retains its expected refusal and Linux executes pinned Mutmut 3.5.0 successfully |

## Red-first procedure

1. Add only the new target/config/baseline/workflow expectations.
2. Run the named focused tests against the unchanged policy and retain every failure.
3. Add the target and mirrored Mutmut configuration without touching Board production behavior.
4. Push the green non-baseline implementation branch and run native Linux mutation to obtain the
   exact report.
5. Classify every survivor, update the exact baseline and fingerprint, and rerun the ratchet.

The procedure was executed in three commits: `5169c5d` established the red contract and first native
measurement, `44d5d4a` added only the new behavioral killers and produced the reduced survivor set,
and `d1ee42b` committed the exact baseline that passed the final native ratchet.
