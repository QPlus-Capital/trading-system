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

## Round-two findings

Claude completed review
[4826969384](https://github.com/QPlus-Capital/trading-system/pull/145#pullrequestreview-4826969384)
against `3448fbc`. The dispositions below implement Jan's explicit scope; a new complete
independent review remains required.

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| D-01 | Defect | Four confirmed prior findings had no permanent registry entries | Added one generalized, content-addressed entry for each prior D-01/S-01/S-02/S-03 finding, including root cause, missed oracle, executable regression, and workflow response | resolved |
| S-01 | Suspected defect | AC-04 used four historical literals instead of the future-action property | The guard now evaluates sentences containing `these settings` against the specified future-action forms; all ten measured counterexamples are committed as a parametrized negative table | resolved |
| N-01 | Note | Any `strategy` was misreported as a matrix while reusable-workflow jobs were accepted | Only `strategy.matrix` is refused, non-matrix strategy options are accepted, and `uses` jobs fail closed because their inner job changes the emitted context | resolved |
| N-02 | Note | Renaming the closing heading silently widened section parsing to end-of-file | The section extractor now requires exactly one opening and closing heading; a renamed closing heading is a committed negative case | resolved |
| N-03 | Note | The bare `Codex` phrase guard was satisfied by an unrelated sentence | Replaced it with the complete merge-authority clause `Codex, and hooks never merge` | resolved |
| N-04 | Note | The previous regex rejected unrelated prose containing `applies` | Removed that broad token; the replacement inspects only sentences containing `these settings` and concrete future-action forms | resolved |
| N-05 | Note | Exact equality also classifies every workflow job as a required context | Kept deliberately: it fails closed and prevents an unclassified gating job; changing the policy needs its own approved contract decision | deferred |
| N-06 | Note | Impact analysis still claimed the deleted local specification file | Corrected the artifact description; the approved issue is explicitly the sole specification | resolved |
| N-07 | Note | Conditional required-check enforcement remains outside this issue | Unchanged as directed; issue #146 owns that guard | deferred |

The finding registry entries generalize the four confirmed defect classes rather than restating
the individual changed lines. No workflow, ruleset, production path, threshold, or baseline changed.
