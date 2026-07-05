"""Illustrative portfolio equity report for the FROZEN live config.

Runs a full-history backtest of the frozen strategy (``config/live/paper_rsi_wpr_bb.py``:
no_bb_wpr, fixed per-market SL/TP) on each of the 9 markets, then builds ONE shared account
that trades all of them at **flat** risk (a fixed fraction of the starting balance -- exactly
the live sizing). The output is an equity-over-time curve starting at the chosen balance, with
the reserved-holdout cutoff marked, plus a Monte-Carlo fan over trade order.

This is an *illustration of the chosen config's character* over the full data span (it includes
in-sample periods, so it is NOT the out-of-sample validation -- that is the 95.4% holdout number
from the pipeline). The everything-left-of-the-line part was used for fitting; only the part to
the right of the marked cutoff is genuinely out-of-sample.

Sizing is made independent of the backtest's own compounding by working in **R-multiples**: each
trade's realized PnL (costs included) is divided by the risk it took, giving a size-invariant,
cost-inclusive return in risk units; the flat account then books ``risk_amount * R`` per trade.

Run from the repo root::

    uv run python -m qplus.backtest.portfolio.equity_report
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from qplus.backtest.config import load_config_module  # noqa: E402
from qplus.backtest.foundation.recipe import SweepRecipe  # noqa: E402
from qplus.backtest.portfolio.trades import timed_trades_from_report  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[4]
_START_BALANCE = 200_000.0  # the study's account size (what the feasibility was scored on)
_HOLDOUT_MONTHS = 24  # reserved tail marked on the chart (matches the study config)
_BASE_RISK = 0.01  # the backtest sizes each trade at 1% of equity; used to recover R-multiples


def r_multiples(pnls: Sequence[float], *, start: float = _START_BALANCE) -> list[float]:
    """Size-invariant, cost-inclusive return per trade (realized PnL / the risk it took).

    The backtest sizes each position at ``_BASE_RISK`` of the *current* equity, so we walk the
    per-market equity forward to recover the risk each trade actually took and divide the PnL by
    it. The resulting R-multiples no longer depend on the backtest's compounding, so they can be
    re-booked at any flat risk on a shared account.
    """
    equity = start
    out: list[float] = []
    for pnl in pnls:
        risk = _BASE_RISK * equity
        out.append(pnl / risk if risk > 0 else 0.0)
        equity += pnl
    return out


def flat_portfolio(trades: pd.DataFrame, *, risk_amount: float) -> pd.DataFrame:
    """Combine all markets' trades into one flat-risk account, ordered by close time.

    ``trades`` needs columns ``ts_closed`` (ns) and ``r`` (per-trade R-multiple). Each trade
    books ``risk_amount * r`` into a shared account starting at ``_START_BALANCE``.
    """
    t = trades.sort_values("ts_closed").reset_index(drop=True)
    pnl = risk_amount * t["r"].to_numpy(dtype=float)
    equity = _START_BALANCE + np.cumsum(pnl)
    return pd.DataFrame(
        {"date": pd.to_datetime(t["ts_closed"], unit="ns"), "equity": equity, "market": t["market"]}
    )


def _market_trades(
    factory: Any, csv: str, leverage: float, sl: float, tp: float, switches: dict[str, Any]
) -> pd.DataFrame:
    """Full-history backtest of one market at the frozen config -> timed trades with R-multiples."""
    from nautilus_trader.backtest.node import BacktestNode

    recipe = SweepRecipe(
        factory(),
        csv,
        leverage=leverage,
        config_overrides={**switches, "stop_loss_pct": sl, "take_profit_pct": tp},
    )
    node = BacktestNode(configs=[recipe.build_run_config({})])  # start/end None -> full history
    try:
        node.run()
        pos = node.get_engines()[0].trader.generate_positions_report()
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    rows = timed_trades_from_report(pos, str(recipe.INSTRUMENT.raw_symbol))
    df = pd.DataFrame(rows).sort_values("ts_closed").reset_index(drop=True)
    df["r"] = r_multiples(df["pnl_base"].tolist())
    return df


def plot_equity(
    curve: pd.DataFrame, holdout_start: pd.Timestamp, risk_pct: float, out: Path
) -> None:
    """Equity over time, starting at the initial balance, with the OOS-holdout cutoff marked."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        curve["date"], curve["equity"], color="tab:blue", linewidth=1.6, label="portfolio equity"
    )
    ax.axhline(_START_BALANCE, color="0.6", linewidth=0.8, linestyle=":")
    ax.axvline(
        holdout_start,
        color="tab:red",
        linewidth=1.2,
        linestyle="--",
        label="holdout start (out-of-sample -->)",
    )
    ax.fill_betweenx(
        [curve["equity"].min(), curve["equity"].max()],
        holdout_start,
        curve["date"].max(),
        color="tab:red",
        alpha=0.05,
    )
    ax.set_title(
        f"Frozen config (no_bb_wpr, 9 markets) -- flat {risk_pct:.2f}% risk, "
        f"start EUR {_START_BALANCE:,.0f}\n"
        "illustrative full-history backtest; only right of the red line is out-of-sample"
    )
    ax.set_xlabel("year")
    ax.set_ylabel("account equity (EUR)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def plot_monte_carlo(r: np.ndarray, risk_amount: float, out: Path, n_sims: int = 2000) -> None:
    """Bootstrap the trade ORDER to show how much the final equity depends on luck/sequence."""
    rng = np.random.default_rng(7)
    n = len(r)
    paths = np.empty((n_sims, n + 1))
    paths[:, 0] = _START_BALANCE
    for i in range(n_sims):
        shuffled = rng.choice(r, size=n, replace=True)
        paths[i, 1:] = _START_BALANCE + np.cumsum(risk_amount * shuffled)
    x = np.arange(n + 1)
    fig, ax = plt.subplots(figsize=(12, 6))
    for i in range(min(300, n_sims)):
        ax.plot(x, paths[i], color="0.75", linewidth=0.3, alpha=0.15)
    ax.plot(x, np.percentile(paths, 50, axis=0), color="tab:blue", linewidth=1.8, label="median")
    ax.plot(
        x,
        np.percentile(paths, 5, axis=0),
        color="tab:blue",
        linewidth=1.0,
        linestyle="--",
        label="5th / 95th pct",
    )
    ax.plot(x, np.percentile(paths, 95, axis=0), color="tab:blue", linewidth=1.0, linestyle="--")
    ax.axhline(_START_BALANCE, color="0.6", linewidth=0.8, linestyle=":")
    ax.set_title("Monte-Carlo: same trades, reshuffled order (bootstrap) -- sequence risk")
    ax.set_xlabel("trade #")
    ax.set_ylabel("account equity (EUR)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def daily_equity(
    trades: pd.DataFrame,
    risk_amount: float,
    daily_close: dict[str, pd.Series],
    *,
    start_balance: float = _START_BALANCE,
) -> pd.Series:
    """Daily mark-to-market equity (flat sizing), INCLUDING open positions' floating PnL.

    Uses the tested ``base_curves`` machinery: each trade's flat contribution (risk_amount * R)
    is booked as realized on close and marked to the daily price while open. The result -- unlike
    the realized-only trade curve -- shows the real intraday swings, so Sharpe / drawdown computed
    on it are honest (not flattered by ignoring floating losses).
    """
    from qplus.backtest.portfolio.curves import DAY_NS, align_prices, base_curves, to_day

    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    t["pnl_base"] = risk_amount * t["r"]  # flat EUR contribution per trade
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}
    realized, unrealized = base_curves(t, prices, d0, d1)
    idx = pd.to_datetime(np.arange(d0, d1 + 1) * DAY_NS)
    return pd.Series(start_balance + realized + unrealized, index=idx)


