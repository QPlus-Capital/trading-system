"""Turn raw MT5 deals into round-trip trades, a realized-equity curve, and live stats.

Pure functions over a list of deal dicts (from ``Mt5Bridge.history_deals``), so they are
testable without a terminal. A "trade" is one closed position segment: deals are processed by
``position_id``; an INOUT reversal ends one segment and starts its opposite successor.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

_ZERO = Decimal("0")
_MONEY_LEGS = ("profit", "swap", "commission", "fee")
_DEAL_TYPE_BUY = 0
_DEAL_TYPE_SELL = 1
_DEAL_ENTRY_IN = 0
_DEAL_ENTRY_OUT = 1
_DEAL_ENTRY_INOUT = 2
_DEAL_ENTRY_OUT_BY = 3
_TRADE_COLUMNS = [
    "position_id",
    "symbol",
    "direction",
    "open_time",
    "open_ticket",
    "close_time",
    "volume",
    "net_pnl",
]


@dataclass
class _OpenSegment:
    position_id: int
    symbol: str
    direction: str
    open_time: int
    open_ticket: int
    opened_volume: Decimal
    remaining_volume: Decimal
    net_pnl: Decimal


def _money(value: object) -> Decimal:
    """Convert a broker or fixture money value without binary-float arithmetic."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _deal_amount(deal: dict[str, Any]) -> Decimal:
    return sum((_money(deal.get(leg, 0)) for leg in _MONEY_LEGS), start=_ZERO)


def _deal_context(deal: dict[str, Any]) -> str:
    return (
        f"type={deal.get('type')!r}, ticket={deal.get('ticket')!r}, "
        f"entry={deal.get('entry')!r}, position_id={deal.get('position_id')!r}"
    )


def _deal_direction(deal: dict[str, Any]) -> str:
    """Map only MT5 BUY/SELL deal types to a monitoring direction."""
    value = deal.get("type")
    if type(value) is not int:
        raise ValueError(f"MT5 deal type must be an exact integer ({_deal_context(deal)})")
    if value == _DEAL_TYPE_BUY:
        return "BUY"
    if value == _DEAL_TYPE_SELL:
        return "SELL"
    raise ValueError(f"Unsupported symbol-bearing MT5 deal type ({_deal_context(deal)})")


def _deal_entry(deal: dict[str, Any]) -> int:
    value = deal.get("entry")
    if type(value) is not int or value not in {
        _DEAL_ENTRY_IN,
        _DEAL_ENTRY_OUT,
        _DEAL_ENTRY_INOUT,
        _DEAL_ENTRY_OUT_BY,
    }:
        raise ValueError(f"Unsupported symbol-bearing MT5 deal entry ({_deal_context(deal)})")
    return value


def _deal_volume(deal: dict[str, Any]) -> Decimal:
    volume = _money(deal.get("volume", _ZERO))
    if volume <= _ZERO:
        raise ValueError(f"MT5 trade deal volume must be positive ({_deal_context(deal)})")
    return volume


def _opposite(direction: str) -> str:
    if direction == "BUY":
        return "SELL"
    if direction == "SELL":
        return "BUY"
    raise ValueError(f"Unsupported active direction: {direction!r}")


def _trade_row(segment: _OpenSegment, deal: dict[str, Any]) -> dict[str, object]:
    return {
        "position_id": segment.position_id,
        "symbol": segment.symbol,
        "direction": segment.direction,
        "open_time": pd.to_datetime(segment.open_time, unit="s", utc=True),
        "open_ticket": segment.open_ticket,
        "close_time": pd.to_datetime(int(deal["time"]), unit="s", utc=True),
        "volume": float(segment.opened_volume),
        "net_pnl": segment.net_pnl,
    }


