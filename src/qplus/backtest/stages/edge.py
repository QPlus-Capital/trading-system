"""Stage 1 — EDGE: does the strategy have an edge, where, and is it robust?

Runs (or ingests) the walk-forward study sweep and prints a per-variation decision table:
cross-instrument OOS return, its risk-adjusted twin, and how consistent it is. The two
structure gates (robust majority positive AND risk within tolerance of the best) mark which
variations are *eligible*. You read this and decide which variation to carry forward.

Usage::

    # run the full sweep (heavy), then show the ranking:
    uv run python -m qplus.backtest.stages.edge config/study/robustness.py
    # or ingest an already-computed study:
    uv run python -m qplus.backtest.stages.edge config/study/robustness.py --from <study_dir>
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from qplus.backtest.config import load_config_module
from qplus.backtest.select import universe
from qplus.backtest.stages import _runbook as rb

# Defaults only -- a study config may override via SELECT_MIN_FRAC_POSITIVE / SELECT_RPD_TOLERANCE.
_MIN_FRAC_POSITIVE = 0.9  # structure gate: OOS-positive on a robust majority of instruments
_RPD_TOLERANCE = 0.85  # structure gate: risk-adjusted return within 85% of the best


def _study_csv_from(source: Path) -> Path:
    """Resolve ``--from`` to a study.csv (accepts the csv itself or a study run directory)."""
    if source.is_dir():
        return source / "study.csv"
    return source


def _run_study(config: Path) -> Path:
    """Run the heavy sweep via the characterize entrypoint and return its study.csv."""
    from qplus.backtest.edge import characterize

    characterize.main([str(config)])
    study_root = rb._REPO_ROOT / "reports" / "study"
    runs = sorted(study_root.glob("run_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit("study produced no run directory")
    return runs[-1] / "study.csv"


def ranking(
    df: pd.DataFrame,
    *,
    min_frac_positive: float = _MIN_FRAC_POSITIVE,
    rpd_tolerance: float = _RPD_TOLERANCE,
) -> pd.DataFrame:
    """Per-variation decision table: the best training length per variation, return-first, gated."""
    valid = df.dropna(subset=["mean_oos_pct", "return_per_dd"])
    g = universe._per_config(valid).reset_index()
    best_rpd = float(g["mean_rpd"].max()) if not g.empty else 0.0
    gate_pos = g["frac_positive"] >= min_frac_positive
    gate_rpd = g["mean_rpd"] >= rpd_tolerance * best_rpd
    g["eligible"] = gate_pos & gate_rpd
    # One row per variation: its best training length by return (what Stage 2 would pick).
    best_idx = g.groupby("variation")["mean_ret"].idxmax()
    return g.loc[best_idx].sort_values("mean_ret", ascending=False).reset_index(drop=True)


def _print_table(top: pd.DataFrame) -> str:
    """Print the ranking; return the auto-pick (highest-return eligible) variation name."""
    print(f"\n  {'variation':14s} {'train':>5s} {'Rendite':>9s} {'Rend/DD':>8s} {'%pos':>6s}  Gate")
    auto = ""
    for _, r in top.iterrows():
        gate = "ok eligible" if r["eligible"] else "   gated out"
        if r["eligible"] and not auto:
            auto, gate = str(r["variation"]), "<< AUTO-PICK"
        print(
            f"  {r['variation']:14s} {int(r['train_months']):>4d}m {r['mean_ret']:>+8.1f}% "
            f"{r['mean_rpd']:>8.2f} {r['frac_positive']:>5.0%}  {gate}"
        )
    return auto


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stage 1 (EDGE): robustness ranking.")
    parser.add_argument("config", type=Path, help="study config module (strategy + variations)")
    parser.add_argument(
        "--from", dest="source", type=Path, default=None,
        help="ingest an existing study.csv / run dir instead of running the sweep",
    )
    parser.add_argument(
        "--run", type=Path, default=None, help="write into this framework run dir (default: fresh)"
    )
    args = parser.parse_args(argv)

    run = rb.RunDir.open(args.run) if args.run else rb.RunDir.create()
    rb.banner(1, "EDGE - Kante & Robustheit", run)

    study_csv = _study_csv_from(args.source) if args.source else _run_study(args.config)
    shutil.copyfile(study_csv, run.file("study.csv"))  # anchor the study in this run
    df = pd.read_csv(run.file("study.csv"))

    # Gates live in the study config (per strategy), not in this code -- nothing strategy-specific.
    cfg = load_config_module(args.config)
    min_pos = float(getattr(cfg, "SELECT_MIN_FRAC_POSITIVE", _MIN_FRAC_POSITIVE))
    rpd_tol = float(getattr(cfg, "SELECT_RPD_TOLERANCE", _RPD_TOLERANCE))

    top = ranking(df, min_frac_positive=min_pos, rpd_tolerance=rpd_tol)
    top.to_csv(run.file("edge_ranking.csv"), index=False)
    auto = _print_table(top)
    print(f"\n  Gate: %pos>={min_pos:.0%} und Rend/DD>={rpd_tol:.0%} vom Besten.")
    print(f"  Auto-Auswahl (hoechste Rendite unter eligible): {auto or '- (keine eligible)'}")

    select_auto = rb.cmd("select", "--run", str(run.path))
    rb.next_step(select_auto, "Universum waehlen (Auto) - oder --variation <name> anhaengen")


if __name__ == "__main__":
    main()
