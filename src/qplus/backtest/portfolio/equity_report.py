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

    curve = flat_portfolio(trades, risk_amount=risk_amount)
    holdout_start = curve["date"].max() - pd.DateOffset(months=_HOLDOUT_MONTHS)

    out_dir = _REPO_ROOT / "reports" / "equity"
    out_dir.mkdir(parents=True, exist_ok=True)
    curve.to_csv(out_dir / "portfolio_trades.csv", index=False)
    plot_equity(curve, holdout_start, risk_pct, out_dir / "equity_over_time.png")
    plot_monte_carlo(trades["r"].to_numpy(dtype=float), risk_amount, out_dir / "monte_carlo.png")
    plot_market_contributions(trades, risk_amount, out_dir / "market_contributions.png")

    final = float(curve["equity"].iloc[-1])
    gain = final / _START_BALANCE - 1
    print("\n===== flat portfolio (illustrative, full history) =====")
    print(f"trades:        {len(trades)}")
    print(f"start / final: EUR {_START_BALANCE:,.0f} -> EUR {final:,.0f}  ({gain:+.1%})")
    print(f"risk/trade:    {risk_pct:.2f}% of start (EUR {risk_amount:,.0f})")
    print(f"charts:        {out_dir}")


if __name__ == "__main__":
    main()
