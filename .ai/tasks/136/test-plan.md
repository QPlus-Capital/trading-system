# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_board.py::test_move_out_of_ready_removes_approved_before_status_change` | RED: focused pre-fix run failed; `move` retained `approved` | GREEN: all three destinations pass in the 35-test Board suite |
| AC-02 | `tests/test_quality_board.py::test_start_refuses_after_demoting_an_approved_card` | RED: stale permit survived the round trip and `start` did not raise | GREEN: the returned card is unarmed and `start` refuses |
| AC-03 | `tests/test_quality_board.py::test_withdraw_removes_approved_without_moving_card` | RED: `BoardService.withdraw` did not exist | GREEN: permit removed with status unchanged |
| AC-04 | `tests/test_quality_board.py::test_withdrawn_ready_card_can_run_full_arm_sequence` | RED: `BoardService.withdraw` did not exist | GREEN: all four approval writes run and `approved` is last |
| AC-05 | `tests/test_quality_board.py::test_every_permit_removal_is_verified_by_rereading_state` | RED: `move` did not remove, `start` used a generic error, and `withdraw` did not exist | GREEN: move/start/withdraw all refuse a sticky label |
| AC-06 | `tests/test_quality_board.py::test_move_refuses_before_status_change_when_permit_removal_does_not_stick` | RED: move reported success and changed status | GREEN: refusal occurs before the status write |
| AC-07 | `tests/test_quality_board.py::test_start_refusal_names_observed_backlog_status` | RED: generic requirement sentence omitted `Backlog` | GREEN: observed `Backlog` is named |
| AC-08 | `tests/test_quality_board.py::test_start_refusal_names_only_missing_permit_when_ready` | RED: generic sentence also suggested valid conditions were wrong | GREEN: exact message names only absent `approved` |
| AC-09 | `tests/test_quality_board.py::test_start_refusal_names_both_observed_risk_labels` | RED: neither observed label was reported | GREEN: both labels are sorted and named |
| AC-10 | `tests/test_quality_board.py::test_start_refusal_reports_every_observed_failure` | RED: start stopped at one generic sentence | GREEN: start, arm, and approval-write failures aggregate every mismatch |
| AC-11 | `tests/test_quality_board.py::test_arm_and_approval_write_refusals_name_observed_status` | RED: both messages named only the required status | GREEN: each exact message names the observed status |
| AC-12 | `tests/test_quality_board.py::test_refusals_report_a_card_absent_from_project` | RED: absence was reported as a generic wrong-status condition | GREEN: all four state-dependent operations report absence |
| AC-13 | `tests/test_quality_board.py::test_refusal_messages_contain_only_observed_state_values` | RED: generic requirements substituted unobserved values | GREEN: exact message contains only the fixture's observed status and labels |
| INV-01 | `tests/test_quality_board.py::test_no_board_operation_path_reaches_armed_ready_without_arm` | RED: `Specifying -> Ready to Implement` carried a stale permit | GREEN: every contract edge is unarmed; only the explicit arm case is armed |
| INV-02 | `tests/test_quality_board.py::test_only_arm_can_add_approved` | RED: the required withdrawal operation did not exist | GREEN: every public operation except arm is exercised and none adds the label |
| INV-03 | `tests/test_quality_board.py::test_start_moves_before_removing_permit_and_preserves_it_on_failure` | Existing guard passed before implementation | GREEN: unchanged ordering guard passes |
| INV-04 | `tests/test_quality_board.py::test_refusal_messages_do_not_expose_sensitive_values` | RED: the message omitted the required observed status | GREEN: observed status is present while URL, account-like number, and token stay absent |

The exact red-first command was `uv run pytest -q tests/test_quality_board.py`: **24 failed,
9 passed**. The focused green Board run is **35 passed**; Board plus split-registry integration is
**39 passed**.
