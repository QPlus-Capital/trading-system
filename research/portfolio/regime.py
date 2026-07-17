"""Regime robustness: does the edge hold broadly, or does it hinge on one market regime?

Every trade is classified by the regime of *its own instrument* at the moment it opened, then the
edge (in R) is aggregated per regime. Two axes, plus named crises:
- **Volatility** -- rolling realized vol, split at the instrument's own 33/66 percentiles into
  {ruhig, mittel, stuermisch}.
- **Trend** -- Kaufman's efficiency ratio (|net move| / summed absolute moves), split the same way
  into {seitwaerts, mittel, trendig}. For a mean-reversion strategy this is the decisive cut:
  reversals should struggle when a market trends hard.
- **Crisis windows** -- performance inside well-known stress periods (COVID, 2022 rate hikes, ...).

Per-instrument terciles are self-calibrating (no magic thresholds) and make the buckets comparable
across markets. Read a broad positive expectancy across regimes as a plateau (robust); an edge
concentrated in one bucket as a fragile peak.

    uv run python -m research.portfolio.regime
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.portfolio.curves import DAY_NS
from research.portfolio.stats import edge_stats

_VOL_LABELS = ("ruhig", "mittel", "stuermisch")
_TREND_LABELS = ("seitwaerts", "mittel", "trendig")

# Named stress windows (data-covered). Reversal strategies are stressed by sharp directional moves.
CRISIS_WINDOWS: dict[str, tuple[str, str]] = {
    "China-Abwertung 2015": ("2015-08-01", "2015-10-31"),
    "Q4-2018-Selloff": ("2018-10-01", "2018-12-31"),
    "COVID-Crash 2020": ("2020-02-20", "2020-04-30"),
    "Zinswende 2022": ("2022-01-01", "2022-10-31"),
}


def realized_vol(closes: pd.Series, lookback: int) -> pd.Series:
    """Rolling standard deviation of daily log returns (NaN over the warmup)."""
    return np.log(closes.astype(float)).diff().rolling(lookback).std()


def efficiency_ratio(closes: pd.Series, lookback: int) -> pd.Series:
    """Kaufman efficiency ratio over ``lookback``: |net change| / summed absolute changes in [0, 1].

    1 = a clean one-way move (trend); near 0 = lots of motion but no progress (range/chop).
    """
    c = closes.astype(float)
    net = c.diff(lookback).abs()
    path = c.diff().abs().rolling(lookback).sum()
    return net / path.replace(0.0, np.nan)


def tercile_labels(values: pd.Series, labels: tuple[str, str, str]) -> pd.Series:
    """Label each value low/mid/high by the series' own 33/66 percentiles (NaN -> ``<NA>``)."""
    lo, hi = values.quantile(0.33), values.quantile(0.66)
    out = pd.Series(pd.NA, index=values.index, dtype="object")
    out[values <= lo] = labels[0]
    out[(values > lo) & (values <= hi)] = labels[1]
    out[values > hi] = labels[2]
    return out


def market_regime_by_day(daily_close: pd.Series, *, vol_lb: int, trend_lb: int) -> pd.DataFrame:
    """Per-day {vol_regime, trend_regime} labels for one instrument, indexed by day number."""
    return pd.DataFrame(
        {
            "vol_regime": tercile_labels(realized_vol(daily_close, vol_lb), _VOL_LABELS),
            "trend_regime": tercile_labels(efficiency_ratio(daily_close, trend_lb), _TREND_LABELS),
        }
    )


def label_trades(
    trades: pd.DataFrame,
    daily_closes: dict[str, pd.Series],
    *,
    vol_lb: int = 20,
    trend_lb: int = 20,
) -> pd.DataFrame:
    """Tag each trade with the vol/trend regime of its market at its open day (ffill to the day)."""
    out = trades.copy()
    out["day"] = (out["ts_opened"].to_numpy() // DAY_NS).astype(int)
    out["vol_regime"] = pd.NA
    out["trend_regime"] = pd.NA
    for market, group in out.groupby("market"):
        series = daily_closes.get(str(market))
        if series is None:
            continue
        reg = market_regime_by_day(series, vol_lb=vol_lb, trend_lb=trend_lb)
        for col in ("vol_regime", "trend_regime"):
            labels = reg[col].reindex(group["day"].to_numpy(), method="ffill")
            out.loc[group.index, col] = labels.to_numpy()
    return out


def regime_edge_table(
    labeled: pd.DataFrame, regime_col: str, *, r_col: str = "r", order: tuple[str, ...]
) -> pd.DataFrame:
    """Per-regime edge stats in R: trades, share, hit-rate, expectancy, profit-factor, total-R."""
    rows = []
    valid = labeled.dropna(subset=[regime_col])
    for name in order:
        r = valid.loc[valid[regime_col] == name, r_col].to_numpy(dtype=float)
        if len(r) == 0:
            continue
        stats = edge_stats(r)
        rows.append(
            {
                "regime": name,
                "trades": len(r),
                "share": len(r) / len(valid),
                "hit_rate": stats["hit_rate"],
                "expectancy_R": stats["expectancy"],
                "profit_factor": stats["profit_factor"],
                "total_R": float(r.sum()),
            }
        )
    return pd.DataFrame(rows)
