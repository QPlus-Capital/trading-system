# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01, AC-04 | `test_tool_contracts_bind_builder_and_reviewer_to_the_correct_files` | RED: old AGENTS reviewer language lacks `primary builder` | GREEN: swapped markers pass and stale markers are absent |
| AC-02 | `test_role_contracts_preserve_exception_and_human_authority` plus role-language audit | RED: exception and Jan's full authority are absent | GREEN: both contracts and constitution agree |
| AC-03 | `test_claude_runtime_files_match_the_primary_review_role` and runtime schema tests | RED: builder skills are not exception-scoped | GREEN: reviewer path is primary and builder skills are exception-only |
| AC-05 | cumulative R3 gates via `pr-ready` | RED: evidence incomplete before the branch run | GREEN: all local gates and Linux mutation passed |
| INV-01 | parameterized load-bearing rule guard over both contracts | RED: AGENTS lacks multiple inline constraints | GREEN: all immutable markers pass in both contracts |
| INV-02, INV-03 | exception/authority guard over both contracts and constitution | RED: required phrases absent | GREEN: exception and Jan/R3 authority pass |
| INV-04 | changed-path audit and parity/live-money attestations | N/A: scope invariant | GREEN: only governance Markdown, role-only TOML reasons, guard, and task artifact changed |
