# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_board.py::test_arm_refuses_a_card_outside_ready_without_mutation` | RED: board module absent | GREEN: non-ready cards fail before any GitHub write |
| AC-02 | `tests/test_quality_board.py::test_arm_derives_contract_order_and_never_approves_after_status_failure` | RED: board module absent | GREEN: sorted contract actions reach status before approved and stop on failure |
| AC-03 | `tests/test_quality_board.py::test_start_moves_before_removing_permit_and_preserves_it_on_failure` | RED: board module absent | GREEN: failed Implementing move leaves approved present |
| AC-04 | `tests/test_quality_issue_body.py::test_r2_issue_body_rejects_each_invalid_shape` | RED: issue-body module absent | GREEN: missing section, absent/unnumbered/noncontiguous ACs, unjustified risk, and open decisions fail |
| AC-05 | `tests/test_quality_issue_body.py::test_issue_body_accepts_valid_r2_and_skips_r0_r1` | RED: issue-body module absent | GREEN: valid R2 passes and R0/R1 are not validated |
| AC-06 | `tests/test_quality_issue_body.py::test_scaffold_task_copies_only_files_required_by_issue_risk` | RED: scaffolder absent | GREEN: R0/R1 create no directory, R2 creates two files, R3 creates four |
| AC-06 | `tests/test_quality_issue_body.py::test_just_new_task_delegates_to_the_production_scaling_scaffolder` | RED: recipe absent | GREEN: recipe invokes the production module with the issue number |
| Runtime status mapping | `tests/test_quality_board.py::test_every_contract_status_must_resolve_to_a_runtime_option` | RED: board adapter absent | GREEN: one missing board option blocks before mutation |
| Project scope | `tests/test_quality_board.py::test_missing_project_scope_has_one_actionable_error` | RED: GitHub adapter absent | GREEN: missing scope reports the required remediation without a raw 404 |
| INV-01 | `tests/test_quality_board.py::test_public_command_surface_cannot_done_merge_approve_or_create_pr` | RED: command surface absent | GREEN: only status/add/move/arm/start exist and Done is refused |
| INV-02 | `tests/test_quality_board.py::test_every_arm_write_failure_leaves_approved_absent` | RED: ordered service absent | GREEN: each injected GitHub failure stops before an approved state can remain |

