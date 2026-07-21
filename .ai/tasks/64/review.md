# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P1 | Exact-HEAD evidence creates an impossible self-referential committed SHA | Permit exactly one later evidence-only commit; test that later code makes it stale | resolved |
| R-02 | P2 | A typo in the critical map could silently recommend a nonexistent test | Test every configured recommendation against a real repository path | resolved |
| R-03 | P1 | Repository-wide format checking fails on 42 untouched baseline files | Format-check only changed Python paths obtained from `changed_paths` | resolved |
| R-04 | P2 | Impact JSON changed when the same paths arrived in a different order | Sort normalized unique paths before analysis and test order independence | resolved |
| R-05 | P1 | Readiness accepted required-gate failures and missing gate evidence | Bind every TOML gate ID to evidence; missing or non-zero required gates block | resolved |
| R-06 | P2 | An R3 review could pass without demonstrating adversarial work | Require a finding row or `No findings; N counterexamples attempted` with N >= 1 | resolved |
| R-07 | P3 | The regenerated impact map caused change-set churn in every PR | Ignore the local artifact and document it as unversioned scratch output | resolved |

## Dispositions

All findings are addressed by executable tests or, for artifact versioning, an ignore guard.
Claude's adversarial review attempted the failed-gate, empty-review, and regenerated-artifact
counterexamples recorded as R-05 through R-07. No autonomous merge action is part of this change.
The pre-existing Pandas 4 deprecation warnings remain tracked separately in issue #68.
