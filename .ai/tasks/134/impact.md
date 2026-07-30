# Impact analysis

## Direct impact

- `scripts/quality/review_observation.py` becomes the sole GitHub boundary and commit-identity
  decision for independent review facts. It preserves rename sources and paginates commits,
  commit-file pages, and reviews.
- `scripts/quality/validate_task.py`, `pr_ready.py`, and `pr_body.py` consume the same observed
  verdict for R2 and R3. Markdown in `review.md` no longer certifies that review ran, while its
  required sections and unresolved blocking dispositions remain separately binding.
- `.github/workflows/ci.yml` derives task-artifact-only synchronization from the actual diff and
  skips the expensive Linux test, property, security, and invariant gates only for the current
  task's four schema files. Diff failure selects the full set.
- `AGENTS.md`, `CLAUDE.md`, and the engineering workflow describe reviewer-owned audit records.

## Transitive impact

- `just pr-ready`, `just check-pr-evidence`, task-artifact validation, PR body validation, and the
  required `pr-evidence-validation` check all reach the shared review verdict.
- Evidence currency now permits later changes to both `review.md` and `evidence.md`, while any
  later production, test, workflow, or policy change still invalidates evidence.
- CI cost-contract tests exercise the workflow predicate and preserve every named required gate.
- `docs/architecture.md` gains the new quality-module entry.

## Critical dependencies

- The change is R3 because it changes PR readiness and required CI enforcement. The critical
  dependency is GitHub's pull-request commits and reviews APIs, isolated behind a fakeable gateway.
- `CHANGES_REQUESTED` remains blocking per reviewer; a later comment cannot clear it, equal-time
  events are deterministic, and a dismissed approval cannot verify.
- Required gates, review sections, resolved-status configuration, and severity vocabulary remain
  active and cumulative.

## Unknown or dynamic edges

- GitHub availability, event payload shape, review commit identity, reviewer state, and complete
  commit file enumeration are runtime facts. Malformed reachable data fails closed; an unreachable
  local GitHub boundary is reported as `UNVERIFIABLE` and advisory, while CI requires a verifiable
  result.
- GitHub cannot prove a different human account authored the review when builder and reviewer share
  an account; issue #134 explicitly leaves that limitation out of scope.
