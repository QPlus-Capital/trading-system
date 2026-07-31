# Adversarial review

## Findings

Claude's second independent review is
[4823450100](https://github.com/QPlus-Capital/trading-system/pull/143#pullrequestreview-4823450100).
The builder completed the remediations below; a complete independent re-review of the new head is
still required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | Local `gh pr view` requested a nonexistent field and its double accepted an invented payload. | Request `number,headRefOid,url`, derive the base repository from the URL, and assert the exact module-owned argv. | resolved |
| D-02 | Defect | Task 134's evidence HEAD was not parseable by readiness. | Record a bare full SHA and parse every committed non-template evidence file with the production reader. | resolved |
| D-03 | Defect | Blocking disposition rows outside Findings escaped enforcement. | Scan the whole review document and bind the header exception to the ID/Severity columns. | resolved |
| S-01 | Suspected defect | A new commit window erased an older undismissed change request. | Preserve blocking reviewer state across commit windows until GitHub reports dismissal; freshness only proves current review activity exists. | resolved |
| S-02 | Suspected defect | The no-rename test did not distinguish the flag. | Rename a content-preserving production file into the task namespace and require full CI. | resolved |
| S-03 | Suspected defect | Strict observation forwarding was tested by replacing the next production frame. | Execute real PR-body validation under permissive and strict observation modes. | resolved |
| S-04 | Suspected defect | Artifact-only pull-request history was unassigned. | Assert that it cannot self-certify even with an approval. | resolved |
| S-05 | Suspected defect | Equal-time approval versus change request was unassigned. | Execute both API orders and keep the change request blocking. | resolved |
| S-06 | Suspected defect | Local pull-request head mismatch was unassigned. | Drive the local `gh pr view` path with a mismatched `headRefOid`. | resolved |
| S-07 | Suspected defect | The malformed resolved-row branch had lost its regression. | Restore the four-column blocking-row counterexample. | resolved |

## Dispositions

- Jan decided S-01 must follow GitHub: an undismissed `CHANGES_REQUESTED` remains blocking across
  commit windows and is cleared only by explicit dismissal.
- D-01 through D-03 and S-01 through S-07 have executable regressions in the task test plan.
- Complete independent re-review remains pending; the builder has not reviewed its own fix.
