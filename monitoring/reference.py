"""Load the backtest reference and its Monte-Carlo expectation band for the live comparison.

The reference is the staged framework's full-history trade stream
(``reports/research/run_*/full_history_trades.csv``), net of the TTP swap. Everything is in
**R-multiples** (per-trade return in units of risk), so the live account (any size / broker) is
comparable to the backtest without a currency/scale mismatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from research.portfolio.stats import edge_stats


def load_reference(trades_csv: str | Path) -> dict[str, Any]:
    """Backtest edge metrics (overall + per market) + per-trade R from the framework stream.

    Reads the framework trade stream (columns ``market``, ``r`` and optional ``swap_r``) and nets
    the swap onto R, so every metric is net of the overnight cost of carry.
    """
    df = pd.read_csv(trades_csv)
    r = df["r"].to_numpy(dtype=float)
    if "swap_r" in df.columns:
        r = r + df["swap_r"].to_numpy(dtype=float)  # net of the realized swap
    df = df.assign(_net_r=r)
    return {
        "trades": len(df),
        "overall": edge_stats(r),
        "per_market": {
            str(m): edge_stats(g["_net_r"].to_numpy(dtype=float)) for m, g in df.groupby("market")
        },
        "r_multiples": r,
    }


def mc_band(r: np.ndarray, n_trades: int, *, n_sims: int = 2000, seed: int = 7) -> pd.DataFrame:
    """Expected cumulative-R path band (5th / median / 95th) over ``n_trades`` trades.

    Bootstraps the backtest R-multiples: 'if the backtest edge held, where should a live account
    of this many trades be?'. Overlay the live cumulative R on it to see if live tracks expectation.
    """
    n = max(int(n_trades), 1)
    rng = np.random.default_rng(seed)
    paths = np.cumsum(rng.choice(r, size=(n_sims, n), replace=True), axis=1)
    return pd.DataFrame(
        {
            "trade": np.arange(1, n + 1),
            "p5": np.percentile(paths, 5, axis=0),
            "p50": np.percentile(paths, 50, axis=0),
            "p95": np.percentile(paths, 95, axis=0),
        }
    )
