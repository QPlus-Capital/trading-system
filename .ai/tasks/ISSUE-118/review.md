# Adversarial review

## Status

Builder counterexample analysis is recorded below. Independent Claude review is required before
readiness or merge.

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| ISSUE-118-R1 | P1 | Updating only `total` would conceal 29 killed survivors and 53 newly generated survivor names. | Regenerate summary and exact survivor classifications together from the retained report. | resolved |
| ISSUE-118-R2 | P1 | Copying every observed survivor without attribution would silently weaken the ratchet. | Diff survivor identities against the old baseline and admit new exact names only in #96-changed path-risk/sizing functions with explicit meaningful-gap reasons. | resolved |
| ISSUE-118-R3 | P1 | Removing all old survivors would discard valid classifications for 364 still-surviving names. | Preserve existing classifications and reasons only for names still observed. | resolved |
| ISSUE-118-R4 | P1 | Reporting only the improved killed count could hide the lower derived score caused by the expanded surface. | Record old/new counts and derived scores explicitly; change no score check or threshold. | resolved |
| ISSUE-118-R5 | P2 | A Windows-local claim could fabricate mutation evidence because Mutmut requires fork. | Bind evidence to Linux run `30333581031` and record the missing local substitute as a workflow finding. | resolved |
| ISSUE-118-R6 | P2 | Regeneration could accidentally change mutation targets or production/test code. | Assert exact target equality and restrict the diff to the baseline plus task artifacts. | resolved |

## Counterexamples attempted

1. Summary updated without survivor-set reconciliation.
2. Killed survivors left in an existing group.
3. New survivor admitted outside #96/#97/#98-changed modules.
4. New survivor admitted without exact-name classification or reason.
5. Target order changed.
6. Non-zero unhealthy mutation status accepted.
7. Threshold, policy, test selection, production, or open-PR file changed.
8. Windows result represented as Linux mutation evidence.

## Dispositions

All builder findings have executable dispositions. Independent review remains external.
