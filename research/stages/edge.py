"""Stage 1 — EDGE: does the strategy have an edge, where, and is it robust?

Runs (or ingests) the walk-forward study sweep and prints a per-variation decision table:
cross-instrument OOS return, its risk-adjusted twin, and how consistent it is. The two
structure gates (robust majority positive AND risk within tolerance of the best) mark which
variations are *eligible*. You read this and decide which variation to carry forward.

Usage::

    # run the full sweep (heavy), then show the ranking:
    uv run python -m research.stages.edge research/config/robustness.py
    # or ingest an already-computed study:
    uv run python -m research.stages.edge research/config/robustness.py --from <study_dir>
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from research.engine.config import load_config_module
from research.stages import _runbook as rb
from research.stages import universe

# Defaults only -- a study config may override via SELECT_MIN_FRAC_POSITIVE / SELECT_RPD_TOLERANCE.
_MIN_FRAC_POSITIVE = 0.9  # structure gate: OOS-positive on a robust majority of instruments
_RPD_TOLERANCE = 0.85  # structure gate: risk-adjusted return within 85% of the best
# Statistical gate (Stage 2, methodology.md): the deflated Sharpe must clear this after correcting
# for the trial budget, and the study-level PBO must stay below its ceiling.
_DSR_MIN = 0.90
_PBO_MAX = 0.20


def _study_csv_from(source: Path) -> Path:
    """Resolve ``--from`` to a study.csv (accepts the csv itself or a study run directory)."""
    if source.is_dir():
        return source / "study.csv"
    return source


def _run_study(config: Path) -> Path:
    """Run the heavy sweep via the characterize entrypoint and return its study.csv."""
    from research.engine import characterize

    characterize.main([str(config)])
    study_root = rb._REPO_ROOT / "reports" / "research"
    runs = sorted(study_root.glob("study_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit("study produced no run directory")
    return runs[-1] / "study.csv"


def load_overfitting(source_dir: Path) -> tuple[dict[str, float], float | None]:
    """Read the study's ``ranking.csv`` (per-variation DSR) + ``overfitting.json`` (study PBO).

    Returns ``(dsr_by_variation, pbo)``. Both are empty/None if the study predates these artifacts
    (the DSR/PBO are computed by the study, which alone holds the per-window return series).
    """
    dsr: dict[str, float] = {}
    ranking_csv = source_dir / "ranking.csv"
    if ranking_csv.exists():
        r = pd.read_csv(ranking_csv)
        if "dsr" in r.columns:
            dsr = {str(v): float(d) for v, d in zip(r["variation"], r["dsr"], strict=True)}
    pbo: float | None = None
    of_json = source_dir / "overfitting.json"
    if of_json.exists():
        pbo = json.loads(of_json.read_text(encoding="utf-8")).get("pbo")
    return dsr, pbo


def ranking(
    df: pd.DataFrame,
    *,
    min_frac_positive: float = _MIN_FRAC_POSITIVE,
    rpd_tolerance: float = _RPD_TOLERANCE,
    dsr_by_variation: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Per-variation decision table: the best training length per variation, return-first, gated.

    ``eligible`` is the *structure* gate (robust majority positive AND risk within tolerance of the
    best). ``dsr_ok`` is the *statistical* gate (deflated Sharpe clears ``_DSR_MIN``); it is only
    applied when the DSR is available. The auto-pick requires both.
    """
    valid = df.dropna(subset=["mean_oos_pct", "return_per_dd"])
    g = universe.per_config(valid).reset_index()
    best_rpd = float(g["mean_rpd"].max()) if not g.empty else 0.0
    gate_pos = g["frac_positive"] >= min_frac_positive
    gate_rpd = g["mean_rpd"] >= rpd_tolerance * best_rpd
    g["eligible"] = gate_pos & gate_rpd
    dsr_map = dsr_by_variation or {}
    g["dsr"] = g["variation"].map(dsr_map)  # NaN where unavailable
    g["dsr_ok"] = g["dsr"].isna() | (g["dsr"] >= _DSR_MIN)  # unknown DSR does not gate out
    # One row per variation: its best training length by return (what Stage 2 would pick).
    best_idx = g.groupby("variation")["mean_ret"].idxmax()
    return g.loc[best_idx].sort_values("mean_ret", ascending=False).reset_index(drop=True)


def _print_table(top: pd.DataFrame) -> str:
    """Print the ranking; return the auto-pick (highest-return, structure- AND DSR-eligible)."""
    print(
        f"\n  {'variation':14s} {'train':>5s} {'Rendite':>9s} {'Rend/DD':>8s} "
        f"{'%pos':>6s} {'DSR':>6s}  Gate"
    )
    auto = ""
    for _, r in top.iterrows():
        ok = bool(r["eligible"]) and bool(r["dsr_ok"])
        gate = "ok eligible" if ok else "   gated out"
        if ok and not auto:
            auto, gate = str(r["variation"]), "<< AUTO-PICK"
        dsr_txt = "  n/a" if pd.isna(r["dsr"]) else f"{r['dsr']:5.2f}"
        print(
            f"  {r['variation']:14s} {int(r['train_months']):>4d}m {r['mean_ret']:>+8.1f}% "
            f"{r['mean_rpd']:>8.2f} {r['frac_positive']:>5.0%} {dsr_txt:>6s}  {gate}"
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

    # The study alone holds the per-window return series, so it (not this stage) computes the DSR +
    # PBO; carry those artifacts into the run and surface them. Older studies may lack them.
    source_dir = study_csv.parent
    for artifact in ("ranking.csv", "overfitting.json"):
        if (source_dir / artifact).exists():
            shutil.copyfile(source_dir / artifact, run.file(artifact))
    dsr_by_variation, pbo = load_overfitting(source_dir)

    # Gates live in the study config (per strategy), not in this code -- nothing strategy-specific.
    cfg = load_config_module(args.config)
    min_pos = float(getattr(cfg, "SELECT_MIN_FRAC_POSITIVE", _MIN_FRAC_POSITIVE))
    rpd_tol = float(getattr(cfg, "SELECT_RPD_TOLERANCE", _RPD_TOLERANCE))

    top = ranking(
        df, min_frac_positive=min_pos, rpd_tolerance=rpd_tol, dsr_by_variation=dsr_by_variation
    )
    top.to_csv(run.file("edge_ranking.csv"), index=False)
    auto = _print_table(top)
    print(f"\n  Struktur-Gate: %pos>={min_pos:.0%} und Rend/DD>={rpd_tol:.0%} vom Besten.")
    if dsr_by_variation:
        n = len(dsr_by_variation)
        print(f"  Statistik-Gate: DSR>={_DSR_MIN:.2f} (nach Deflation um {n} Varianten)")
    else:
        print("  Statistik-Gate: DSR n/a - Studie neu laufen lassen fuer DSR/PBO.")
    if pbo is not None:
        verdict = "ok" if pbo <= _PBO_MAX else "ZU HOCH"
        print(f"  PBO (Overfitting-Wahrsch. der Auswahl): {pbo:.2f} <= {_PBO_MAX:.2f}? {verdict}")
    else:
        print("  PBO: n/a - Studie neu laufen lassen.")
    print(f"  Auto-Auswahl (hoechste Rendite unter eligible): {auto or '- (keine eligible)'}")

    select_auto = rb.cmd("select", "--run", str(run.path))
    rb.next_step(select_auto, "Universum waehlen (Auto) - oder --variation <name> anhaengen")


if __name__ == "__main__":
    main()
