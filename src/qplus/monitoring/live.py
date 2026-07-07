"""Turn raw MT5 deals into round-trip trades, a realized-equity curve, and live stats.

Pure functions over a list of deal dicts (from ``Mt5Bridge.history_deals``), so they are
testable without a terminal. A "trade" is one closed position: its deals are grouped by
``position_id``; the net PnL is profit + swap + commission across the position's deals.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

_TRADE_COLUMNS = [
    "position_id",
    "symbol",
    "direction",
    "open_time",
    "close_time",
    "volume",
    "net_pnl",
]


def deals_to_trades(deals: list[dict[str, Any]]) -> pd.DataFrame:
    """Reconstruct closed round-trip trades from raw deals (grouped by position).

    Skips balance operations (no symbol) and still-open positions (no OUT deal). Net PnL folds
    in swap + commission, so the live numbers are the honest, all-in result.
    """
    df = pd.DataFrame(deals)
    if df.empty or "position_id" not in df:
        return pd.DataFrame(columns=_TRADE_COLUMNS)
    df = df[df["symbol"].astype(bool)]  # drop balance/credit deals (empty symbol)

    rows = []
    for pid, g in df.groupby("position_id"):
        ins, outs = g[g["entry"] == 0], g[g["entry"] == 1]
        if ins.empty or outs.empty:
            continue  # not a completed round trip
        first_in, last_out = ins.iloc[0], outs.iloc[-1]
        net = float((g["profit"] + g["swap"] + g["commission"]).sum())
        rows.append(
            {
                "position_id": int(pid),
                "symbol": str(first_in["symbol"]),
                "direction": "BUY" if int(first_in["type"]) == 0 else "SELL",
                "open_time": pd.to_datetime(int(first_in["time"]), unit="s", utc=True),
                "close_time": pd.to_datetime(int(last_out["time"]), unit="s", utc=True),
                "volume": float(first_in["volume"]),
                "net_pnl": net,
            }
        )
    out = pd.DataFrame(rows, columns=_TRADE_COLUMNS)
    return out.sort_values("close_time").reset_index(drop=True) if not out.empty else out


def equity_curve(trades: pd.DataFrame, start_balance: float) -> pd.DataFrame:
    """Realized equity over time: ``start_balance`` plus the cumulative net PnL at each close."""
    if trades.empty:
        return pd.DataFrame(columns=["close_time", "equity"])
    eq = start_balance + trades["net_pnl"].cumsum()
    return pd.DataFrame({"close_time": trades["close_time"], "equity": eq})


def live_stats(net_pnl: np.ndarray) -> dict[str, float]:
    """Edge metrics for a set of live trades (hit rate, payoff, profit factor, expectancy)."""
    wins, losses = net_pnl[net_pnl > 0], net_pnl[net_pnl < 0]
    n = len(net_pnl)
    return {
        "trades": float(n),
        "hit_rate": len(wins) / n if n else 0.0,
        "payoff": (wins.mean() / -losses.mean()) if len(wins) and len(losses) else 0.0,
        "profit_factor": (wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "expectancy": float(net_pnl.mean()) if n else 0.0,
    }
