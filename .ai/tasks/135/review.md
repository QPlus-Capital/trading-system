# Independent review

## Findings

Claude completed review
[4825906480](https://github.com/QPlus-Capital/trading-system/pull/145#pullrequestreview-4825906480)
against `e5b769e`. The builder resolved every finding below; a complete independent re-review of
the resulting head remains required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | INV-03's closing warning could be deleted while the test plan claimed it was guarded | The existing documentation test now requires both `renamed required check must be` and `same rollout window`; the INV-03 test-plan mapping names that executable assertion | resolved |
| S-01 | Suspected defect | AC-05 compared workflow job keys rather than effective status-context names and allowed matrices | Effective contexts resolve `job.name` with a key fallback, matrices are refused because they suffix contexts, and the exact documented/workflow sets must be equal | resolved |
| S-02 | Suspected defect | The forbidden local `spec.md` re-scoped the approved issue contract | Deleted `.ai/tasks/135/spec.md`; Jan corrected the authoritative issue body and issue #146 owns the separate mechanical unknown-artifact guard | resolved |
| S-03 | Suspected defect | Squash-only merging was used as a reason but was not listed as a setting to configure | Added the explicit setting `Set allowed merge methods to squash only` and bound it in the existing documentation test | resolved |
| N-01 | Note | Bypass actors, Active enforcement, and code-owner-review policy were unguarded | Added all three applied settings to the existing phrase guard | resolved |
| N-02 | Note | The future-action guard rejected only one historical sentence | Replaced it with a case-insensitive regex covering `will apply`, `applies`, `after this workflow lands`, and `later configures` | resolved |
| N-03 | Note | Required-context bullets were scraped document-wide | Restricted parsing to `Required status checks`, required its exact-context lead-in, and stopped unrelated bullets from becoming contexts | resolved |

## Dispositions

No finding was rejected, deferred, or used to widen production, workflow, ruleset, path-filter, or
baseline scope. The issue-body correction authorizes only the stale existing documentation-test
update. The ruleset and workflow files are unchanged. The separate ruleset/API and `paths-ignore`
guards remain assigned to issue #146.

The pull request remains draft. It cannot become ready until Claude completes the required
whole-change re-review of the material remediation.
