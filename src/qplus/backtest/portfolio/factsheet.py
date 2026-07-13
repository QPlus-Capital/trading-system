"""End-of-run fact sheet: the consistent metrics matrix for a chosen variant.

Everything is measured in R (scale- and sizing-invariant); the flat-vs-compound split enters
ONLY the two money rows -- annualised return and max drawdown -- where both are shown side by
side. Per-market and per-year use the flat % lens (a linear rescale of R: ``sum(R) * risk_frac``),
never mixed with compound figures. Regime tables report edge quality in R.

Two windows are compared: the FULL history (all data, every crisis) and the reserved HOLDOUT
(genuine out-of-sample). The full-history stream is produced once by the portfolio stage (for the
tail cap) and reused here, so the fact sheet costs no extra backtests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from qplus.backtest.portfolio import regime
from qplus.backtest.portfolio.curves import DAY_NS, align_prices
from qplus.backtest.portfolio.equity_report import edge_stats, risk_stats
from qplus.backtest.portfolio.risk import AccountProfile, flat_base_pnl
from qplus.backtest.portfolio.sizing import flat, simulate

# Must match regime.py's _VOL_LABELS / _TREND_LABELS (low -> high on each axis).
_VOL_ORDER = ("ruhig", "mittel", "stuermisch")
_TREND_ORDER = ("seitwaerts", "mittel", "trendig")


@dataclass(frozen=True)
class Money:
    """The two sizing-dependent numbers for one (window, sizing) cell."""

    ann_return_pct: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class Edge:
    """Sizing-invariant edge / character for one window (identical for flat and compound)."""

    sharpe: float
    hit_rate: float
    profit_factor: float
    payoff: float
    expectancy_r: float
    avg_hold_days: float
    median_hold_days: float
    trades: int


@dataclass(frozen=True)
class WindowResult:
    """One window (full or holdout): both sizings' money numbers, the shared edge, the curves."""

    flat: Money
    compound: Money
    edge: Edge
    equity_flat: pd.Series
    equity_comp: pd.Series


@dataclass(frozen=True)
class FactSheet:
    risk_pct: float
    full: WindowResult
    holdout: WindowResult
    per_market: pd.DataFrame  # market, trades, ret_pct (flat), share_pct, hit_rate, avg_r
    per_year: pd.DataFrame  # year, ret_pct (flat), trades
    regime_vol: pd.DataFrame  # regime, trades, share, hit_rate, expectancy_R, ret_pct (flat)
    regime_trend: pd.DataFrame
    holdout_start: pd.Timestamp


def _daily_equity(
    trades: pd.DataFrame,
    daily_close: dict[str, pd.Series],
    account: AccountProfile,
    *,
    compound: bool,
) -> pd.Series:
    """Mark-to-market daily equity (incl. floating) via the tested simulate, at the live risk."""
    t = trades.copy()
    ns_open = pd.to_datetime(t["ts_opened"]).astype("int64")
    ns_close = pd.to_datetime(t["ts_closed"]).astype("int64")
    t["od"] = ns_open // DAY_NS
    t["cd"] = ns_close // DAY_NS
    t["pnl_base"] = flat_base_pnl(t, account)  # r * base_risk_frac * start (flat EUR at live risk)
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}
    _real, eq, _sizes = simulate(
        t,
        prices,
        d0,
        d1,
        account.start_balance,
        account.trailing_hard,
        flat(1.0),
        compound=compound,
    )
    idx = pd.to_datetime(np.arange(d0, d1 + 1) * DAY_NS)
    return pd.Series(eq, index=idx)


def _money(equity: pd.Series, start: float, *, compound: bool) -> Money:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    if compound:  # geometric: risk tracks equity, returns compound
        ann = (float(equity.iloc[-1]) / float(equity.iloc[0])) ** (1 / years) - 1
    else:  # flat: linear off the fixed start balance
        ann = (float(equity.iloc[-1]) - start) / start / years
    maxdd = float(((equity - equity.cummax()) / equity.cummax()).min())
    return Money(round(ann * 100, 1), round(maxdd * 100, 2))


def _edge(trades: pd.DataFrame, equity_flat: pd.Series, start: float) -> Edge:
    r = trades["r"].to_numpy(dtype=float)
    es = edge_stats(r)  # expectancy here is mean(R) since we pass R directly
    sharpe = risk_stats(equity_flat, start_balance=start)["sharpe"]
    hold = pd.to_datetime(trades["ts_closed"]) - pd.to_datetime(trades["ts_opened"])
    hold_days = hold.dt.total_seconds().to_numpy() / 86400.0
    return Edge(
        sharpe=round(sharpe, 2),
        hit_rate=es["hit_rate"],
        profit_factor=es["profit_factor"],
        payoff=es["payoff"],
        expectancy_r=round(float(es["expectancy"]), 3),
        avg_hold_days=round(float(hold_days.mean()), 1),
        median_hold_days=round(float(np.median(hold_days)), 1),
        trades=len(r),
    )


def _window(
    trades: pd.DataFrame, daily_close: dict[str, pd.Series], account: AccountProfile
) -> WindowResult:
    eq_f = _daily_equity(trades, daily_close, account, compound=False)
    eq_c = _daily_equity(trades, daily_close, account, compound=True)
    start = account.start_balance
    return WindowResult(
        flat=_money(eq_f, start, compound=False),
        compound=_money(eq_c, start, compound=True),
        edge=_edge(trades, eq_f, start),
        equity_flat=eq_f,
        equity_comp=eq_c,
    )


