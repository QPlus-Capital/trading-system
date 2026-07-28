# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01, INV-01 | `test_fixed_basis_scores_after_cumulative_losses_exceed_the_basis` | RED: `-110` cumulative PnL on basis `100` raises `account exhausted` before the `-20%` later window | GREEN: first window is `-110%`, later window is `-20%`, and all events remain present |
| AC-02 | `test_prior_loss_depth_never_changes_a_later_fixed_basis_score` | RED: exact/below-basis cases raise while `-99.5%` scores | GREEN: prior losses `-99.5%/-100%/-150%` all leave the identical later `+10%` score |
| AC-03, INV-03, INV-04 | source search plus existing attribution/boundary/drawdown tests | RED: exhaustion branch and message exist | GREEN: no viability branch remains; attribution and statistical curves pass |
| AC-04 | targeted real `_run_task` execution for two XAGUSD 36m variations | RED: baseline contains two `account exhausted` error rows | GREEN: both return 21 windows, 24 inner combos, and finite numeric metrics with no error |
| AC-05, INV-05 | zero-tolerance regression plus SHA-256 of both trade CSVs | RED: no ISSUE-58 comparison exists | GREEN: no unexpected changes and both files byte-identical |
| AC-06, INV-06 | local cumulative R3 gates and mutation blocker record | RED: task/evidence absent | GREEN: every runnable gate passes; Linux mutation truthfully blocked |
| INV-02 | Stage-1 swap and candidate artifact suites | RED: not yet verified for this change | GREEN: canonical net stream remains exact |
