"""Stage 2 candidate aggregation and per-market universe filtering.

The strict global structure decision lives only in :mod:`research.stages.select`, where the
lineage-bound SPA, Romano-Wolf, MCS, structure, and complexity evidence is available. This module
provides its descriptive per-candidate aggregates and filters markets after that decision.
"""

import pandas as pd


def per_config(df: pd.DataFrame) -> pd.DataFrame:
    """Return + risk summary per (variation, train_months), aggregated across instruments."""
    return df.groupby(["variation", "train_months"]).agg(
        mean_ret=("mean_oos_pct", "mean"),  # the objective: cross-instrument OOS return
        mean_rpd=("return_per_dd", "mean"),  # the risk-adjusted tolerability gate
        worst_rpd=("return_per_dd", "min"),
        frac_positive=("mean_oos_pct", lambda s: float((s > 0).mean())),
    )


def select_universe(
    df: pd.DataFrame,
    variation: str,
    train_months: int,
    *,
    min_return_per_dd: float = 1.0,
    min_pct_profitable: float = 60.0,
) -> list[str]:
    """Instruments whose own risk-adjusted edge clears the thresholds under the structure."""
    sub = df[(df["variation"] == variation) & (df["train_months"] == train_months)]
    keep = sub[
        (sub["return_per_dd"] >= min_return_per_dd)
        & (sub["mean_oos_pct"] > 0)
        & (sub["pct_profitable"] >= min_pct_profitable)
    ]
    return sorted(str(x) for x in keep["instrument"].tolist())
