# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_review_observation.py::test_a_code_commit_after_every_review_makes_the_review_stale` | RED: review observation module absent | GREEN: a later code/test commit rejects every earlier review |
| AC-02 | `tests/test_quality_review_observation.py::test_review_verdict_comes_from_the_latest_review_after_the_last_code_commit` | RED: review observation module absent | GREEN: a later non-blocking PR review verifies independently of the audit Markdown |
| AC-03 | `tests/test_quality_validate_task.py::test_old_review_phrase_without_an_observed_pr_review_fails` | RED: validator trusted the phrase | GREEN: the phrase cannot substitute for a rejected PR observation |
| AC-04 | `tests/test_quality_validate_task.py::test_review_markdown_shape_is_not_a_gate_input` | RED: validator parsed exact Markdown | GREEN: alternate headings, bold text, and arbitrary tables do not affect the verdict |
| AC-05 | `tests/test_quality_pr_ready.py::test_task_validator_and_pr_readiness_apply_the_same_review_verdict` | RED: no shared verdict existed | GREEN: all three observation states agree under strict enforcement |
| AC-06 | `tests/test_quality_pr_ready.py::test_review_and_evidence_commits_may_follow_the_tested_head` | RED: review.md invalidated evidence | GREEN: only review.md and evidence.md may follow the tested commit |
| AC-07 | `tests/test_ci_cost_workflows.py::test_task_artifact_only_diff_selects_the_reduced_linux_gate_set` | RED: ready synchronizations always ran the full Linux set | GREEN: synchronize-event delta selects two light Linux gates; code/test deltas select all gates |
| INV-01 | `tests/test_quality_review_observation.py::test_a_code_commit_after_every_review_makes_the_review_stale` | RED: self-reported review could remain current | GREEN: no review predating the last non-artifact commit verifies |
| INV-02 | `tests/test_quality_review_observation.py::test_reduced_ci_requires_a_task_only_synchronize_event` | RED: no synchronize-diff predicate existed | GREEN: only the actual task-only push delta selects reduced CI |
| INV-03 | `tests/test_ci_cost_workflows.py::test_full_job_invokes_every_existing_gate_as_a_distinct_step` | RED: reduced path was not represented | GREEN: every existing named gate remains a distinct workflow step |
