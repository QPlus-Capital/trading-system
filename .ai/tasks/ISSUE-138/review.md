# Adversarial review

## Findings

Claude completed independent review
[4827246531](https://github.com/QPlus-Capital/trading-system/pull/144#pullrequestreview-4827246531)
against `e77e8d4`. The builder dispositions below implement Jan's three explicit decisions. A
complete independent re-review of the material remediation remains required.

## Dispositions

| ID | Severity | Disposition | Status |
|---|---|---|---|
| D-01 | Defect | `move` now preserves `BoardRateLimitError` through its inner handler and attaches the already-confirmed permit removal | resolved |
| D-02 | Defect | Both changed Python files were formatted with `ruff format`; the format evidence is rerun rather than inferred | resolved |
| D-03 | Defect | Evidence is rebound to a real material commit, followed only by an evidence-only commit | resolved |
| D-04 | Defect | A detected write exhaustion makes exactly one `gh api rate_limit` lookup for reset time without retrying the failed write | resolved |
| S-01 | Suspected defect | Label pagination is requested and any truncated label connection refuses before a permit decision | resolved |
| S-02 | Suspected defect | Tests pin project id selection, foreign memberships, `first: 20`, `includeArchived: false`, `labels(first: 100)`, owner, and project number | resolved |
| S-03 | Suspected defect | The subprocess-boundary test asserts exactly one failed GraphQL invocation; the reset lookup is separately identified and cannot repeat it | resolved |
| S-04 | Suspected defect | `FakeGateway.rate_limit_on` injects write exhaustion; every progress handler and every `arm` step is exercised | resolved |
| S-05 | Suspected defect | A stateful subprocess fake drives `add`, `arm`, `move`, and `start` through the real gateway and pins each exact command sequence | resolved |
| N-01 | Note | Restored `_remove_approved_and_verify` as the sole verified permit-removal path for `move`, `withdraw`, and `start` | resolved |
| N-02 | Note | Removed the unreachable standalone project query; mutations require metadata loaded by a fresh issue snapshot | resolved |
| N-03 | Note | Documented exit code `3` and that it is not a retry signal | resolved |
| N-04 | Note | `--owner` remains public, and its failure now states that it must name a GitHub organization | resolved |
| N-05 | Note | An interrupted `start` explicitly reports that approved removal is unconfirmed | resolved |
| N-06 | Note | Corrected the historical red count and the two invariant rows that were green before implementation | resolved |
| N-07 | Note | Evidence now distinguishes fake API-call counts from the separate live GraphQL-point observation | resolved |
| N-08 | Note | `IssueState.on_project` distinguishes an existing item with unset Status from board absence | resolved |

No retry, backoff, persistent cache, workflow-contract fact, permit ordering, or live-money path was
added or changed. The pull request remains draft pending the complete independent re-review.
