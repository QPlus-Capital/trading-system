# Evidence

## HEAD

HEAD: 9b10b15

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | planned-path `uv run python -m scripts.quality.classify ...` | 0 | R3: Stage-1 selection, continuous attribution, lineage, and result integrity |
| `impact-pre-code` | `uvx --from rust-just just impact origin/main` | 0 | R0 for the task-document-only diff; the explicit result-stream inventory in `impact.md` governs the planned R3 implementation |
| `red-first` | `uv run pytest -q tests/test_research_candidate_artifacts.py` before implementation | 1 | RED: all 10 tests failed; the candidate module, canonical payload, artifacts, hashes, and exact aggregation did not exist |

## Red-first proof

All ten focused tests were observed failing before production implementation.

## Regression

Pending zero-threshold comparison of unchanged `run_20260724_1146`.

## Deferred checks

Implementation and all R3 gates are pending.
