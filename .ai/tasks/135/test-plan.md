# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `test_branch_protection_names_every_required_check_and_setting` exact documented context set | RED: the page exposed seven retired, workflow-prefixed contexts | GREEN: the page exposes exactly the four live contexts |
| AC-02 | Live ruleset API statement-by-statement comparison | RED: ruleset name, approval count, stale/last-push approval, linear-history, merge-method, and strict-check statements differed | GREEN: every described stored parameter matches the API response |
| AC-03 | Existing documentation test checks both deliberate values and their reasons | RED: one approval and strict checks were presented without the applied rationale | GREEN: zero approvals names the same-account limitation; non-strict checks name rebase and re-run cost |
| AC-04 | Existing documentation test rejects the future-action sentence and requires the application date | RED: `Jan applies these settings` remained | GREEN: applied date is present and the future sentence is absent |
| AC-05 | Existing documentation test compares documented contexts with effective workflow context names | RED: none of the seven documented strings matched a current context | GREEN: the exact four documented contexts equal the effective non-matrix workflow contexts |
| INV-01 | Ruleset API response before/after comparison plus changed-path audit | RED: not applicable to repository content; external state captured before editing | GREEN: API response remains byte-equivalent in all rule parameters and contexts |
| INV-02 | `just check-security` and changed-content inspection | RED: no credential is required for the change | GREEN: no secret, account number, identifier, or login is present |
| INV-03 | `test_branch_protection_names_every_required_check_and_setting` requires both closing-warning clauses | RED: deleting the warning left the existing test green | GREEN: both `renamed required check must be` and `same rollout window` are required |

## Red-first procedure

1. Update the existing audit test to express the active ruleset and current workflow contexts.
2. Run only the named documentation test against the unchanged page and record the failure.
3. Correct the page without changing the ruleset or either workflow.
4. Run the focused test, the complete R3 gate set, and the independent review.
