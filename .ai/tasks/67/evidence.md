# Evidence

## HEAD

HEAD: replace-with-tested-commit-sha

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_github_templates.py tests/test_quality_security.py tests/test_gate_consistency.py tests/test_engineering_workflow_docs.py tests/test_workflow_system_validation.py` | 1 | RED at collection: `pr_body.py` and `security.py` absent |
| `red-first` | `uv run pytest -q tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries` | 1 | RED: real MT5 functions had no pytest boundary |
| `red-first` | focused manual-R3 and unchecked-attestation tests | 1 | RED: both unsafe states were accepted |
| `red-first` | `uv run pip-audit --skip-editable` before lock refresh | 1 | RED: GitPython 3.1.50 had three published vulnerabilities |

## Coverage and mutation

Pending.

## Deferred checks

- Linux mutation-critical will run through the existing workflow dispatch after the tested commit.
- Jan applies branch protection after merge.
