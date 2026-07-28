# ISSUE-118: Refresh the critical mutation baseline

## Problem

`.ai/quality/mutation-baseline.toml` still describes the pre-#96/#97/#98 critical mutation surface
(`4,406` mutants), while Linux run `30333581031` on `main@494eafc` measured `4,568` mutants and
proved that 29 formerly allowed survivors are now killed.

## Goal

Regenerate the critical baseline wholesale from the retained Linux result, remove every newly
killed survivor, classify every newly observed survivor by exact name, and preserve the fail-closed
ratchet without changing production code, mutation targets, tests, or thresholds.

## Acceptance criteria

- AC-01: The committed baseline summary exactly matches run `30333581031`: total `4,568`, killed
  `4,151`, survived `417`, and every unhealthy status zero.
- AC-02: Baseline targets exactly match the measured report and the existing mutation policy.
- AC-03: All 29 baseline survivors now measured killed are removed and listed explicitly in
  `evidence.md`.
- AC-04: Every one of the 417 observed survivors has exactly one non-empty exact-name
  classification; no unobserved survivor is admitted.
- AC-05: Every newly classified survivor is attributable to merged #96/#97/#98. The measured delta
  is confined to #96's `research.portfolio.path_risk` and `research.portfolio.sizing` functions;
  #97 and #98 introduce no unexplained survivor.
- AC-06: `scripts.quality.mutation.check_baseline` returns no issues when the retained
  `critical.toml` report is compared with the regenerated baseline.
- AC-07: No mutation target, threshold, test selection, test, production file, research result,
  live path, or open pull request changes.
- AC-08: Every locally executable R3 gate passes. The Linux result is the retained run
  `30333581031`; the workflow finding explains why native Windows had no substitute while the
  organisation's Actions allowance was exhausted.
- AC-09: Delivery uses a separate draft PR; it is not marked ready, merged, or configured for
  auto-merge.

## Invariants

- INV-01: The ratchet remains exact-name and fail-closed: any survivor outside the measured 417
  fails.
- INV-02: The total increases from `4,406` to `4,568`; no configured threshold is relaxed.
- INV-03: All 29 now-killed mutants are removed from allowed survivors, tightening the ratchet.
- INV-04: The derived mutation score is reported honestly even though the expanded code surface
  changes it; no score floor or comparison rule is edited.
- INV-05: `.ai/quality/mutation.toml`, `pyproject.toml`, mutation selection, tests, and production
  code remain byte-unchanged.
- INV-06: No live runner or MT5 terminal is queried, initialized, stopped, or restarted.

## Scope

- `.ai/quality/mutation-baseline.toml`
- `.ai/tasks/ISSUE-118/`

## Non-goals

- Killing or reclassifying surviving mutants beyond the retained Linux measurement.
- Editing mutation tooling, targets, thresholds, tests, production code, or existing PR branches.
- Claiming a new Linux run on this branch; the binding measurement is run `30333581031` on the
  identical production/tooling state at `main@494eafc`.

## Behavioural requirements

- Regenerate the baseline as one coupled artifact from the retained Linux report rather than
  patching individual counts or survivor groups.
- Preserve classifications only for survivors still present, remove all now-killed survivors, and
  classify each newly observed survivor by exact name with merge attribution.
- Keep mutation targets, policy, comparison logic, thresholds, tests, and production code
  unchanged.

## Assumptions

- GitHub artifact `mutation-critical-result` from run `30333581031` is the authoritative retained
  report; its source SHA is the requested `main@494eafc`.
- The completed mutation self-test and zero unhealthy statuses establish that the report is usable
  even though the workflow conclusion is failure from the stale-baseline comparison.

## Expected artifacts

- Wholesale-regenerated `.ai/quality/mutation-baseline.toml`.
- Complete `.ai/tasks/ISSUE-118/` specification, impact, traceability, review, and evidence.
- A separate draft pull request linked to issue #118.

## Risk class

R3. `scripts/quality/classify.py` assigns R3 because the mutation baseline governs the critical
quality gate for every high-risk change.

## Human decisions required

Jan directed wholesale regeneration from run `30333581031`, required explicit proof that the
ratchet tightens, and prohibited merging or marking the change ready.

## Open questions

None.
