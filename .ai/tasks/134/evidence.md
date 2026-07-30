# Evidence

## HEAD

HEAD: f2f89ff8122aaa51efaa50e69eaedb31e6125717

## Commands

Record every cumulative gate printed by `pr-ready` with its exact gate ID and a final exit status
of 0. Label before-fix failures `red-first`, not with a required gate ID; any non-zero record for a
required gate blocks readiness even when another row passes.

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_review_observation.py tests/test_quality_pr_ready.py tests/test_quality_validate_task.py tests/test_ci_cost_workflows.py` | 1 | RED: collection failed because `scripts.quality.review_observation` did not exist |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | 8 changed Python files formatted; R3 impact report completed |
| `docs-consistency` | `uv run pytest -q tests/test_workflow_contract.py tests/test_engineering_docs.py tests/test_claude_runtime_files.py` | 0 | 99 documentation and workflow-contract tests passed |
| `check` | `uv run ruff check .` | 0 | All Ruff checks passed |
| `check` | `uv run mypy` | 0 | No issues in 195 source files |
| `check` | `uvx vulture core research live monitoring scripts --min-confidence 80` | 0 | No dead-code findings at 80% confidence |
| `check` | `uv run pytest -q` | 0 | 1,657 tests passed; one Windows Mutmut availability self-test skipped |
| `check` | `uv run python -m scripts.quality.security` | 0 | Secret scan passed with no findings |
| `check` | `uv run pip-audit --skip-editable` | 0 | No known dependency vulnerabilities |
| `check` | `uv run ruff check core research live monitoring scripts --select S --ignore S101,S110,S603,S607` | 0 | Security lint passed |
| `impacted-tests` | `uv run pytest -q tests/test_ci_cost_workflows.py tests/test_github_templates.py tests/test_quality_board.py tests/test_quality_hooks.py tests/test_quality_issue_body.py tests/test_quality_pr_ready.py tests/test_quality_process_scaling.py tests/test_quality_review_observation.py tests/test_quality_validate_task.py tests/test_workflow_system_validation.py` | 0 | All 142 directly and transitively impacted tests passed |
| `property-tests-where-applicable` | `uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721` (twice) | 0 | Both deterministic replays passed, 21 tests each |
| `integration-tests` | `uv run pytest -q` | 0 | Full integration-bearing suite passed: 1,657 passed, 1 platform skip |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 134 --base origin/main` | 0 | Task 134 valid with 7 AC and 3 INV mappings |
| `adversarial-review` | `deferred to independent reviewer on the draft pull request` | 1 | Pending; the builder did not review or self-certify the change |
| `invariants` | `uv run pytest -q tests/test_live_risk_control.py tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_signal_adapter_parity.py tests/test_strategy_sizing_basis.py tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_portfolio_dd.py tests/test_research_risk.py tests/test_research_stats.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_continuous_windows.py tests/test_research_regression.py tests/test_research_forward_test_registry.py tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py tests/test_quality_classify.py tests/test_quality_pr_ready.py` | 0 | 537 critical-invariant tests passed |
| `mutation-on-touched-critical` | `uv run --no-sync --with mutmut==3.5.0 python -m scripts.quality.mutation run --scope fast --base origin/main` | 1 | Deferred to Linux CI: no critical target was discovered, and Mutmut correctly refused Windows; WSL is unavailable |
| `parity-where-applicable` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | No live/backtest parity path is touched |
| `live-money-review` | `uv run python -m scripts.quality.classify` | 0 | Not applicable: no `live/**` path or live-money boundary is touched |
| `human-decision-escalation` | `uv run python -m scripts.quality.board status 134` | 0 | Issue was approved at R3 with no open human decision before the permit was consumed |
| `no-autonomous-merge` | `git status --short --branch` | 0 | Feature branch only; merge and auto-merge remain disabled |

## Coverage and mutation

Focused behavioural coverage includes review/commit ordering, GitHub verdict states, validator and
readiness agreement, Markdown-shape independence, evidence-only currency, and synchronize-diff CI
selection. The full suite passed on the recorded HEAD. Linux mutation execution remains a CI check;
impact analysis selected no configured critical target for the changed files.

## Deferred checks

Independent review and Linux mutation execution are deferred to the draft pull request. Both
required gate rows remain non-zero until their real external checks complete.