def edge_stats(pnl: np.ndarray) -> dict[str, float]:
    """Trade-level edge metrics: hit rate, payoff, profit factor, expectancy, avg win/loss."""
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    n = len(pnl)
    return {
        "trades": float(n),
        "hit_rate": len(wins) / n if n else 0.0,
        "payoff": (wins.mean() / -losses.mean()) if len(wins) and len(losses) else 0.0,
        "profit_factor": (wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "expectancy": float(pnl.mean()) if n else 0.0,
    }


def risk_stats(equity: pd.Series, *, start_balance: float = _START_BALANCE) -> dict[str, float]:
    """Return / drawdown / Sharpe from the floating-inclusive daily equity (honest risk view).

    Returns use the fixed ``start_balance`` base (correct for flat sizing); Sharpe is annualised
    from daily returns; max drawdown is the worst peak-to-trough of the mark-to-market equity.
    """
    ret = equity.diff().dropna().to_numpy() / start_balance
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] - equity.iloc[0]) / start_balance
    peak = equity.cummax()
    std = float(ret.std(ddof=1)) if len(ret) > 1 else 0.0
    return {
        "years": years,
        "total_return": total_return,
        "annual_return": total_return / years,
        "max_drawdown": float(((equity - peak) / peak).min()),
        "sharpe": float(ret.mean() / std * np.sqrt(252)) if std > 0 else 0.0,
    }


