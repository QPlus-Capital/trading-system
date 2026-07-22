# Evidence

## HEAD

HEAD: a1b556c828ef3b5cf4f70bca917dd69c7488b4aa

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_github_templates.py tests/test_quality_security.py tests/test_gate_consistency.py tests/test_engineering_workflow_docs.py tests/test_workflow_system_validation.py` | 1 | RED at collection: `pr_body.py` and `security.py` absent |
| `red-first` | `uv run pytest -q tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries` | 1 | RED: real MT5 functions had no pytest boundary |
| `red-first` | focused manual-R3 and unchecked-attestation tests | 1 | RED: both unsafe states were accepted |
| `red-first` | `uv run pip-audit --skip-editable` before lock refresh | 1 | RED: GitPython 3.1.50 had three published vulnerabilities |
| `red-first` | Linux mutation workflow run `29905820402` | 1 | RED: global pytest fixture imported Windows-only MetaTrader5 during collection |
| `format` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | 12 changed Python files formatted; Ruff and mypy passed |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py tests/test_github_templates.py` | 0 | 68 passed; architecture, policies, native template metadata, and PR body contract agree |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check` | 0 | Ruff, mypy over 150 files, 715 pytest tests, and vulture passed; one Linux-only test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-fast` | 0 | R3 impact analysis selected 83 tests; all passed |
| `property-tests-where-applicable` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-properties` | 0 | 8 properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `check` | 0 | 715 passed; no live terminal or account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 67` | 0 | Valid: 5 acceptance criteria and 5 invariants |
| `adversarial-review` | `.ai/tasks/67/review.md` | 0 | 36 counterexamples; R-01 through R-07 resolved and F-026 through F-032 registered |
| `invariants` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-invariants` | 0 | 129 critical live-risk, parity, sizing, research-integrity, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29906179089` | 0 | Real weakened-test probe, complete mutation ratchet, and result-artifact upload passed |
| `parity-where-applicable` | `git diff --quiet origin/main -- core research live monitoring` | 0 | No production trading package changed |
| `live-money-review` | production-package diff plus adversarial review | 0 | No live/risk/order/account code or runner interaction; test boundary blocks real MT5 calls |
| `human-decision-escalation` | issue #67 and branch-protection policy review | 0 | Jan retains branch-protection, scope, go-live, and merge decisions |
| `no-autonomous-merge` | workflow and PR policy review | 0 | No merge action exists; R3 autonomous merge is explicitly prohibited |
| `security` | `uvx --from rust-just just --shell powershell.exe --shell-arg -Command check-security` | 0 | Tracked secret scan clean; no known dependency vulnerabilities; static security rules passed |

## Coverage and mutation

The synthetic secret/clean fixtures use the real detect-secrets engine. Deterministic property
tests passed twice. Linux run `29906179089` passed the weakened-test probe and every configured
critical mutation scope, and uploaded `.ai/mutation/critical.toml`.

## Deferred checks

- Jan applies branch protection after merge.
