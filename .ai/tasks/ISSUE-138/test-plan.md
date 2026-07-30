# Test plan

## Traceability

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_command_query_count_is_independent_of_project_size` | RED: `item-list --limit 1000` incurs more fake GraphQL pages for the large project | GREEN: both sizes use one issue-scoped GraphQL query |
| AC-02 | `test_status_uses_one_graphql_query` | RED: status uses project view, field list, issue view, and whole-project item list | GREEN: status uses one combined snapshot query |
| AC-03 | `test_project_metadata_is_loaded_once_across_state_reads` | RED: every status read reloads project view and fields | GREEN: metadata is included once and omitted from later fresh state reads |
| AC-04 | `test_rate_limit_error_has_type_reset_time_and_distinct_cli_result` | RED: exhaustion becomes a generic `BoardError` without reset time and exits like a state refusal | GREEN: `BoardRateLimitError` carries reset time and the CLI emits its distinct refusal/exit |
| AC-05 | `test_rate_limit_after_a_write_reports_only_confirmed_steps` | RED: an interrupted sequence loses which write already returned successfully | GREEN: the exception names confirmed steps and the CLI never reports success |
| AC-06 | `test_rate_limit_is_never_retried` | RED: no explicit no-retry contract exists | GREEN: the first rate-limit response ends the command with no later gateway call |
| AC-07 | `test_absent_issue_uses_one_query_and_returns_no_status` | RED: absence requires scanning every project item | GREEN: an empty issue-scoped project-item connection returns `status=None` |
| INV-01 | `test_each_guard_decision_uses_a_fresh_issue_query` | RED: no query-level proof distinguishes state caching from metadata caching | GREEN: each guard/verification read increments the issue snapshot count |
| INV-02 | `test_arm_and_start_keep_all_verification_reads` | RED: existing tests assert writes but not the three state reads in each sequence | GREEN: both commands retain their initial, intermediate, and final reads |
| INV-03 | `test_rate_limit_and_state_refusals_do_not_expose_secrets` | RED: no rate-limit-specific output contract exists | GREEN: neither refusal contains token, account number, or credential-bearing URL |

Additional fail-closed defense: `test_incomplete_issue_project_membership_refuses_without_retry`
proves that a truncated issue-level project connection cannot be mistaken for board absence and
cannot trigger pagination or retry after the one bounded query.

## Red-first procedure

1. Add the counting `gh` fake and all named AC/INV tests against unchanged `board.py`.
2. Run `uv run pytest -q tests/test_quality_board.py` and record the exact failures.
3. Commit the red-only contract without pushing it.
4. Implement the smallest gateway/service/CLI change, then rerun the same file green.

## R3 gates

- `just check-fast origin/main`
- `just check`
- `just check-properties`
- `just check-invariants`
- `just check-security`
- `just impact origin/main`
- `validate_task --task-id ISSUE-138`
- Linux critical mutation where the production policy selects a configured target; otherwise
  execute the authoritative selector and record the exact empty target set without a mutation claim
- independent adversarial and live-money review
- `pr-ready ISSUE-138`; never merge autonomously

## Safety

Tests replace every `gh` subprocess with an in-memory fake. No live trade, MT5 terminal, runner,
order, account, project mutation, issue mutation, retry loop, or persistent cache is exercised.
