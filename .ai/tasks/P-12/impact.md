# Impact analysis

## Direct impact

- Adds one isolated `research/forward_test_registry.py` persistence boundary.
- Adds focused registry tests and deterministic properties.
- Adds the module to the architecture map and the hashing/identity functions to the existing
  mutation policy.

Initial explicit-path classifier result: R3 after including `.ai/quality/mutation.toml`; the new
research module alone is the model's R2 minimum and is semantically upgraded to R3 for result
integrity.

Initial `just impact` reported R0/no changes because changed-path discovery is commit based and the
red-first files were uncommitted. Explicit intended-path impact reported R3, selected
`tests/test_research_forward_test_registry.py` and `tests/test_quality_properties.py`, and found no
transitive or dynamic consumer. Final `just impact` against `origin/main` reported R3, the same two
direct tests, the registry as a critical-path escalation, and no transitive, dynamic, or possibly
affected tests.

## Transitive impact

Nothing imports the registry yet. P-13 may later read its definitions and observation series, but
this package changes no stage, report, live process, or decision.

## Critical dependencies

- `research/stages/lineage.py` remains the sole SHA-256 file/byte hashing convention.
- JSON serialization must preserve `Decimal` values as strings and UUIDs as opaque identifiers.
- Registry reads must revalidate persisted identity before returning observations.

## Unknown or dynamic edges

- The future P-13 consumer and the operational location/mapping of the first cohort do not exist in
  this package.
- Cross-process append contention is outside the issue's single-writer registry contract; create
  uses exclusive file creation and every read revalidates the complete artifact.
