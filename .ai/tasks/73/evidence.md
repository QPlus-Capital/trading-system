# Evidence

## HEAD

HEAD: pending-final-commit

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_docs.py::test_tool_contracts_bind_builder_and_reviewer_to_the_correct_files` | 1 | RED: old AGENTS reviewer contract lacked `primary builder` |
| `red-first` | focused engineering/runtime documentation suite after role edit | 1 | RED: existing runtime guard rejected non-trigger-oriented skill description |

## Coverage and mutation

Pending final local and Linux evidence.

## Deferred checks

Linux mutation evidence is deferred until the committed branch is pushed.
