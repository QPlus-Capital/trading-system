# Issue 67: Templates, CI split, security, and finding loop

## Problem

Repository governance lacks evidence-bound contribution templates, independently visible CI gates,
an effective security gate, and durable reviewer/session operating policies.

## Goal

Make every contribution path produce verifiable task evidence, run the same named gates locally and
in CI, block secrets and vulnerable or security-significant code, and document the final review loop.

## Non-goals

- Trading, research, monitoring, risk, account, or live-runner behaviour.
- Applying GitHub branch protection through an API; Jan applies the documented settings.
- Adding a second risk classifier, task validator, impact engine, readiness implementation, or
  mutation implementation.

## Behavioural requirements

- Provide Markdown issue and pull-request templates that request every field in issue #67.
- Validate a PR body against its task artifact and current successful readiness evidence.
- Expose distinct Standard Quality, Tests, Task-Artifact Validation, Security, Critical Invariants,
  Mutation-Critical, and PR-Evidence Validation checks, each backed by a local `just` recipe.
- Run the complete CI split for every R3 change and cancel superseded runs.
- Scan tracked content for secrets, audit dependencies, and run static security analysis using
  Python 3.13-compatible, cross-platform tools configured through TOML.
- Preserve confirmed findings as registry entries plus regression tests and use artifacts rather
  than chat history as the session audit trail.

## Acceptance criteria

- AC-01: All issue and PR templates render, and PR-body validation rejects missing or
  evidence-unbacked claims.
- AC-02: Distinct CI jobs invoke matching local `just` recipes, pinned actions and concurrency
  cancellation are enforced, and R3 changes cannot skip the complete split.
- AC-03: `just check-security` blocks a synthetic fake secret, passes clean content, audits locked
  dependencies, runs static analysis, and is the Security job's sole gate entry point.
- AC-04: Readiness self-tests prove unresolved P1/P2 block, P3 does not, R3 paths require critical
  gates, and missing, failed, or stale evidence blocks.
- AC-05: Branch protection, reviewer findings, and session policy are documented and `just check`
  remains green.

## Invariants

- INV-01: `scripts/quality/classify.py` remains the only changed-path risk matcher.
- INV-02: CI contains no quality decision unavailable through a local `just` recipe.
- INV-03: New tests use temporary files/repositories, require no network, and never initialize or
  interact with MT5 or a live account.
- INV-04: An R3 path triggers every full-validation workflow, including Linux mutation-critical.
- INV-05: Security failures disclose file paths and detector names only, never secret values or
  file contents.

## Assumptions

- GitHub Actions workflows and the required Markdown issue-template frontmatter use GitHub's native
  YAML formats; repository-owned policy configuration remains TOML parsed with stdlib `tomllib`.
- GitHub-hosted Windows and Ubuntu runners provide Python 3.13 through `setup-uv`.

## Open questions

None.

## Expected artifacts

- `.github` issue/PR templates and split pinned workflows.
- PR-body and security quality modules, TOML policy, local recipes, and behavioural tests.
- Branch-protection, reviewer-findings, session-policy, testing, and architecture documentation.
- This five-file task artifact and a ready-for-review pull request.

## Risk class

R3 — CI, gate commands, dependency pins, and governance paths control every repository change.

## Human decisions required

- Jan applies the documented branch-protection settings and retains merge authority.
- Codex performs the independent review; R3 never merges autonomously.
