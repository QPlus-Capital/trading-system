# Evidence

## HEAD

HEAD: fd0ab938d4a5e8936b85c16a6a7b63dfe0cf53f1

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_docs.py::test_tool_contracts_bind_builder_and_reviewer_to_the_correct_files` | 1 | RED: old AGENTS reviewer contract lacked `primary builder` |
| `red-first` | focused engineering/runtime documentation suite after role edit | 1 | RED: existing runtime guard rejected non-trigger-oriented skill description |
| `format` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | GREEN: Ruff formatting plus the focused gate passed |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py` | 0 | GREEN: 74 governance, runtime-schema, and template tests passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check` | 0 | GREEN: Ruff, mypy over 150 files, vulture, and 717 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | GREEN: impact selected `tests/test_engineering_docs.py`; all 57 tests passed |
| `property-tests-where-applicable` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-properties` | 0 | GREEN: 8 properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 717 passed with no live terminal/account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 73` | 0 | GREEN: valid task with 5 acceptance criteria and 4 invariants |
| `adversarial-review` | `.ai/tasks/73/review.md` | 0 | GREEN: 14 role, safety, runtime, and scope counterexamples; no unresolved finding |
| `invariants` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-invariants` | 0 | GREEN: 129 critical live-risk, parity, sizing, research-integrity, and workflow tests passed |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring scripts/quality .claude/settings.json .github/workflows justfile pyproject.toml uv.lock` | 0 | GREEN: no trading, quality-tool, hook, CI, recipe, or dependency behaviour changed |
| `live-money-review` | changed-path and role-contract audit | 0 | GREEN: no live/risk/order/account code and no runner interaction; immutable constraints remain inline |
| `human-decision-escalation` | issue #73 and role-authority guard | 0 | GREEN: Jan retains every business, trading, methodology, live-money, architecture, risk, and merge decision |
| `no-autonomous-merge` | contract/constitution/branch-protection guard | 0 | GREEN: R3 autonomous merge remains prohibited and no merge action was added |
| `security` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and static security passed |

## Coverage and mutation

The role guard failed against the old assignment and passed after the content swap. Deterministic
properties passed twice. No production critical function changed; the mandatory Linux mutation
ratchet is recorded after the branch workflow completes.

## Deferred checks

Linux mutation evidence is deferred until the committed branch is pushed; it must pass before the
pull request opens.
