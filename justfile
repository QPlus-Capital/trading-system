# QPlus Trading System — command hub. Run `just` to list everything.
# (Install once: `winget install --id Casey.Just` or `cargo install just`.)

# Show all commands (default when you just type `just`)
default:
    @just --list

# ── RESEARCH ────────────────────────────────────────────────────────────
# Full backtest pipeline stage 1 → prints the next command after each stage.
# Results land in reports/framework/run_*/  (report.html is the readable one).
backtest study="research/config/robustness.py":
    uv run python -m research.stages.edge --config {{study}}

# Re-run only sizing + verdict on an existing run dir (fast; no re-extraction).
verdict run:
    uv run python -m research.stages.portfolio --run {{run}} --risk flat:0.18 --fixed live/config/paper_rsi_wpr_bb.py
    uv run python -m research.stages.verdict --run {{run}}

# Open the newest report.html in the browser.
report:
    uv run python -c "import pathlib,webbrowser; d=sorted(pathlib.Path('reports/framework').glob('run_*'));\
 webbrowser.open((d[-1]/'report.html').as_uri()) if d else print('no runs yet')"

# ── LIVE ────────────────────────────────────────────────────────────────
# Real TTP account (real money). Add MODE=execute for real orders.
live-ttp mode="signal_only":
    uv run python -m live.run --account ttp --mode {{mode}}

# MEX Atlantic demo account.
live-demo mode="signal_only":
    uv run python -m live.run --account mex --mode {{mode}}

# GO/NO-GO pre-flight before taking an account live.
preflight account="ttp":
    uv run python -m live.preflight --account {{account}}

# ── MONITORING ──────────────────────────────────────────────────────────
# Live-vs-backtest dashboard (browser). Defaults to the TTP account.
monitor:
    uv run streamlit run monitoring/dashboard.py

# ── QUALITY GATES (run before every commit) ─────────────────────────────
check:
    uv run ruff check .
    uv run mypy
    uv run pytest -q
