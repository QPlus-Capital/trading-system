# P-12: Immutable forward-test registry

## Problem

`research/config/robustness.py` names a forward-test freeze date but no registry binds observations
to immutable, content-addressed cohort inputs.

## Goal

Provide an append-only forward-test registry that identifies cohorts from exact input contents,
keeps live and paper daily net-R observations separate, and fails closed on identity drift.

## Non-goals

- Implementing the P-13 decision protocol, thresholds evaluation, stopping decisions, or go-live
  logic.
- Changing any research stage, lineage convention, Monte Carlo process, live runner, reported
  result, strategy parameter, or account configuration.
- Reading actual fills or computing the 16:15 America/Chicago daily net portfolio R.
- Persisting an account number, credential, or mapping from an opaque identifier to an account.

## Behavioural requirements

- Hash strategy config, universe, stops, targets, risk, broker/cost snapshot, and signal logic by
  file contents through `research.stages.lineage.sha256_file`.
- Derive cohort identity from canonical content hashes plus the immutable cohort design; paths
  never enter the identity.
- Persist one create-only cohort definition and append daily observations without rewriting it.
- Reject a definition whose persisted identity no longer matches its contents.
- Bind each cohort to exactly one observation source (`live` or `paper`) and one UUID-shaped opaque
  participant identifier.
- Store daily net portfolio R as finite `Decimal` text on the named 16:15
  America/Chicago loss-day axis.
- Refuse pooling across cohort IDs or observation sources.

## Acceptance criteria

- AC-01: Changing one stop-file value changes the cohort UUID.
- AC-02: Moving every hashed file without changing its contents preserves the cohort UUID.
- AC-03: Changing signal-code contents changes the cohort UUID.
- AC-04: Pooling result sets from two cohort UUIDs raises.
- AC-05: Appending or pooling live and paper observations into one cohort series raises.
- AC-06: A synthetic credential and numeric account ID are rejected before writing, and neither
  appears anywhere in the registry artifact on disk.
- AC-07: Editing a persisted cohort's hashed inputs makes subsequent reads raise an integrity
  error; registering changed inputs creates a new cohort and leaves the old definition byte-for-byte
  unchanged.
- AC-08: Cohort records contain every field required by issue #53, and daily observations preserve
  exact `Decimal` values and the loss-day axis.
- AC-09: `just check`, deterministic property replay, focused mutation, security, and readiness
  gates pass.

## Invariants

- INV-01: A path is metadata outside cohort identity; only the bytes at that path are hashed.
- INV-02: Cohort definitions are create-only and observations are append-only.
- INV-03: Different cohorts and different observation sources never pool.
- INV-04: Persisted money/count-like values are finite `Decimal` strings, never JSON floats.
- INV-05: The registry has no logging path and accepts only UUID-shaped opaque participant IDs.
- INV-06: No existing historical or staged research artifact is read, rewritten, or re-scored.

## Assumptions

- The producer supplies one file for each content category and an aware cohort start timestamp.
- Upstream fill accounting supplies one already-aggregated daily net portfolio R per loss day.
- A UUID-shaped participant ID is maintained outside the repository as the opaque account/paper
  mapping.

## Open questions

- The issue does not specify the current cohort's opaque participant UUID, primary hypothesis,
  thresholds, minimum duration/trade count, or allowed safety-stop reasons. The package therefore
  provides the registry and schema but does not invent or commit an operational cohort. P-13 or a
  human-approved enrollment step must supply those values.

## Expected artifacts

- `research/forward_test_registry.py`, focused behavioural and property tests, an updated
  architecture module map, focused mutation policy/ratchet coverage, and this five-file task
  artifact.

## Risk class

R3 by semantic upgrade: the new module itself classifies R2 under the research catch-all, while
the registry governs forward-test result integrity and its required mutation-policy changes are
R3. Full cumulative R3 gates apply.

## Human decisions required

Jan must approve operational cohort enrollment values and every merge. Claude independently
reviews this R3 P-package; there is no autonomous merge.