def plot_scorecard(full: dict[str, float], oos: dict[str, float], out: Path) -> None:
    """Render the key metrics as a table: full history vs. out-of-sample (holdout)."""
    rows = [
        ("Zeitraum", f"{full['years']:.1f} Jahre", f"{oos['years']:.1f} Jahre"),
        ("Trades", f"{full['trades']:,.0f}", f"{oos['trades']:,.0f}"),
        ("Trefferquote", f"{full['hit_rate']:.1%}", f"{oos['hit_rate']:.1%}"),
        ("Payoff (Chance/Risiko)", f"{full['payoff']:.2f} : 1", f"{oos['payoff']:.2f} : 1"),
        ("Profit-Faktor", f"{full['profit_factor']:.2f}", f"{oos['profit_factor']:.2f}"),
        ("Durchschn. Gewinn", f"{full['avg_win']:,.0f} EUR", f"{oos['avg_win']:,.0f} EUR"),
        ("Durchschn. Verlust", f"{full['avg_loss']:,.0f} EUR", f"{oos['avg_loss']:,.0f} EUR"),
        ("Erwartung / Trade", f"{full['expectancy']:,.0f} EUR", f"{oos['expectancy']:,.0f} EUR"),
        ("Gesamtrendite", f"{full['total_return']:+.1%}", f"{oos['total_return']:+.1%}"),
        ("Rendite p.a.", f"{full['annual_return']:+.1%}", f"{oos['annual_return']:+.1%}"),
        ("Max Drawdown (Equity)", f"{full['max_drawdown']:.1%}", f"{oos['max_drawdown']:.1%}"),
        ("Sharpe (annualisiert)", f"{full['sharpe']:.2f}", f"{oos['sharpe']:.2f}"),
    ]
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.axis("off")
    ax.set_title(
        "Kennzahlen -- no_bb_wpr, 9 Maerkte, flach 0.15% Risiko (Start EUR 200,000)\n"
        "volle Historie enthaelt In-Sample; Out-of-Sample = unberuehrter Holdout. "
        "Sharpe/DD auf Mark-to-Market-Equity (inkl. offener Buchverluste).",
        fontsize=11,
        pad=18,
    )
    table = ax.table(
        cellText=[[r[1], r[2]] for r in rows],
        rowLabels=[r[0] for r in rows],
        colLabels=["volle Historie", "Out-of-Sample (Holdout)"],
        cellLoc="center",
        rowLoc="left",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.9)
    for (row, col), cell in table.get_celld().items():
        if row == 0:  # header
            cell.set_facecolor("#2b5c8a")
            cell.set_text_props(color="white", fontweight="bold")
        elif col == 1:  # out-of-sample column highlighted
            cell.set_facecolor("#eef4fb")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_market_contributions(trades: pd.DataFrame, risk_amount: float, out: Path) -> None:
    """Bar chart: each market's total flat PnL contribution (risk_amount * sum of its R)."""
    by_market = (trades.groupby("market")["r"].sum() * risk_amount).sort_values()
    colors = ["tab:red" if v < 0 else "tab:green" for v in by_market]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(by_market.index.tolist(), by_market.to_numpy(), color=colors)
    ax.axvline(0, color="0.4", linewidth=0.8)
    ax.set_title("Contribution to portfolio profit by market (flat sizing, full history)")
    ax.set_xlabel("total PnL contribution (EUR)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main() -> None:
    """Run all 9 markets, build the flat portfolio, and save the charts + the trade stream."""
    cfg = load_config_module(_REPO_ROOT / "config" / "live" / "paper_rsi_wpr_bb.py")
    risk_pct = float(cfg.RISK_PER_TRADE_PCT)
    risk_amount = risk_pct / 100.0 * _START_BALANCE
    switches = dict(cfg.STRATEGY_SWITCHES)

    frames = []
    for factory, csv, leverage, sl, tp in cfg.MARKETS:
        name = str(factory().raw_symbol)
        print(f"backtesting {name} (full history, SL {sl}% / TP {tp}%) ...")
        frames.append(_market_trades(factory, csv, leverage, sl, tp, switches))
    trades = pd.concat(frames, ignore_index=True)

    from qplus.backtest.portfolio.curves import load_daily_close

    curve = flat_portfolio(trades, risk_amount=risk_amount)
    curve["pnl"] = np.diff(
        np.concatenate([[_START_BALANCE], curve["equity"].to_numpy(dtype=float)])
    )
    holdout_start = curve["date"].max() - pd.DateOffset(months=_HOLDOUT_MONTHS)

    # Honest risk view: daily equity WITH floating PnL of open positions.
    daily_close = {str(f().raw_symbol): load_daily_close(c) for f, c, _l, _s, _t in cfg.MARKETS}
    eq_full = daily_equity(trades, risk_amount, daily_close)
    eq_oos = eq_full[eq_full.index >= holdout_start]

    full = {**edge_stats(curve["pnl"].to_numpy()), **risk_stats(eq_full)}
    oos_pnl = curve.loc[curve["date"] >= holdout_start, "pnl"].to_numpy()
    oos = {**edge_stats(oos_pnl), **risk_stats(eq_oos)}

    out_dir = _REPO_ROOT / "reports" / "equity"
    out_dir.mkdir(parents=True, exist_ok=True)
    curve.to_csv(out_dir / "portfolio_trades.csv", index=False)
    plot_equity(curve, holdout_start, risk_pct, out_dir / "equity_over_time.png")
    plot_monte_carlo(trades["r"].to_numpy(dtype=float), risk_amount, out_dir / "monte_carlo.png")
    plot_market_contributions(trades, risk_amount, out_dir / "market_contributions.png")
    plot_scorecard(full, oos, out_dir / "scorecard.png")

    print("\n===== flat portfolio (illustrative) -- full history | out-of-sample =====")
    print(f"trades:        {full['trades']:,.0f} | {oos['trades']:,.0f}")
    print(f"hit rate:      {full['hit_rate']:.1%} | {oos['hit_rate']:.1%}")
    print(f"profit factor: {full['profit_factor']:.2f} | {oos['profit_factor']:.2f}")
    print(f"expectancy:    EUR {full['expectancy']:,.0f} | {oos['expectancy']:,.0f} per trade")
    print(f"Sharpe (ann.): {full['sharpe']:.2f} | {oos['sharpe']:.2f}")
    print(f"max drawdown:  {full['max_drawdown']:.1%} | {oos['max_drawdown']:.1%}")
    print(f"risk/trade:    {risk_pct:.2f}% of start (EUR {risk_amount:,.0f})")
    print(f"charts:        {out_dir}")


if __name__ == "__main__":
    main()
