# Evidence

## HEAD

HEAD: pre-implementation

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_signal_adapter_parity.py` | 1 | Planned behavioural mismatch proof; replace with actual output after execution. |

## Coverage and mutation

Coverage and mutation evidence will be recorded after implementation. The Linux Critical mutation
gate is expected to be blocked by infrastructure, not treated as passed.

## Deferred checks

Linux Critical mutation is blocked by infrastructure because the GitHub Actions quota is exhausted
until 2026-08-01. Independent Claude review follows the draft pull request.
