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

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.portfolio.curves import DAY_NS, load_daily_close  # noqa: E402
from research.portfolio.equity_report import edge_stats  # noqa: E402

_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
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


def _day_number(date: str) -> int:
    return int((pd.Timestamp(date, tz="UTC") - _EPOCH) // pd.Timedelta(days=1))


def crisis_table(labeled: pd.DataFrame, *, r_col: str = "r") -> pd.DataFrame:
    """Edge inside each named crisis window: trades, total-R, expectancy, hit-rate, worst trade."""
    day = labeled["ts_opened"].to_numpy() // DAY_NS
    rows = []
    for name, (start, end) in CRISIS_WINDOWS.items():
        mask = (day >= _day_number(start)) & (day <= _day_number(end))
        r = labeled.loc[mask, r_col].to_numpy(dtype=float)
        rows.append(
            {
                "crisis": name,
                "trades": len(r),
                "total_R": float(r.sum()) if len(r) else 0.0,
                "expectancy_R": float(r.mean()) if len(r) else 0.0,
                "hit_rate": float((r > 0).mean()) if len(r) else 0.0,
                "worst_R": float(r.min()) if len(r) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def plot_regime(
    vol_tbl: pd.DataFrame, trend_tbl: pd.DataFrame, crisis_tbl: pd.DataFrame, out: Path
) -> None:
    """Expectancy (R) per volatility + trend regime, and total-R per crisis window."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    for ax, tbl, title in [
        (axes[0], vol_tbl, "Erwartung/Trade (R) nach Volatilitaet"),
        (axes[1], trend_tbl, "Erwartung/Trade (R) nach Trendstaerke"),
    ]:
        colors = ["tab:green" if v >= 0 else "tab:red" for v in tbl["expectancy_R"]]
        ax.bar(tbl["regime"], tbl["expectancy_R"], color=colors)
        ax.axhline(0, color="0.4", linewidth=0.8)
        ax.set_title(title)
        ax.set_ylabel("Erwartung je Trade (R)")
        for i, (e, n) in enumerate(zip(tbl["expectancy_R"], tbl["trades"], strict=True)):
            ax.annotate(f"n={n}", (i, e), ha="center", va="bottom" if e >= 0 else "top", fontsize=9)
        ax.grid(True, axis="y", alpha=0.25)
    colors = ["tab:green" if v >= 0 else "tab:red" for v in crisis_tbl["total_R"]]
    axes[2].barh(crisis_tbl["crisis"], crisis_tbl["total_R"], color=colors)
    axes[2].axvline(0, color="0.4", linewidth=0.8)
    axes[2].set_title("Gesamt-R in Krisenfenstern")
    axes[2].set_xlabel("Summe R")
    axes[2].grid(True, axis="x", alpha=0.25)
    fig.suptitle(
        "Regime-Robustheit -- no_bb_wpr, 9 Maerkte, netto (Terzile je Instrument)", fontsize=12
    )
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    """Re-run the frozen config full-history (net of costs), then report the edge per regime."""
    from core.broker import MEX_ATLANTIC, load_swap_snapshot, swap_snapshot_path

    from research.engine.config import load_config_module
    from research.portfolio.equity_report import _REPO_ROOT, _market_trades

    cfg = load_config_module(_REPO_ROOT / "config" / "live" / "paper_rsi_wpr_bb.py")
    switches = dict(cfg.STRATEGY_SWITCHES)
    snap = swap_snapshot_path(MEX_ATLANTIC.name)
    broker = MEX_ATLANTIC.with_swaps(load_swap_snapshot(snap)) if snap.exists() else MEX_ATLANTIC

    frames, daily_closes = [], {}
    for factory, csv, leverage, sl, tp in cfg.MARKETS:
        name = str(factory().raw_symbol)
        print(f"backtesting {name} (full history) ...")
        frames.append(_market_trades(factory, csv, leverage, sl, tp, switches, broker))
        daily_closes[name] = load_daily_close(csv)
    trades = pd.concat(frames, ignore_index=True)
    labeled = label_trades(trades, daily_closes)

    vol_tbl = regime_edge_table(labeled, "vol_regime", order=_VOL_LABELS)
    trend_tbl = regime_edge_table(labeled, "trend_regime", order=_TREND_LABELS)
    crisis_tbl = crisis_table(labeled)

    out_dir = _REPO_ROOT / "reports" / "equity"
    plot_regime(vol_tbl, trend_tbl, crisis_tbl, out_dir / "regime.png")

    pd.options.display.float_format = lambda v: f"{v:,.3f}"
    print("\n===== edge by VOLATILITY regime (R) =====")
    print(vol_tbl.to_string(index=False))
    print("\n===== edge by TREND regime (R) =====")
    print(trend_tbl.to_string(index=False))
    print("\n===== edge in CRISIS windows (R) =====")
    print(crisis_tbl.to_string(index=False))
    print(f"\nchart: {out_dir / 'regime.png'}")


if __name__ == "__main__":
    main()
