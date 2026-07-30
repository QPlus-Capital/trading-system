# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_board.py::test_move_out_of_ready_removes_approved_before_status_change` | RED: focused pre-fix run failed; `move` retained `approved`, then the first fix incorrectly blessed the build-start edge | GREEN: permitted demotions remove first; the separately named `test_move_cannot_reach_implementing_without_the_start_guard` proves the reserved build-start refusal |
| AC-02 | `tests/test_quality_board.py::test_start_refuses_after_demoting_an_approved_card` | RED: stale permit survived the round trip and `start` did not raise | GREEN: the returned card is unarmed and `start` refuses |
| AC-03 | `tests/test_quality_board.py::test_withdraw_removes_approved_without_moving_card` | RED: `BoardService.withdraw` did not exist | GREEN: permit removed with status unchanged |
| AC-04 | `tests/test_quality_board.py::test_withdrawn_ready_card_can_run_full_arm_sequence` | RED: `BoardService.withdraw` did not exist | GREEN: all four approval writes run, the status step is explicitly proven to be a no-op, and `approved` is last |
| AC-05 | `tests/test_quality_board.py::test_every_permit_removal_is_verified_by_rereading_state` | RED: `move` did not remove, `start` used a generic error, and `withdraw` did not exist | GREEN: move/start/withdraw refuse a sticky label; one-shot hooks exercise concurrent state changes; three sticky-write tests exercise every lost-write read-back |
| AC-06 | `tests/test_quality_board.py::test_move_refuses_before_status_change_when_permit_removal_does_not_stick` | RED: move reported success and changed status | GREEN: refusal occurs before the status write |
| AC-07 | `tests/test_quality_board.py::test_start_refusal_names_observed_backlog_status` | RED: generic requirement sentence omitted `Backlog` | GREEN: observed `Backlog` is named |
| AC-08 | `tests/test_quality_board.py::test_start_refusal_names_only_missing_permit_when_ready` | RED: generic sentence also suggested valid conditions were wrong | GREEN: exact message names only absent `approved` |
| AC-09 | `tests/test_quality_board.py::test_start_refusal_names_both_observed_risk_labels` | RED: neither observed label was reported; review separately found the zero-label boundary unpinned | GREEN: both observed labels are reported exactly; `test_start_refuses_a_card_without_any_risk_label` pins the complementary empty boundary |
| AC-10 | `tests/test_quality_board.py::test_start_refusal_reports_every_observed_failure` | RED: start stopped at one generic sentence | GREEN: start, arm, and approval-write failures aggregate every mismatch |
| AC-11 | `tests/test_quality_board.py::test_arm_and_approval_write_refusals_name_observed_status` | RED: both messages named only the required status | GREEN: each exact message names the observed status |
| AC-12 | `tests/test_quality_board.py::test_refusals_report_a_card_absent_from_project` | RED: absence was reported as a generic wrong-status condition and `move` used a separate caller-derived message | GREEN: all five state-dependent operations use the observed-absence vocabulary |
| AC-13 | `tests/test_quality_board.py::test_refusal_messages_contain_only_observed_state_values` | RED: generic requirements substituted unobserved values | GREEN: exact message contains only the fixture's observed status and labels |
| INV-01 | `tests/test_quality_board.py::test_no_board_operation_path_reaches_armed_ready_without_arm` | RED: `Specifying -> Ready to Implement` carried a stale permit; review found 13 of 14 edge iterations asserted nothing | GREEN: every generic edge asserts an unarmed result, the build-start edge asserts refusal, and only explicit arm is armed |
| INV-02 | `tests/test_quality_board.py::test_only_arm_can_add_approved` | RED: the required withdrawal operation did not exist | GREEN: every public operation except arm is exercised and none adds the label; refused internal approval writes also prove zero permit writes |
| INV-03 | `tests/test_quality_board.py::test_start_guard_condition_set_is_unchanged` | Existing focused cases passed before implementation but did not prove the complete condition set | GREEN: all 448 contract-status/label combinations distinguish exact risk labels from lookalikes and match the pre-registered Start predicate; ordering remains pinned separately |
| INV-04 | `tests/test_quality_board.py::test_raw_gh_stderr_is_not_echoed_in_board_error` | RED: raw `gh` stderr exposed a synthetic token-bearing URL | GREEN: state, body-validation, interleaving, and external-stderr surfaces all suppress sensitive inputs |

The original final test file run against `origin/main` was
`uv run pytest -q tests/test_quality_board.py` from commit `a91eed6` against production
`origin/main`: **27 failed, 8 passed**. The review-remediation
counterexamples were then run against commit `1c0b10b` with
`uv run pytest -q tests/test_quality_board.py tests/test_finding_registry_split.py`: **7 failed,
49 passed**. Nine additional round-one tests closed coverage gaps on unchanged behavior rather than
reproducing a defect; the independent review verified that each killed at least one mutant. The
focused green counts are recorded in `evidence.md`.
