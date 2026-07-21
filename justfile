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
check:
    uv run ruff check .
    uv run mypy
    uv run pytest -q
    uvx vulture core research live monitoring scripts --min-confidence 80

# Risk class (R0–R3) and required gates for this branch vs origin/main (or pass explicit paths)
classify *paths:
    uv run python -m scripts.quality.classify {{paths}}

# Conservative changed-file impact report and machine-readable .ai/impact/test-map.json
impact range="origin/main":
    uv run python -m scripts.quality.impact --base {{range}}

# Fast local feedback: format, lint, types, then the conservative focused-test recommendation
check-fast range="origin/main":
    uv run python -m scripts.quality.impact --base {{range}} --check-format
    uv run ruff check .
    uv run mypy
    uv run python -m scripts.quality.impact --base {{range}} --run-focused

# Explicit placeholder until the dedicated security scanner lands; succeeds without claiming a scan
check-security:
    @uv run python -c "print('STUB: no automated security scanner is configured; human review required')"

# Explicit placeholder until critical-path mutation testing lands; never substitutes for `just check`
check-critical:
    @uv run python -c "print('STUB: no critical-path mutation runner is configured; record deferral')"

# Validate task artifacts, traceability, risk classification, review findings, and HEAD evidence
pr-ready task_id="" range="origin/main":
    uv run python -m scripts.quality.pr_ready {{task_id}} --base {{range}}
