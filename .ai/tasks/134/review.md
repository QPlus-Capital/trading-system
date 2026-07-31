# Adversarial review

## Findings

Claude's third independent review is
[4828407030](https://github.com/QPlus-Capital/trading-system/pull/143#pullrequestreview-4828407030).
The builder completed the remediations below; a complete independent re-review of the new material
head is still required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | A rebase discarded an undismissed change request before reviewer-state reduction. | Reduce all non-dismissed reviews per reviewer; use only current reviews for freshness. A later approval supersedes that reviewer's request, while a comment does not. | resolved |
| D-02 | Defect | The `gh pr view` argument test compared the production constant with itself. | Probe the installed CLI's offline field list and require every production field to exist. | resolved |
| D-03 | Defect | Markdown emphasis hid blocking severities, and the header exception was content-based rather than positional. | Normalize backticks, asterisks, and underscores before matching; accept a header only as the first row of its table. | resolved |
| S-01 | Suspected defect | The two production entrypoints could drop the task id or observed verdict without a failing test. | Drive the real readiness frame with a rejected observation and assert both entrypoints forward task id and verdict. | resolved |
| S-02 | Suspected defect | Task-id extraction and both `_templates` exclusions were unassigned outcomes. | Parameterize empty, ambiguous, template, and valid PR bodies and assert templates never qualify as task-only scope. | resolved |
| S-03 | Suspected defect | No test protected the non-blocking `Note` half of the severity partition. | Prove an open Note remains non-blocking at R2 and R3. | resolved |
| N-01 | Note | Evidence and impact stated opposite approval semantics. | Align both artifacts with GitHub's latest-decisive-state rule. | resolved |
| N-02 | Note | The pre-Bash review-code set omitted malformed-row and malformed-severity findings. | Add both codes and bind them at R2 and R3. | resolved |
| N-03 | Note | Three registry records claimed protection broader than their regressions. | Make the external-interface and template claims executable; replace the state-reduction record with content matching Jan's approval decision. | resolved |
| N-04 | Note | The timestamp buckets and special-state branches had no remaining verdict effect. | Replace them with one explicit latest-decisive reduction ordered by server review id. | resolved |
| N-05 | Note | Empty-diff and malformed-URL boundaries were unpinned. | Add direct fail-closed regressions for both. | resolved |
| N-06 | Note | A sole current review from the last commit's account could look independently verified. | Keep COMMENTED observable but name that independence is not verified in the output. | resolved |
| N-07 | Note | A registry-migration assertion duplicated the detailed missing-content oracle below it. | Remove the redundant assertion and retain the diagnostic oracle. | resolved |

## Dispositions

- Jan decided that each reviewer's latest non-dismissed decisive state wins: a later `APPROVED`
  clears that reviewer's `CHANGES_REQUESTED`, while `COMMENTED` does not. A dismissed review is
  excluded. Freshness still requires a current review, so an orphaned review cannot verify.
- Jan decided `COMMENTED` remains an observed review. When the only current review and the last
  material commit use the same GitHub account, the verified observation explicitly says that
  independence is not verified; no second-account requirement is introduced by issue #134.
- D-01 through D-03, S-01 through S-03, and N-01 through N-07 have executable regressions in the
  task test plan.
- Complete independent re-review remains pending; the builder has not reviewed its own fix.
