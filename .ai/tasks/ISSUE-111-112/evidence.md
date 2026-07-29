# Evidence

## HEAD

HEAD: pending-tested-commit

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_review_selection.py tests/test_claude_runtime_files.py tests/test_finding_registry_split.py tests/test_task_artifact_validation.py tests/test_workflow_contract.py` | 1 | Pending execution against the pre-change tree. |

## Coverage and mutation

Focused, full-suite, invariant, property, security, and Linux mutation evidence is pending
implementation.

## Deferred checks

Independent Claude review is intentionally deferred until the draft pull request exists. Jan alone
makes the pull request ready and merges it.
