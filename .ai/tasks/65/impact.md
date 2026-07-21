# Impact analysis

## Direct impact

- `tests/support/` and the testing guide define reusable boundary and reconciliation techniques.
- Hypothesis and property tests exercise existing pure live/research/quality behaviour.
- Mutation TOML, orchestrator, just recipes, and Linux workflow add an R3 survivor ratchet.
- Windows CI replays the deterministic property suite twice.

## Transitive impact

- Future R3 changes to configured critical modules may run `mutation-fast` locally and are checked
  against the critical baseline in Linux CI.
- `check-critical` now invokes real focused mutation selection instead of a success-only stub.
- Task readiness can record `mutation-on-touched-critical` as executable evidence.

## Critical dependencies

- Mutation fast selection calls `changed_paths`, `normalize`, and `classify_path` from
  `scripts/quality/classify.py`.
- Mutmut reads its execution paths from `pyproject.toml`; the orchestrator verifies those paths
  exactly equal `.ai/quality/mutation.toml`.
- The baseline target IDs must equal the critical policy order and every survivor is explained.

## Unknown or dynamic edges

- Mutmut relies on Linux `fork`, pytest coverage discovery, and the pinned tool's textual result
  format; the dedicated job executes these dynamic edges rather than simulating them on Windows.
- The Linux job omits MetaTrader5 because no Linux wheel exists; configured targets are pure and do
  not require the bridge, but the complete Windows suite remains mandatory.
