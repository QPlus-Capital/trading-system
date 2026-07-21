# Issue 65: test design, properties, and mutation testing

## Problem

The repository has no executable test-design matrices, reusable semantic property helpers, or
mutation ratchet for the pure code guarding live risk and reported research results.

## Goal

Add deterministic property tests and a focused Linux mutation gate on top of the issue-64 task,
impact, readiness, classifier, and finding-registry foundation.

## Non-goals

- Changes to trading, research methodology, live account state, or reported research numbers.
- Claude skills, subagents, hooks, templates, security scanners, or CI restructuring beyond the
  dedicated mutation job and deterministic property replay.
- Whole-repository mutation testing or native-Windows mutation execution.

## Behavioural requirements

- Store mutation policy, baseline, and current results as TOML read by stdlib `tomllib`.
- Reuse `classify.py` for changed paths and R3 classification; add no second matcher.
- Each generic helper must reject a concrete counterexample, not merely assert source text.
- Valid-domain Hypothesis strategies must emit finite and internally consistent values.
- Run Mutmut 3.5.0 only on Linux/Python 3.13 and fail native Windows with an actionable message.
- Block on new survivors, unhealthy outcomes, score regression, or unexplained baseline changes.

## Acceptance criteria

- AC-01: Every reusable helper has a passing use and a violating input that raises.
- AC-02: Deterministic properties cover live risk, position sizing, drawdown, parameter schedules,
  continuous window/gap attribution, regression comparison, and risk classification, and CI runs
  the property module twice with seed 20260721.
- AC-03: `mutation-critical` runs the eight focused critical targets, writes a TOML result, and
  rejects the extra survivor produced by a deliberately weakened-test result.
- AC-04: Hypothesis is locked as a dev dependency, Linux mutation execution is documented, the
  normal Windows gates remain green, and the branch remains unmerged.

## Invariants

- INV-01: `scripts/quality/classify.py` remains the only risk matcher and changed-range algorithm.
- INV-02: Mutation never expands beyond configured pure critical modules and never touches a live
  runner, account, order, or position.
- INV-03: A stronger risk limit never admits a case blocked by a weaker limit.
- INV-04: Property and mutation infrastructure does not change any production trading calculation
  or current research result.

## Assumptions

- Ubuntu can install the locked environment while omitting the Windows-only MetaTrader5 wheel.
- Mutmut 3.5.0's `name: status` output and Python 3.13 support remain stable at the pinned version.

## Open questions

None.

## Expected artifacts

- Testing guide, reusable assertions/strategies, deterministic properties, and their tests.
- TOML mutation policy/baseline, Linux orchestrator/job, two just recipes, and CI result artifact.
- This five-file task record, locked Hypothesis dependency, architecture map, and PR evidence.

## Risk class

R3 — `pyproject.toml`, `justfile`, CI, and gates guarding live-money/result-integrity paths change.

## Human decisions required

- Claude performs the independent PR review.
- Jan decides whether and when to merge; no automation in this change merges the PR.
