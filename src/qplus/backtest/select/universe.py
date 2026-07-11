"""Stage 2 -- universe selection + global structure.

Consumes the Stage 1 study table (one row per instrument x variation x training length,
carrying the risk-adjusted ``return_per_dd`` and friends) and makes two joined decisions:

1. **Global structure:** pick the single (variation, training-length) with the highest
   **return** *averaged across instruments* -- but only among configs whose **risk is
   tolerable**: OOS-positive on a robust majority of instruments (cross-instrument
   consistency) AND within a tolerance of the best risk-adjusted return (so more return is
   never bought with reckless drawdown). Return-first is deliberate: the goal is to make
   money; the two gates keep the risk acceptable and robust. One structure for all markets,
   not per-market (the locked design decision).
2. **Universe:** under that structure, keep the instruments whose own risk-adjusted edge
   clears thresholds; drop the weak / inconsistent ones.

Pure pandas -- no backtest. See ``docs/methodology.md`` (Stage 3, selection).
"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Selection:
    """The chosen global structure and tradeable universe."""

    variation: str
    train_months: int
    instruments: list[str]


def _per_config(df: pd.DataFrame) -> pd.DataFrame:
    """Return + risk summary per (variation, train_months), aggregated across instruments."""
    return df.groupby(["variation", "train_months"]).agg(
        mean_ret=("mean_oos_pct", "mean"),  # the objective: cross-instrument OOS return
        mean_rpd=("return_per_dd", "mean"),  # the risk-adjusted tolerability gate
        worst_rpd=("return_per_dd", "min"),
        frac_positive=("mean_oos_pct", lambda s: float((s > 0).mean())),
    )


def select_structure(
    df: pd.DataFrame, *, min_frac_positive: float = 0.9, rpd_tolerance: float = 0.85
) -> tuple[str, int]:
    """Pick the global (variation, train_months) with the highest **return**, risk permitting.

    Return-first, because the goal is to make money. Two gates keep the risk tolerable:
    a config is eligible only if it is OOS-positive on at least ``min_frac_positive`` of
    instruments (robustness) AND its risk-adjusted return (``mean_rpd``) is at least
    ``rpd_tolerance`` of the best config's (so a bit more return is never taken at the cost of
    a much worse drawdown profile). Among the eligible, the highest mean OOS return wins. If
    none qualify, fall back to the full pool so a choice is always returned.
    """
    g = _per_config(df)
    best_rpd = float(g["mean_rpd"].max())
    eligible = g[
        (g["frac_positive"] >= min_frac_positive) & (g["mean_rpd"] >= rpd_tolerance * best_rpd)
    ]
    pool = eligible if not eligible.empty else g
    best = pool["mean_ret"].idxmax()  # (variation, train_months) with the most return
    return str(best[0]), int(best[1])


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


def select(
    df: pd.DataFrame,
    *,
    min_frac_positive: float = 0.9,
    rpd_tolerance: float = 0.85,
    min_return_per_dd: float = 1.0,
    min_pct_profitable: float = 60.0,
) -> Selection:
    """Run both selections: global structure (return-first, risk-gated), then the universe."""
    variation, train_months = select_structure(
        df, min_frac_positive=min_frac_positive, rpd_tolerance=rpd_tolerance
    )
    instruments = select_universe(
        df,
        variation,
        train_months,
        min_return_per_dd=min_return_per_dd,
        min_pct_profitable=min_pct_profitable,
    )
    return Selection(variation=variation, train_months=train_months, instruments=instruments)
