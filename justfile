# QPlus Trading System — type `just` to see all commands.
# (Install once: `winget install --id Casey.Just`)

# Recipes default to `sh`, which Windows only has inside Git Bash — from PowerShell every recipe
# fails before it starts. cmd passes comma-joined arguments through literally; PowerShell splits
# them, which would break the `--ignore S101,...` line below.
set windows-shell := ["cmd.exe", "/c"]

# List all commands
default:
    @just --list

# Run the full research pipeline (stage 1 -> prints the next command)
backtest:
    uv run python -m research.stages.edge research/config/robustness.py

# Open the newest report.html in the browser -- refuses if its lineage no longer verifies
report:
    uv run python -m research.stages.open_report

# Live TTP account — signal-only (safe, no orders)
live-ttp:
    uv run --env-file .env python -m live.run --account ttp

# Live TTP account — REAL orders
live-ttp-execute:
    uv run --env-file .env python -m live.run --account ttp --mode execute

# Live MEX demo account — signal-only
live-demo:
    uv run --env-file .env python -m live.run --account mex

# GO/NO-GO pre-flight for the TTP account
preflight:
    uv run --env-file .env python -m live.preflight --account ttp

# Live-vs-backtest monitoring dashboard
monitor:
    uv run --env-file .env streamlit run monitoring/dashboard.py

# Quality gates — run before every commit (same as CI)
# Standard static quality gates (the CI Standard Quality job invokes this recipe verbatim)
check-standard:
    uv run ruff check .
    uv run mypy
    uvx vulture core research live monitoring workflow --min-confidence 80

# Full deterministic test suite (the CI Tests job invokes this recipe verbatim)
check-tests:
    uv run pytest -q

# Deterministic property replay (the CI Tests job invokes this recipe verbatim)
check-properties:
    uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721
    uv run pytest -q tests/test_quality_properties.py --hypothesis-seed=20260721

# Quality gates — run before every commit (same commands as the split CI jobs)
check: check-standard check-tests

# Risk class (R0–R3) and required gates for this branch vs origin/main (or pass explicit paths)
classify *paths:
    uv run python -m workflow.classify {{paths}}

# Run exactly the gates this branch's risk class requires, and print the evidence table
gates range="origin/main":
    uv run python -m workflow.gates --base {{range}}

# Read or move one card on the project board
board *args:
    uv run python -m workflow.board {{args}}

# Remove the worktree and branch traces left by one completed ticket
finish issue:
    uv run python -m workflow.finish {{issue}}

# Conservative changed-file impact report and ignored local workflow/impact/test-map.json
impact range="origin/main":
    uv run python -m workflow.impact --base {{range}}

# Fast local feedback: format, lint, types, then the conservative focused-test recommendation
check-fast range="origin/main":
    uv run python -m workflow.impact --base {{range}} --check-format
    uv run ruff check .
    uv run mypy
    uv run python -m workflow.impact --base {{range}} --run-focused

# Secret scan, dependency vulnerability audit, and high-signal static security checks
check-security:
    uv run python -m workflow.security
    uv run pip-audit --skip-editable
    uv run ruff check core research live monitoring workflow --select S --ignore S101,S110,S603,S607

# Critical invariant suite; separate CI visibility, never a substitute for the full tests
check-invariants:
    uv run pytest -q tests/test_live_risk_control.py tests/test_live_accounts.py tests/test_live_mt5_bridge.py tests/test_live_runner_cycle.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_signal_adapter_parity.py tests/test_strategy_sizing_basis.py tests/test_research_h4_path.py tests/test_research_sizing.py tests/test_research_portfolio_dd.py tests/test_research_risk.py tests/test_research_stats.py tests/test_research_scenarios.py tests/test_research_path_risk.py tests/test_research_continuous_windows.py tests/test_research_regression.py tests/test_research_forward_test_registry.py tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py tests/test_workflow_classify.py tests/test_workflow_contract_docs.py tests/test_workflow_finish.py

# Backtest/live parity: the two adapters must produce identical signals from one engine
check-parity:
    uv run pytest -q tests/test_signal_adapter_parity.py tests/test_live_parity_check.py tests/test_strategy_sizing_basis.py

# Mutation on the critical modules this branch changed (macOS/Linux; needs fork)
mutation range="origin/main":
    uv run --no-sync --with mutmut==3.5.0 python -m workflow.mutation run --scope fast --base {{range}}

# Mutation on every target this branch's diff can reach, incl. via changed tests (macOS/Linux)
mutation-affected range="origin/main":
    uv run --no-sync --with mutmut==3.5.0 python -m workflow.mutation run --scope affected --base {{range}}

# Full focused critical mutation scope with the committed TOML ratchet (macOS/Linux)
mutation-critical:
    uv run --no-sync --with mutmut==3.5.0 python -m workflow.mutation run --scope critical

# Prove the mutation ratchet catches a real weakened test (macOS/Linux)
mutation-self-test:
    uv run --no-sync --with mutmut==3.5.0 pytest -q tests/test_workflow_mutation.py::test_a_real_weakened_test_increases_survivors_and_is_caught
