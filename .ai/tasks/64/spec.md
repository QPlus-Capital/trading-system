# Issue 64: task artifacts, impact analysis, and PR readiness

## Problem

The repository has a risk classifier but no validated task record, conservative changed-file test
map, or composed readiness gate that binds evidence to the tested revision.

## Goal

Add concise task artifacts, conservative impact recommendations, and a fail-closed PR-readiness
summary on top of the existing classifier.

## Non-goals

- Property testing, mutation testing, security scanning, CI splitting, and agent hooks.
- Any trading, research-methodology, live-account, or autonomous-merge change.

## Behavioural requirements

- Store all machine-readable policy as TOML loaded by stdlib `tomllib`.
- Reuse `scripts/quality/classify.py` for path classification and git-range discovery.
- Treat focused impact tests as recommendations; the full suite remains mandatory.
- Keep `just check` unchanged and green.

## Acceptance criteria

- AC-01: Task validation rejects missing sections, unmapped AC/INV IDs, and unresolved P0/P1/P2,
  while accepting a complete task.
- AC-02: Impact analysis surfaces the known tests for `research/engine/continuous.py` and
  `live/risk_control.py`, emits JSON, and states that the full suite remains mandatory.
- AC-03: PR readiness returns non-zero for missing or stale evidence, zero for a clean task, and
  reports cumulative R3 gates.
- AC-04: All new quality tooling classifies as R3, adds no dependency, and passes `just check`.

## Invariants

- INV-01: The implementation contains no second path-risk matcher or git changed-path algorithm.
- INV-02: Impact analysis never claims that its static result is complete or replaces full pytest.
- INV-03: The existing `check` recipe remains byte-for-byte unchanged in command content and order.
- INV-04: Versioned `.ai` artifacts contain concise engineering evidence, never model transcripts or
  chain-of-thought.

## Assumptions

- Git and the repository's `uv`, `just`, and Python toolchain are available.
- A final evidence-only commit is necessary because a committed file cannot contain its own commit
  SHA; any non-evidence change after the recorded SHA makes evidence stale.

## Open questions

None.

## Expected artifacts

- Five reusable templates and this issue's five dogfood artifacts.
- TOML task schema and critical-dependency map.
- Validator, impact analyzer, readiness orchestrator, tests, recipes, docs, and generated test map.

## Risk class

R3 — the change modifies the quality policy and gates that guard result integrity.

## Human decisions required

- Claude performs the independent PR review.
- Jan decides whether and when to merge; the tooling must never merge autonomously.
