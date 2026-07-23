# QPlus Trading System — type `just` to see all commands.
# (Install once: `winget install --id Casey.Just`)

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
    uv run python -m live.run --account ttp

# Live TTP account — REAL orders
live-ttp-execute:
    uv run python -m live.run --account ttp --mode execute

# Live MEX demo account — signal-only
live-demo:
    uv run python -m live.run --account mex

# GO/NO-GO pre-flight for the TTP account
preflight:
    uv run python -m live.preflight --account ttp

# Live-vs-backtest monitoring dashboard
monitor:
    uv run streamlit run monitoring/dashboard.py

# Quality gates — run before every commit (same as CI)
# Standard static quality gates (the CI Standard Quality job invokes this recipe verbatim)
check-standard:
    uv run ruff check .
    uv run mypy
    uvx vulture core research live monitoring scripts --min-confidence 80

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
    uv run python -m scripts.quality.classify {{paths}}

# Conservative changed-file impact report and ignored local .ai/impact/test-map.json
impact range="origin/main":
    uv run python -m scripts.quality.impact --base {{range}}

# Fast local feedback: format, lint, types, then the conservative focused-test recommendation
check-fast range="origin/main":
    uv run python -m scripts.quality.impact --base {{range}} --check-format
    uv run ruff check .
    uv run mypy
    uv run python -m scripts.quality.impact --base {{range}} --run-focused

# Validate the one changed task artifact (or pass its ID explicitly)
check-task-artifact task_id="" range="origin/main":
    uv run python -m scripts.quality.impact --base {{range}}
    uv run python -m scripts.quality.validate_task --task-id "{{task_id}}" --base {{range}}

# Secret scan, dependency vulnerability audit, and high-signal static security checks
check-security:
    uv run python -m scripts.quality.security
    uv run pip-audit --skip-editable
    uv run ruff check core research live monitoring scripts --select S --ignore S101,S110,S603,S607

# Critical invariant suite; separate CI visibility, never a substitute for the full tests
check-invariants:
    uv run pytest -q tests/test_live_risk_control.py tests/test_live_accounts.py tests/test_live_parity_check.py tests/test_strategy_sizing_basis.py tests/test_research_sizing.py tests/test_research_portfolio_dd.py tests/test_research_risk.py tests/test_research_stats.py tests/test_research_continuous_windows.py tests/test_research_regression.py tests/test_research_forward_test_registry.py tests/test_quality_classify.py tests/test_quality_pr_ready.py

# Validate the PR template and bind its task reference to current readiness evidence
check-pr-evidence body_file="" range="origin/main":
    uv run python -m scripts.quality.pr_body --body-file "{{body_file}}" --base {{range}}

# Fast mutation feedback for configured R3 modules changed on this branch (Linux/WSL only)
mutation-fast range="origin/main":
    uv run --no-sync --with mutmut==3.5.0 python -m scripts.quality.mutation run --scope fast --base {{range}}

# Full focused critical mutation scope with the committed TOML ratchet (Linux/WSL only)
mutation-critical:
    uv run --no-sync --with mutmut==3.5.0 python -m scripts.quality.mutation run --scope critical

# Prove the mutation ratchet catches a real weakened test (Linux/WSL only)
mutation-self-test:
    uv run --no-sync --with mutmut==3.5.0 pytest -q tests/test_quality_mutation.py::test_a_real_weakened_test_increases_survivors_and_is_caught

# Critical-path gate; never substitutes for `just check`
check-critical range="origin/main":
    just mutation-fast {{range}}

# Validate task artifacts, traceability, risk classification, review findings, and HEAD evidence
pr-ready task_id="" range="origin/main":
    uv run python -m scripts.quality.pr_ready {{task_id}} --base {{range}}
