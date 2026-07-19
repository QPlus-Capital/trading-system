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


def balance_operations(deals: list[dict[str, Any]]) -> pd.DataFrame:
    """Non-trade cashflows: deposits, withdrawals, credits, prop-firm payouts.

    MT5 books these as deals with no symbol, which :func:`deals_to_trades` drops -- correctly,
    they are not trades. But they DO move the balance that later trades are sized against, so any
    reconstruction of that balance has to carry them or every post-payout risk basis is wrong.
    """
    df = pd.DataFrame(deals)
    if df.empty or "symbol" not in df:
        return pd.DataFrame(columns=["time", "amount"])
    ops = df[~df["symbol"].astype(bool)]
    if ops.empty:
        return pd.DataFrame(columns=["time", "amount"])
    amount = ops["profit"] + ops.get("swap", 0.0) + ops.get("commission", 0.0)
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(ops["time"].astype(int), unit="s", utc=True),
            "amount": amount.astype(float),
        }
    )
    return out.sort_values("time").reset_index(drop=True)


def derive_account_start(
    current_balance: float, trades: pd.DataFrame, cash_flows: pd.DataFrame
) -> float:
    """The balance the account opened with, reconstructed from today's balance backwards.

    Used only when no saved risk state names it. Taking today's balance as the origin instead
    would apply the account's whole lifetime result to a figure that already contains it, so every
    risk basis -- and the equity the window starts from -- would be off by that result twice.
    """
    booked = float(trades["net_pnl"].sum()) if not trades.empty else 0.0
    moved = float(cash_flows["amount"].sum()) if not cash_flows.empty else 0.0
    return current_balance - booked - moved


def equity_curve(trades: pd.DataFrame, start_balance: float) -> pd.DataFrame:
    """Realized equity over time: ``start_balance`` plus the cumulative net PnL at each close."""
    if trades.empty:
        return pd.DataFrame(columns=["close_time", "equity"])
    eq = start_balance + trades["net_pnl"].cumsum()
    return pd.DataFrame({"close_time": trades["close_time"], "equity": eq})


def per_trade_risk(
    trades: pd.DataFrame,
    start_balance: float,
    risk_frac: float,
    cash_flows: pd.DataFrame | None = None,
) -> np.ndarray:
    """Each trade's risked amount, off the equity as it stood BEFORE that trade (#20).

    Live sizing compounds: risk is a fraction of equity at entry, so a 1R win early in a smaller
    account is a smaller number of euros than a 1R win today. Dividing the whole history by
    ``risk_frac * today's equity`` therefore shrinks the early trades -- an account that grew
    $50k -> $60k would show its early 1R wins as 0.83R, distorting expectancy and any drift check.

    Reconstructed from realized PnL, which is what the deal history gives us; floating equity at
    the moment of entry is not recoverable after the fact.

    The balance is walked in CLOSE order (that is when PnL is booked) but each trade is charged
    the balance as it stood at its OWN OPEN. With overlapping positions -- our normal case, ten
    markets at once -- a later-opening trade can close first, and crediting its PnL to an earlier
    trade's basis would attribute money that did not exist when that trade was sized, distorting
    exactly the multi-market drift this monitor exists to detect.

    ``cash_flows`` (:func:`balance_operations`) belongs in the same ledger: on a prop account a
    payout or top-up moves the balance without any trade, and leaving it out makes every basis
    after it wrong.
    """
    booked = trades["net_pnl"].to_numpy(dtype=float)
    close_ns = trades["close_time"].astype("int64").to_numpy()
    open_ns = trades["open_time"].astype("int64").to_numpy()
    # Every event that moved the balance, in the order it moved it: trade PnL at close, and any
    # deposit / withdrawal / payout at its own time. Omitting the cashflows would leave the ledger
    # describing an account balance that never existed after the first one.
    events: list[tuple[int, float]] = [
        (int(close_ns[i]), float(booked[i])) for i in range(len(trades))
    ]
    if cash_flows is not None and not cash_flows.empty:
        events += [
            (int(t), float(a))
            for t, a in zip(
                cash_flows["time"].astype("int64"), cash_flows["amount"], strict=True
            )
        ]
    events.sort(key=lambda e: e[0])
    running, balance_at = start_balance, np.empty(len(trades))
    ledger: list[tuple[int, float]] = [(np.iinfo(np.int64).min, start_balance)]
    for when, amount in events:
        running += amount
        ledger.append((when, running))
    stamps = np.array([t for t, _ in ledger])
    values = np.array([v for _, v in ledger])
    for i in range(len(trades)):  # balance as of each trade's OWN open
        balance_at[i] = values[np.searchsorted(stamps, open_ns[i], side="right") - 1]
    risk: np.ndarray = risk_frac * balance_at
    return risk


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
