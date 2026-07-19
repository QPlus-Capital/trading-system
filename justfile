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
    uvx vulture core research live monitoring --min-confidence 80
