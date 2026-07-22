# Evidence

## HEAD

HEAD: 05365c71d779b0cd6de4744c8d9f6035be4812a0

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_hooks.py tests/test_claude_runtime_files.py` | 1 | RED at collection: `scripts.quality.hooks` absent |
| `red-first` | focused hook/runtime suite after first implementation | 1 | RED: exact dotted live command was allowed and agent read-only prose wrapped unexpectedly |
| `red-first` | focused hook/runtime suite after matcher fix | 1 | RED: synthetic fixture source was misclassified as a real secret |
| `red-first` | staged commit-hook dogfood | 1 | RED: the exact fake-secret f-string with an escaped newline blocked its own commit |
| `red-first` | staged commit-hook bypass dogfood | 1 | RED: a quoted broad-ignore counterexample was treated as a real Python suppression |
| `red-first` | coded broad-suppression probe | 1 | RED: `noqa: ALL` passed as if it were a narrow code |
| `red-first` | mutation-policy evidence probe | 1 | RED: `mutation.toml` changed without explicit mutation evidence |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | Five changed Python files already formatted; branch classified R3 |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py` | 0 | 57 passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check` | 0 | Ruff, mypy (144 files), pytest (684 passed, 1 Linux-only skip), and vulture passed |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | R3; 27 recommended hook/runtime tests passed after format, Ruff, and mypy |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` twice | 0 | 8 passed twice with the same seed |
| `integration-tests` | full pytest within `check` | 0 | 684 passed, 1 Linux-only mutation skip |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 66` | 0 | Valid: 4 acceptance criteria and 4 invariants |
| `adversarial-review` | `.ai/tasks/66/review.md` | 0 | 23 counterexamples attempted; R-01 through R-09 resolved |
| `invariants` | `uv run pytest -q tests/test_quality_hooks.py tests/test_claude_runtime_files.py tests/test_engineering_docs.py` | 0 | 82 passed; block/allow, schemas, snapshots, fail-closed output, and risk rules covered |
| `mutation-on-touched-critical` | Linux `mutation-critical` workflow (run 29898400124) | 0 | Weakened-test probe and complete focused critical ratchet passed; later hook-only commit leaves all configured critical targets byte-identical |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring` | 0 | No production trading package changed |
| `live-money-review` | R3 review plus production-package diff check | 0 | No live implementation changed and no live interaction occurred |
| `human-decision-escalation` | issue #66 scope and merge rule | 0 | Jan retains scope and merge authority |
| `no-autonomous-merge` | branch/PR policy review | 0 | No merge or autonomous-merge action exists in the change |

## Coverage and mutation

The hook/runtime suite has 25 tests and includes paired unsafe/safe decisions for all eight policy
areas. The deterministic property suite passed twice. No configured production mutation target or
production trading module changed. Linux run `29898400124` passed both the real weakened-test probe
and the complete focused critical mutation ratchet.

## Deferred checks

- Issue #74 tracks a fail-closed bootstrap for Linux-only evidence before the first Windows push.
