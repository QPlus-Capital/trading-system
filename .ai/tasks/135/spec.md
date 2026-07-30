# Issue 135: Synchronize the branch-protection audit reference

## Problem

`docs/engineering/branch-protection.md` records a pre-consolidation design rather than the active
GitHub ruleset. It names seven retired status contexts and seven pull-request or ruleset settings
that differ from the applied configuration.

## Goal

Make the page an accurate audit reference for the active `main` ruleset and the CI jobs that can
produce its four required contexts.

## Acceptance criteria

- AC-01: The page names exactly `platform-quality`, `full-quality`,
  `critical-change-filter`, and `mutation-critical` as required contexts.
- AC-02: Every described pull-request and ruleset parameter matches the live API response.
- AC-03: Zero required approvals explains the single-account self-approval limitation, and
  non-strict status checks explain the avoided rebase and rerun cost.
- AC-04: The page records that the configuration was applied on 2026-07-30 and contains no future
  application instruction.
- AC-05: Every required context named by the page exists as a job in the current CI workflows.

## Invariants

- INV-01: No GitHub ruleset rule, parameter, bypass actor, or required context is changed.
- INV-02: No credential, token, account number, ruleset identifier, or account login is committed.
- INV-03: The warning requiring documentation and GitHub to move together after a check rename
  remains on the page.

## Scope

- Correct `docs/engineering/branch-protection.md`.
- Update only the stale assertions in the existing engineering-workflow documentation test.
- Add the required R3 task artifacts.

## Non-goals

- No production, workflow, ruleset, threshold, target, or baseline change.
- No new test that calls the GitHub API.
- No autonomous merge or ready-for-review transition.

## Risk class

R3. The authoritative path classifier assigns `docs/engineering/**` to R3 because these documents
define governance that protects live-money and result-integrity changes.

## Human decisions required

None. Jan approved issue #135 with no open decisions.
