"""Shared portfolio statistics: the metric helpers the stages and analysis tools all use.

Edge metrics (hit rate, payoff, expectancy), risk metrics (return, drawdown, Sharpe on the
floating-inclusive daily equity), R-multiples, and the per-market full-history backtest that
turns the frozen config into a timed, cost-inclusive trade stream. Pure functions on DataFrames
and arrays -- no plotting, no CLI.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from core.broker import BrokerProfile, swap_r_per_trade

from research.engine.recipe import SweepRecipe
from research.portfolio.trades import timed_trades_from_report

_START_BALANCE = 100_000.0  # matches the live prop account (see config ACCOUNT)
_BASE_RISK = 0.01  # the backtest sizes each trade at 1% of equity; used to recover R-multiples


def r_multiples(pnls: Sequence[float], *, start: float = _START_BALANCE) -> list[float]:
    """Size-invariant, cost-inclusive return per trade (realized PnL / the risk it took).

    The backtest sizes each position at ``_BASE_RISK`` of the *current* equity, so we walk the
    per-market equity forward to recover the risk each trade actually took and divide the PnL by
    it. The R-multiples are independent of the backtest's compounding, so they can be re-booked at
    any flat risk on a shared account.
    """
    equity = start
    out: list[float] = []
    for pnl in pnls:
        risk = _BASE_RISK * equity
        out.append(pnl / risk if risk > 0 else 0.0)
        equity += pnl
    return out


def _market_trades(
    factory: Any,
    csv: str,
    leverage: float,
    sl: float,
    tp: float,
    switches: dict[str, Any],
    broker: BrokerProfile | None = None,
) -> pd.DataFrame:
    """Full-history backtest of one market at the frozen config -> timed trades with R-multiples.

    If ``broker`` carries a swap spec for this market, the per-trade overnight swap (in R) is
    netted onto the R-multiples, so every downstream metric is automatically net of swap.
    """
    from nautilus_trader.backtest.node import BacktestNode

    recipe = SweepRecipe(
        factory(),
        csv,
        leverage=leverage,
        config_overrides={**switches, "stop_loss_pct": sl, "take_profit_pct": tp},
        broker=broker,
    )
    node = BacktestNode(configs=[recipe.build_run_config({})])  # start/end None -> full history
    try:
        node.run()
        pos = node.get_engines()[0].trader.generate_positions_report()
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    name = str(recipe.INSTRUMENT.raw_symbol)
    rows = timed_trades_from_report(pos, name, sl)
    df = pd.DataFrame(rows).sort_values("ts_closed").reset_index(drop=True)
    df["r"] = r_multiples(df["pnl_base"].tolist())
    if broker is not None and (spec := broker.swap_spec(name)) is not None:
        df["r"] = df["r"].to_numpy(dtype=float) + swap_r_per_trade(df, spec)
    return df


def daily_equity(
    trades: pd.DataFrame,
    flat_pnl: np.ndarray,
    daily_close: dict[str, pd.Series],
    *,
    start_balance: float = _START_BALANCE,
) -> pd.Series:
    """Daily mark-to-market equity (flat sizing), INCLUDING open positions' floating PnL.

    ``flat_pnl`` is each trade's flat EUR contribution (aligned to ``trades``' rows). Uses the
    tested ``base_curves`` machinery: booked as realized on close and marked to the daily price
    while open. Unlike the realized-only trade curve, this shows the real intraday swings, so
    Sharpe / drawdown computed on it are honest (not flattered by ignoring floating losses).
    """
    from research.portfolio.curves import DAY_NS, align_prices, base_curves, to_day

    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    t["pnl_base"] = np.asarray(flat_pnl, dtype=float)  # base_curves reads 'pnl_base'
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
        # Standard max drawdown: worst peak-to-trough as a fraction of the equity AT the peak.
        "max_drawdown": float(((equity - peak) / peak).min()),
        "sharpe": float(ret.mean() / std * np.sqrt(252)) if std > 0 else 0.0,
    }
