# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_review_observation.py::test_a_code_commit_after_every_review_makes_the_review_stale` | RED: a backdated later code commit remained verified under timestamp comparison | GREEN: the review's `commit_id` precedes the current code commit and is rejected regardless of time |
| AC-02 | `tests/test_quality_review_observation.py::test_review_verdict_comes_from_the_latest_review_after_the_last_code_commit` | RED: the branch had no external review observation | GREEN: a non-blocking review bound to the current code commit verifies independently of audit prose |
| AC-03 | `tests/test_quality_pr_ready.py::test_r2_requires_the_observed_review_as_well_as_dispositions` | RED: R2 discarded the supplied rejected observation | GREEN: R2 and R3 require the observed review in addition to resolved dispositions |
| AC-04 | `tests/test_quality_validate_task.py::test_review_markdown_shape_is_not_a_gate_input` | RED: exact prose certified completion | GREEN: prose shape cannot certify completion; required sections and blocking dispositions remain independent structural gates |
| AC-05 | `tests/test_quality_pr_ready.py::test_task_validator_and_pr_readiness_apply_the_same_review_verdict` | RED: no shared verdict existed | GREEN: all three observation states agree under strict enforcement |
| AC-06 | `tests/test_quality_pr_ready.py::test_review_and_evidence_commits_may_follow_the_tested_head` | RED: review.md invalidated evidence | GREEN: only review.md and evidence.md may follow the tested commit |
| AC-07 | `tests/test_quality_review_observation.py::test_ci_scope_detector_uses_the_real_no_rename_git_diff` | RED: the embedded workflow body had no executable wiring test | GREEN: the shared entrypoint reads the real no-rename delta; mixed or renamed paths select full CI |
| INV-01 | `tests/test_quality_review_observation.py::test_gateway_parses_all_pages_and_preserves_rename_sources` | RED: `previous_filename` and review `commit_id` were discarded | GREEN: complete path provenance and server-bound review identity reach the decision |
| INV-02 | `tests/test_quality_review_observation.py::test_ci_scope_detector_fails_closed_to_the_full_set_for_an_unreachable_base` | RED: an unreachable pre-force-push SHA raised and wedged the workflow | GREEN: diff uncertainty selects the full gate set |
| INV-03 | `tests/test_quality_validate_task.py::test_observed_review_does_not_clear_an_unresolved_blocking_finding` | RED: all six R2/R3 blocking cases passed under a verified observation | GREEN: observation, structure, and disposition are independent cumulative requirements |

## Review-finding regressions

