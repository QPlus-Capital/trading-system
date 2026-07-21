# Evidence

## HEAD

HEAD: 367e44485f713eafa2b5b2d4b1095c53f1467baa

## Commands

| Command | Exit status | Result |
|---|---:|---|
| `uv run pytest -q tests/test_quality_validate_task.py tests/test_quality_impact.py tests/test_quality_pr_ready.py` | 1 | RED: three new modules absent during collection |
| same focused command after implementation | 0 | GREEN: 19 tests passed before added hardening cases |
| adversarial validator bypass cases before implementation | 1 | RED: empty section and missing command evidence were accepted |
| `uv run pytest -q tests/test_quality_validate_task.py tests/test_quality_impact.py tests/test_quality_pr_ready.py` | 0 | GREEN: 31 tests passed |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run mypy` | 0 | No issues in 131 source files |
| `uv run pytest -q` | 0 | 609 passed; 86 pre-existing warnings tracked in #68 |
| `uvx vulture core research live monitoring scripts --min-confidence 80` | 0 | No dead code reported |
| `uv run python -m scripts.quality.validate_task 64` | 0 | Four ACs and four INVs valid |
| `uv run python -m scripts.quality.classify ...` | 0 | Every new gate/config path reported R3 |
| `uv run python -m scripts.quality.pr_ready 64 --base origin/main` | 0 | R3 task, risk, and current-evidence checks ready |
| `uvx --from rust-just just --list` and recipe dry runs | 0 | New recipe syntax and argument expansion valid |
| `uvx --from rust-just just ... check-fast origin/main` | 0 | Format, lint, types, and 31 focused tests passed |
| `uv run ruff format --check .` | 1 | RED: 42 untouched baseline files are not formatter-clean |
| impact determinism test before canonical ordering | 1 | RED: identical path sets produced unequal reports |

## Coverage and mutation

Behavioural branch coverage includes malformed task artifacts, direct/transitive/inheritance/dynamic
impact edges, risk understatement, CLI exit status, stale SHA, and the evidence-only commit rule.
Mutation testing is out of scope for issue 64 and is explicitly represented by the `check-critical`
stub; no mutation pass is claimed.

## Deferred checks

- Independent Claude review occurs on the opened PR.
- Dedicated security scanning and mutation infrastructure are later workflow PRs per issue scope.
- The combined gate invocation hit a 120-second harness timeout; each constituent command then ran
  separately to completion with the results above.
