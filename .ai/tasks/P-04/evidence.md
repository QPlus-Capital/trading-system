# Evidence

## HEAD

HEAD: pending-tested-commit

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_research_resample.py tests/test_research_resample_properties.py` | 1 | Pending exact missing-module failure |

## Coverage and mutation

Calibration counts are fixed at 1,000 experiments and 299 resamples per experiment. Linux mutation
evidence is pending implementation and branch push.

## Deferred checks

Linux mutation and Claude's independent pull-request review remain pending.
