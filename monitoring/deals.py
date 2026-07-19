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


def to_ns(times: pd.Series) -> np.ndarray:
    """Epoch nanoseconds for a datetime column, whatever resolution pandas chose for it.

    ``astype("int64")`` returns the column's own unit -- microseconds for a ``datetime64[us]``
    column -- while ``Timestamp.value`` is always nanoseconds. Mixing the two compares numbers a
    thousandfold apart, and the comparison quietly succeeds.
    """
    ns: np.ndarray = times.to_numpy(dtype="datetime64[ns]").astype("int64")
    return ns


def deal_ledger(deals: list[dict[str, Any]]) -> pd.DataFrame:
    """``time``/``amount`` for EVERY deal: the complete record of balance movements.

    Built from raw deals rather than from reconstructed trades, because the balance moves on
    events a trade view cannot represent. An entry commission on a position that is still open is
    already in the broker's balance, but the position has no OUT deal so it is not a trade, and it
    has a symbol so it is not a cashflow -- it would fall through both and leave the reconstructed
    history quietly off by that commission for as long as the position stays open.
    """
    df = pd.DataFrame(deals)
    if df.empty or "time" not in df:
        return pd.DataFrame(columns=["time", "amount"])
    amount = df.get("profit", 0.0) + df.get("swap", 0.0) + df.get("commission", 0.0)
    out = pd.DataFrame(
        {
            "time": pd.to_datetime(df["time"].astype(int), unit="s", utc=True),
            "amount": amount.astype(float),
        }
    )
    return out.sort_values("time").reset_index(drop=True)


def money_events(ledger: pd.DataFrame | None) -> tuple[np.ndarray, np.ndarray]:
    """``(timestamps_ns, amounts)`` from a ledger, in time order."""
    if ledger is None or ledger.empty:
        return np.array([], dtype="int64"), np.array([], dtype=float)
    stamps = to_ns(ledger["time"])
    amounts = ledger["amount"].to_numpy(dtype=float)
    order = np.argsort(stamps, kind="stable")
    return stamps[order], amounts[order]


def balance_at(
    when_ns: np.ndarray, current_balance: float, ledger: pd.DataFrame | None
) -> np.ndarray:
    """The account balance at each instant in ``when_ns``, walked BACK from today's balance.

    Backwards, not forwards from an opening figure, because the current balance is the one number
    the broker states exactly. A forward walk needs an origin, and every way of obtaining one is
    a trap: today's balance already contains the history about to be replayed onto it; a saved
    start balance already contains the opening deposit that the cashflow ledger would replay
    again; and a broker that truncates deal history corrupts everything after the cutoff.

    Walking back subtracts only what happened AFTER the instant in question, so a truncated
    prefix cannot affect any balance inside the range we can see.

    ``ledger`` must be the COMPLETE record (:func:`deal_ledger`), not a trade view: the current
    balance already reflects every booked movement, so anything missing from the ledger is
    inherited into every reconstructed balance before it.
    """
    stamps, amounts = money_events(ledger)
    if len(stamps) == 0:
        return np.full(len(when_ns), current_balance, dtype=float)
    # Total booked strictly after each instant: cumulative sum from the right.
    tail = np.concatenate([np.cumsum(amounts[::-1])[::-1], [0.0]])
    idx = np.searchsorted(stamps, when_ns, side="right")
    return current_balance - tail[idx]


def equity_curve(start_balance: float, ledger: pd.DataFrame | None) -> pd.DataFrame:
    """The realized balance path: ``start_balance`` moved by every booked event in time order.

    Driven by the same ledger as the risk bases. A curve that omits cashflows never steps at a
    payout while the ledger beside it uses the balance that did step -- two pictures of one
    account, disagreeing, in the panel an operator reads first.
    """
    stamps, amounts = money_events(ledger)
    if len(stamps) == 0:
        return pd.DataFrame(columns=["close_time", "equity"])
    return pd.DataFrame(
        {
            "close_time": pd.to_datetime(stamps, utc=True),
            "equity": start_balance + np.cumsum(amounts),
        }
    )


def per_trade_risk(
    trades: pd.DataFrame,
    current_balance: float,
    risk_frac: float,
    ledger: pd.DataFrame | None = None,
) -> np.ndarray:
    """Each trade's risked amount, off the balance as it stood at that trade's OWN OPEN (#20).

    Live sizing compounds: risk is a fraction of equity at entry, so a 1R win early in a smaller
    account is a smaller number of euros than a 1R win today. Dividing the whole history by
    ``risk_frac * today's balance`` therefore shrinks the early trades -- an account that grew
    $50k -> $60k would show its early 1R wins as 0.83R, distorting expectancy and any drift check.

    Reconstructed from realized money only, which is what the deal history gives us; floating
    equity at the moment of entry is not recoverable after the fact.

    Charged at each trade's OWN OPEN rather than in close order. With overlapping positions -- our
    normal case, ten markets at once -- a later-opening trade can close first, and crediting its
    PnL to an earlier trade's basis would attribute money that did not exist when that trade was
    sized, distorting exactly the multi-market drift this monitor exists to detect.

    ``ledger`` (:func:`deal_ledger`) must carry every booked movement -- trade legs, cashflows,
    and the entry commission of a position that has not closed yet. On a prop account a payout
    moves the balance without any trade, and an open position's commission moves it without any
    completed trade; either omission makes every basis around it wrong.
    """
    if trades.empty:
        return np.array([], dtype=float)
    open_ns = to_ns(trades["open_time"])
    risk: np.ndarray = risk_frac * balance_at(open_ns, current_balance, ledger)
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
