"""Research-explorer data: slice + aggregate the study results for the dashboard's research view.

The study (``reports/study/<run>/study.csv``) is one row per (instrument x variation x
train_months) with the walk-forward metrics. These pure helpers pick the latest study, drop
failed tasks, and build the two views the explorer renders: a variation x instrument heatmap
of a chosen metric, and a variation ranking averaged across markets.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# label -> (column, neutral midpoint for the diverging color, higher_is_better)
METRICS: dict[str, tuple[str, float | None, bool]] = {
    "Return / drawdown": ("return_per_dd", 1.0, True),
    "OOS return %/window": ("mean_oos_pct", 0.0, True),
    "Max drawdown %": ("oos_maxdd_pct", None, False),
    "% profitable windows": ("pct_profitable", 50.0, True),
    "Norm. walk-forward eff.": ("wfe_norm", 0.5, True),
    "OOS trades": ("oos_trades", None, True),
}


def latest_study_csv(reports_dir: str | Path) -> Path | None:
    """Path of the most recent ``study.csv`` under ``reports/study/`` (timestamped run folders)."""
    cands = sorted(Path(reports_dir).glob("study/*/study.csv"))
    return cands[-1] if cands else None


def load_study(csv: str | Path) -> pd.DataFrame:
    """Load a study table, dropping tasks that errored (so charts see only valid results)."""
    df = pd.read_csv(csv)
    if "error" in df.columns:
        df = df[df["error"].isna()].drop(columns=["error"])
    return df.reset_index(drop=True)


def variant_ranking(df: pd.DataFrame, train_months: int, metric_col: str) -> pd.DataFrame:
    """Mean of ``metric_col`` per variation across instruments, for one training length."""
    sub = df[df["train_months"] == train_months]
    ranked = sub.groupby("variation")[metric_col].mean().reset_index()
    return ranked.sort_values(metric_col, ascending=False).reset_index(drop=True)
