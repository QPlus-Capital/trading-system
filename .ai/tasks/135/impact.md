# Impact analysis

## Direct impact

- `docs/engineering/branch-protection.md` becomes a current audit description of the active
  ruleset: its name, deletion and force-push restrictions, pull-request parameters, merge method,
  non-strict status policy, and four required contexts.
- `tests/test_engineering_workflow_docs.py` stops pinning retired contexts and instead checks that
  the documented contexts are exactly the four approved names and are producible by current
  workflow jobs.
- `.ai/tasks/135/` records the R3 specification, traceability, evidence, and independent-review
  disposition.

## Transitive impact

- Operators auditing GitHub configuration against the repository will no longer be directed to
  create a second ruleset or require contexts that no workflow can report.
- The documented zero-review setting continues to leave merge authority with Jan; it only avoids
  an impossible same-account self-approval requirement.
- The documented non-strict check policy avoids invalidating every other open pull request after
  one branch merges, while all four required contexts must still report for the reviewed head.

## Critical dependencies

- The live GitHub ruleset API response is the source for server-side parameters.
- `.github/workflows/ci.yml` defines `platform-quality` and `full-quality`.
- `.github/workflows/mutation.yml` defines `critical-change-filter` and `mutation-critical`.
- `tests/test_engineering_workflow_docs.py` is the existing executable consumer of the page's
  required-context list.
- The closing rollout warning is the governance control that requires future job renames and the
  external ruleset to move together.

## Unknown or dynamic edges

- GitHub server-side configuration cannot be enforced by repository code. It is read before and
  after the change and compared without mutation.
- No GitHub API comparison is added to CI by this issue, so future external drift remains a
  separate guard opportunity.
- Linux execution is not needed to establish the content correction locally; any unobserved
  platform parity remains explicitly deferred until a ready-state run.