| Finding | Executable protection |
|---|---|
| D-01 / D-02 / D-03 | `tests/test_quality_validate_task.py::test_review_sections_bind_independently_of_the_observed_review`, `tests/test_quality_hooks.py::test_real_staged_task_snapshot_blocks_an_empty_review_artifact` |
| D-04 / D-05 | `tests/test_quality_review_observation.py::test_gateway_parses_all_pages_and_preserves_rename_sources`, `tests/test_quality_review_observation.py::test_review_on_an_artifact_descendant_of_the_last_code_commit_is_current` |
| S-06 | `tests/test_github_templates.py::test_ci_pr_body_entrypoint_strictly_binds_the_observed_review` |
| S-07 / S-12 | `tests/test_quality_review_observation.py::test_ci_scope_detector_uses_the_real_no_rename_git_diff`, `tests/test_quality_review_observation.py::test_ci_scope_detector_fails_closed_to_the_full_set_for_an_unreachable_base` |
| S-08 | `tests/test_quality_review_observation.py::test_a_comment_cannot_clear_the_same_reviewers_change_request`, `tests/test_quality_review_observation.py::test_equal_timestamp_review_states_are_order_independent_and_blocking_wins` |
| S-09 | `tests/test_quality_review_observation.py::test_task_artifact_only_scope_is_derived_from_the_diff`, `tests/test_quality_review_observation.py::test_an_artifact_commit_for_another_task_invalidates_the_review` |
| S-10 | `tests/test_quality_review_observation.py::test_gateway_reports_process_and_json_failures`, `tests/test_quality_review_observation.py::test_gateway_requires_the_paginated_commit_tail_to_equal_the_checked_out_head` |
| Review 4823450100 D-01 | `tests/test_quality_review_observation.py::test_local_gateway_derives_the_base_repository_from_the_pr_url`, `tests/test_quality_review_observation.py::test_local_gateway_refuses_a_pull_request_head_mismatch` |
| Review 4823450100 D-02 | `tests/test_quality_pr_ready.py::test_every_committed_evidence_file_has_a_parseable_full_head_sha` |
| Review 4823450100 D-03 | `tests/test_quality_validate_task.py::test_an_unresolved_blocking_disposition_row_still_blocks_readiness`, `tests/test_quality_validate_task.py::test_the_severity_header_skip_does_not_apply_to_a_finding_cell` |
| Review 4823450100 S-01 | `tests/test_quality_review_observation.py::test_a_current_review_cannot_clear_an_undismissed_earlier_change_request`, `tests/test_quality_review_observation.py::test_an_explicitly_dismissed_change_request_no_longer_blocks_a_current_review` |
| Review 4823450100 S-02 | `tests/test_quality_review_observation.py::test_ci_scope_detector_uses_the_real_no_rename_git_diff` |
| Review 4823450100 S-03 | `tests/test_github_templates.py::test_real_pr_body_validation_forwards_strict_review_observation` |
| Review 4823450100 S-04 / S-05 / S-06 | `tests/test_quality_review_observation.py::test_a_pull_request_with_only_task_artifact_commits_cannot_self_certify`, `tests/test_quality_review_observation.py::test_equal_timestamp_review_states_are_order_independent_and_blocking_wins`, `tests/test_quality_review_observation.py::test_local_gateway_refuses_a_pull_request_head_mismatch` |
| Review 4823450100 S-07 | `tests/test_quality_validate_task.py::test_a_short_resolved_blocking_finding_row_is_invalid` |
| Review 4828407030 D-01 | `tests/test_quality_review_observation.py::test_a_change_request_orphaned_by_a_rebase_still_blocks`, `tests/test_quality_review_observation.py::test_a_dismissed_change_request_orphaned_by_a_rebase_no_longer_blocks`, `tests/test_quality_review_observation.py::test_the_same_reviewers_later_approval_clears_their_change_request` |
| Review 4828407030 D-02 | `tests/test_quality_review_observation.py::test_the_requested_gh_pr_view_fields_exist_in_the_installed_cli` |
| Review 4828407030 D-03 | `tests/test_quality_validate_task.py::test_markdown_emphasis_cannot_hide_an_unresolved_blocking_finding`, `tests/test_quality_validate_task.py::test_only_the_first_row_of_a_review_table_is_treated_as_its_header` |
| Review 4828407030 S-01 | `tests/test_quality_pr_ready.py::test_cli_forwards_the_discovered_task_and_rejected_observation_to_readiness`, `tests/test_github_templates.py::test_ci_pr_body_entrypoint_strictly_binds_the_observed_review` |
| Review 4828407030 S-02 | `tests/test_quality_review_observation.py::test_task_id_from_pr_body_requires_one_non_template_task`, `tests/test_quality_review_observation.py::test_templates_are_never_artifact_only_even_for_a_template_task_id` |
| Review 4828407030 S-03 | `tests/test_quality_validate_task.py::test_an_open_note_remains_non_blocking` |
| Review 4828407030 Notes | `tests/test_quality_hooks.py::test_review_artifact_decision_blocks_every_malformed_review_code`, `tests/test_quality_review_observation.py::test_ci_scope_detector_treats_an_empty_diff_as_full_scope`, `tests/test_quality_review_observation.py::test_local_gateway_rejects_a_malformed_pull_request_url`, `tests/test_quality_review_observation.py::test_same_account_comment_is_observed_but_independence_is_not_verified` |