def _per_market(trades: pd.DataFrame, risk_frac: float) -> pd.DataFrame:
    g = trades.groupby("market")["r"]
    out = pd.DataFrame(
        {
            "trades": g.size(),
            "total_r": g.sum(),
            "hit_rate": g.apply(lambda x: float((x > 0).mean())),
            "avg_r": g.mean(),
        }
    )
    out["ret_pct"] = out["total_r"] * risk_frac * 100.0  # flat % of start balance
    out["share_pct"] = out["total_r"] / out["total_r"].sum() * 100.0
    return out.sort_values("total_r", ascending=False).reset_index()


def _per_year(trades: pd.DataFrame, risk_frac: float) -> pd.DataFrame:
    t = trades.copy()
    t["year"] = pd.to_datetime(t["ts_closed"]).dt.year
    g = t.groupby("year")["r"]
    out = pd.DataFrame({"trades": g.size(), "ret_pct": g.sum() * risk_frac * 100.0})
    return out.reset_index()


def _regime(
    labeled: pd.DataFrame, col: str, order: tuple[str, ...], risk_frac: float
) -> pd.DataFrame:
    tbl = regime.regime_edge_table(labeled, col, order=order)
    if not tbl.empty:
        tbl["ret_pct"] = tbl["total_R"] * risk_frac * 100.0  # flat % contribution
    return tbl


def render_terminal(fs: FactSheet) -> str:
    """The fact sheet as an aligned plain-text block for the verdict stage."""
    f, h = fs.full, fs.holdout
    lines = ["\n  KENNZAHLEN - Volle Historie vs. Holdout, flach vs. compound\n"]
    lines.append(
        f"  {'Rendite & Risiko':26s}{'Voll flach':>12s}{'Voll comp':>12s}"
        f"{'Hold flach':>12s}{'Hold comp':>12s}"
    )
    ret = (
        f.flat.ann_return_pct,
        f.compound.ann_return_pct,
        h.flat.ann_return_pct,
        h.compound.ann_return_pct,
    )
    dd = (
        f.flat.max_drawdown_pct,
        f.compound.max_drawdown_pct,
        h.flat.max_drawdown_pct,
        h.compound.max_drawdown_pct,
    )
    lines.append(f"    {'Rendite p.a.':24s}" + "".join(f"{v:>+11.1f}%" for v in ret))
    lines.append(f"    {'Max Drawdown':24s}" + "".join(f"{v:>11.2f}%" for v in dd))
    lines.append(f"\n  {'Edge & Charakter (invariant)':40s}{'Volle Historie':>16s}{'Holdout':>12s}")
    ed = [
        ("Sharpe (annualisiert)", f"{f.edge.sharpe:.2f}", f"{h.edge.sharpe:.2f}"),
        ("Trefferquote", f"{f.edge.hit_rate * 100:.1f}%", f"{h.edge.hit_rate * 100:.1f}%"),
        ("Profit-Faktor", f"{f.edge.profit_factor:.2f}", f"{h.edge.profit_factor:.2f}"),
        ("Payoff", f"{f.edge.payoff:.2f} : 1", f"{h.edge.payoff:.2f} : 1"),
        ("Erwartung / Trade", f"{f.edge.expectancy_r:+.3f} R", f"{h.edge.expectancy_r:+.3f} R"),
        ("Ø Haltedauer", f"{f.edge.avg_hold_days:.1f} T", f"{h.edge.avg_hold_days:.1f} T"),
        ("Trades", f"{f.edge.trades:,}", f"{h.edge.trades:,}"),
    ]
    for label, fv, hv in ed:
        lines.append(f"    {label:38s}{fv:>16s}{hv:>12s}")
    lines.append("\n  Beitrag je Markt (flach %, volle Historie)")
    for r in fs.per_market.itertuples():
        lines.append(
            f"    {r.market:8s}{r.ret_pct:>+9.1f}%  ({r.share_pct:>4.1f}%)  "
            f"hit {r.hit_rate * 100:>2.0f}%  {r.avg_r:+.2f}R"
        )
    for axis, tbl in (("Volatilitaet", fs.regime_vol), ("Trend", fs.regime_trend)):
        if tbl.empty:
            continue
        lines.append(f"\n  Regime - {axis} (volle Historie)")
        for r in tbl.itertuples():
            lines.append(
                f"    {r.regime:12s} hit {r.hit_rate * 100:>4.1f}%  Erw {r.expectancy_R:+.3f}R  "
                f"Beitrag {r.ret_pct:>+7.1f}%"
            )
    return "\n".join(lines)


def compute_factsheet(
    full_trades: pd.DataFrame,
    holdout_trades: pd.DataFrame,
    daily_close: dict[str, pd.Series],
    account: AccountProfile,
) -> FactSheet:
    """Assemble the full fact sheet from the full-history and holdout trade streams."""
    risk_frac = account.base_risk_frac
    labeled = regime.label_trades(full_trades, daily_close)
    return FactSheet(
        risk_pct=round(risk_frac * 100, 3),
        full=_window(full_trades, daily_close, account),
        holdout=_window(holdout_trades, daily_close, account),
        per_market=_per_market(full_trades, risk_frac),
        per_year=_per_year(full_trades, risk_frac),
        regime_vol=_regime(labeled, "vol_regime", _VOL_ORDER, risk_frac),
        regime_trend=_regime(labeled, "trend_regime", _TREND_ORDER, risk_frac),
        holdout_start=pd.to_datetime(holdout_trades["ts_opened"]).min(),
    )