def deals_to_trades(deals: list[dict[str, Any]]) -> pd.DataFrame:
    """Reconstruct ordered position segments from raw MT5 deals.

    Empty-symbol cash operations remain ledger-only. Normal OUT and OUT_BY deals close the segment
    named by their own position ID. INOUT closes the active segment and opens its opposite residual
    under the same position ID. Net PnL folds in swap, commission, and fee exactly once. Because MT5
    exposes one indivisible money record for an INOUT deal, that record belongs to the segment the
    event closes; the residual segment starts without a duplicated amount.

    The opening ticket is retained because MT5 timestamps have only one-second precision: the
    ticket establishes which same-second money movements existed before the runner sized the
    segment. Still-open final segments are omitted from the closed-trade view but remain fully
    represented in :func:`deal_ledger`.
    """
    grouped: dict[int, list[dict[str, Any]]] = {}
    for sequence, deal in enumerate(deals):
        if not str(deal.get("symbol", "")):
            continue
        normalized = {
            **{leg: deal.get(leg, _ZERO) for leg in _MONEY_LEGS},
            **deal,
            "_sequence": sequence,
            "_event_order": int(deal.get("ticket", sequence)),
        }
        position_id = int(deal["position_id"])
        grouped.setdefault(position_id, []).append(normalized)

    rows: list[dict[str, object]] = []
    for position_id in sorted(grouped):
        events = sorted(
            grouped[position_id],
            key=lambda deal: (
                int(deal["time"]),
                int(deal["_event_order"]),
                int(deal["_sequence"]),
            ),
        )
        segment: _OpenSegment | None = None
        for deal in events:
            direction = _deal_direction(deal)
            entry = _deal_entry(deal)
            volume = _deal_volume(deal)
            amount = _deal_amount(deal)
            symbol = str(deal["symbol"])

            if entry == _DEAL_ENTRY_IN:
                if segment is None:
                    segment = _OpenSegment(
                        position_id=position_id,
                        symbol=symbol,
                        direction=direction,
                        open_time=int(deal["time"]),
                        open_ticket=int(deal["_event_order"]),
                        opened_volume=volume,
                        remaining_volume=volume,
                        net_pnl=amount,
                    )
                    continue
                if segment.symbol != symbol or segment.direction != direction:
                    raise ValueError(
                        "MT5 IN deal contradicts its active position segment "
                        f"({_deal_context(deal)})"
                    )
                segment.opened_volume += volume
                segment.remaining_volume += volume
                segment.net_pnl += amount
                continue

            if segment is None:
                raise ValueError(
                    f"MT5 closing deal has no active position segment ({_deal_context(deal)})"
                )
            if segment.symbol != symbol or direction != _opposite(segment.direction):
                raise ValueError(
                    "MT5 closing deal contradicts its active position segment "
                    f"({_deal_context(deal)})"
                )

            if entry in {_DEAL_ENTRY_OUT, _DEAL_ENTRY_OUT_BY}:
                if volume > segment.remaining_volume:
                    raise ValueError(
                        f"MT5 closing deal exceeds active volume ({_deal_context(deal)})"
                    )
                segment.remaining_volume -= volume
                segment.net_pnl += amount
                if segment.remaining_volume == _ZERO:
                    rows.append(_trade_row(segment, deal))
                    segment = None
                continue

            if volume <= segment.remaining_volume:
                raise ValueError(
                    f"MT5 INOUT deal has no opposite residual volume ({_deal_context(deal)})"
                )
            residual = volume - segment.remaining_volume
            segment.net_pnl += amount
            rows.append(_trade_row(segment, deal))
            segment = _OpenSegment(
                position_id=position_id,
                symbol=symbol,
                direction=direction,
                open_time=int(deal["time"]),
                open_ticket=int(deal["_event_order"]),
                opened_volume=residual,
                remaining_volume=residual,
                net_pnl=_ZERO,
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
    """Ordered ``time``/``ticket``/``amount`` for every balance movement.

    Built from raw deals rather than from reconstructed trades, because the balance moves on
    events a trade view cannot represent. Entry commission or fee on a position that is still open
    is already in the broker's balance, but the position has no OUT deal so it is not a trade, and
    it has a symbol so it is not a cashflow -- it would fall through both and leave the
    reconstructed history quietly off by that cost for as long as the position stays open.
    """
    if not deals or "time" not in deals[0]:
        return pd.DataFrame(columns=["time", "ticket", "sequence", "amount"])
    out = pd.DataFrame(
        {
            "time": pd.to_datetime([int(deal["time"]) for deal in deals], unit="s", utc=True),
            "ticket": [int(deal.get("ticket", sequence)) for sequence, deal in enumerate(deals)],
            "sequence": list(range(len(deals))),
            "amount": [_deal_amount(deal) for deal in deals],
        }
    )
    return out.sort_values(["time", "ticket", "sequence"], kind="stable").reset_index(drop=True)


def money_events(ledger: pd.DataFrame | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(timestamps_ns, tickets, Decimal amounts)`` from a ledger, in total order."""
    if ledger is None or ledger.empty:
        return (
            np.array([], dtype="int64"),
            np.array([], dtype="int64"),
            np.array([], dtype=object),
        )
    stamps = to_ns(ledger["time"])
    tickets = (
        ledger["ticket"].to_numpy(dtype="int64")
        if "ticket" in ledger
        else np.arange(len(ledger), dtype="int64")
    )
    sequences = (
        ledger["sequence"].to_numpy(dtype="int64")
        if "sequence" in ledger
        else np.arange(len(ledger), dtype="int64")
    )
    amounts = np.array([_money(value) for value in ledger["amount"]], dtype=object)
    order = np.lexsort((sequences, tickets, stamps))
    return stamps[order], tickets[order], amounts[order]


def balance_at(
    when_ns: np.ndarray,
    current_balance: Decimal | int | float | str,
    ledger: pd.DataFrame | None,
    *,
    before_ticket: np.ndarray | None = None,
) -> np.ndarray:
    """Balances at event cutoffs, walked backward from the broker's current balance.

    Backwards, not forwards from an opening figure, because the current balance is the one number
    the broker states exactly. A forward walk needs an origin, and every way of obtaining one is
    a trap: today's balance already contains the history about to be replayed onto it; a saved
    start balance already contains the opening deposit that the cashflow ledger would replay
    again; and a broker that truncates deal history corrupts everything after the cutoff.

    With no ticket, the cutoff is the end of the timestamp and walking back subtracts only what
    happened strictly after it. With ``before_ticket``, the cutoff is immediately before that
    ticket: earlier same-second deals remain in the basis, while the named opening deal and every
    later event are subtracted. This matches the runner's pre-order account snapshot.

    ``ledger`` must be the COMPLETE record (:func:`deal_ledger`), not a trade view: the current
    balance already reflects every booked movement, so anything missing from the ledger is
    inherited into every reconstructed balance before it.
    """
    stamps, tickets, amounts = money_events(ledger)
    balance = _money(current_balance)
    if len(stamps) == 0:
        return np.array([balance for _ in when_ns], dtype=object)

    tail = [_ZERO] * (len(amounts) + 1)
    for idx in range(len(amounts) - 1, -1, -1):
        tail[idx] = tail[idx + 1] + amounts[idx]

    stamp_list = [int(stamp) for stamp in stamps]
    event_keys = list(zip(stamp_list, (int(ticket) for ticket in tickets), strict=True))
    cutoffs: list[int]
    if before_ticket is None:
        cutoffs = [bisect_right(stamp_list, int(stamp)) for stamp in when_ns]
    else:
        if len(before_ticket) != len(when_ns):
            raise ValueError("before_ticket must align one-for-one with when_ns")
        cutoffs = [
            bisect_left(event_keys, (int(stamp), int(ticket)))
            for stamp, ticket in zip(when_ns, before_ticket, strict=True)
        ]
    return np.array([balance - tail[idx] for idx in cutoffs], dtype=object)


def equity_curve(
    start_balance: Decimal | int | float | str, ledger: pd.DataFrame | None
) -> pd.DataFrame:
    """The realized balance path: ``start_balance`` moved by every booked event in time order.

    Driven by the same ledger as the risk bases. A curve that omits cashflows never steps at a
    payout while the ledger beside it uses the balance that did step -- two pictures of one
    account, disagreeing, in the panel an operator reads first.
    """
    stamps, _tickets, amounts = money_events(ledger)
    if len(stamps) == 0:
        return pd.DataFrame(columns=["close_time", "equity"])
    running = _money(start_balance)
    equity: list[Decimal] = []
    for amount in amounts:
        running += amount
        equity.append(running)
    return pd.DataFrame(
        {
            "close_time": pd.to_datetime(stamps, utc=True),
            "equity": equity,
        }
    )


def per_trade_risk(
    trades: pd.DataFrame,
    current_balance: Decimal | int | float | str,
    risk_frac: Decimal | int | float | str,
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
    and the opening costs of a position that has not closed yet. On a prop account a payout moves
    the balance without any trade, and an open position's commission or fee moves it without any
    completed trade; either omission makes every basis around it wrong.
    """
    if trades.empty:
        return np.array([], dtype=object)
    open_ns = to_ns(trades["open_time"])
    before_ticket = (
        trades["open_ticket"].to_numpy(dtype="int64") if "open_ticket" in trades else None
    )
    balances = balance_at(
        open_ns,
        current_balance,
        ledger,
        before_ticket=before_ticket,
    )
    fraction = _money(risk_frac)
    return np.array([fraction * balance for balance in balances], dtype=object)


def live_stats(net_pnl: np.ndarray) -> dict[str, float]:
    """Edge metrics for a set of live trades (hit rate, payoff, profit factor, expectancy)."""
    values = [_money(value) for value in net_pnl]
    wins = [value for value in values if value > _ZERO]
    losses = [value for value in values if value < _ZERO]
    n = len(values)
    won = sum(wins, start=_ZERO)
    lost = sum(losses, start=_ZERO)
    mean_win = won / len(wins) if wins else _ZERO
    mean_loss = lost / len(losses) if losses else _ZERO
    return {
        "trades": float(n),
        "hit_rate": len(wins) / n if n else 0.0,
        "payoff": float(mean_win / -mean_loss) if wins and losses else 0.0,
        "profit_factor": float(won / -lost) if lost < _ZERO else float("inf"),
        "expectancy": float(sum(values, start=_ZERO) / n) if n else 0.0,
    }
