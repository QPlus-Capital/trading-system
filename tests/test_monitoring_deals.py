"""Tests for the pure monitoring logic (deals -> trades, equity, live stats)."""

from decimal import Decimal

import numpy as np
import pandas as pd
from monitoring.deals import deal_ledger, deals_to_trades, equity_curve, live_stats


def _deal(
    pid: int,
    symbol: str,
    dtype: int,
    entry: int,
    time: int,
    volume: float = 0.1,
    profit: float = 0.0,
    swap: float = 0.0,
    commission: float = 0.0,
    fee: float = 0.0,
    ticket: int | None = None,
) -> dict[str, object]:
    deal: dict[str, object] = {
        "position_id": pid,
        "symbol": symbol,
        "type": dtype,
        "entry": entry,
        "time": time,
        "volume": volume,
        "price": 1.0,
        "profit": profit,
        "swap": swap,
        "commission": commission,
        "fee": fee,
    }
    if ticket is not None:
        deal["ticket"] = ticket
    return deal


def test_deals_to_trades_pairs_in_and_out() -> None:
    deals = [
        # position 1: a BUY opened then closed for +100 (with -2 swap, -1 commission -> net +97)
        _deal(1, "XAUUSD", 0, 0, 1_000, profit=0.0, commission=-1.0),
        _deal(1, "XAUUSD", 1, 1, 90_000, profit=100.0, swap=-2.0),
        # a balance/credit op (no symbol) -> ignored
        _deal(0, "", 2, 0, 500),
        # an open-only position (no OUT) -> ignored
        _deal(2, "EURUSD", 0, 0, 2_000),
    ]
    t = deals_to_trades(deals)
    assert len(t) == 1
    row = t.iloc[0]
    assert row["position_id"] == 1
    assert row["symbol"] == "XAUUSD"
    assert row["direction"] == "BUY"
    assert row["open_time"] == pd.Timestamp(1_000, unit="s", tz="UTC")
    assert row["close_time"] == pd.Timestamp(90_000, unit="s", tz="UTC")
    assert row["open_ticket"] == 0
    assert row["volume"] == 0.1
    assert row["net_pnl"] == Decimal("97.0")  # 100 - 2 - 1


def test_deals_to_trades_empty() -> None:
    trades = deals_to_trades([])
    assert trades.empty
    assert list(trades.columns) == [
        "position_id",
        "symbol",
        "direction",
        "open_time",
        "open_ticket",
        "close_time",
        "volume",
        "net_pnl",
    ]


def test_deals_to_trades_sorts_deals_before_selecting_the_round_trip() -> None:
    deals = [
        _deal(2, "EURUSD", 0, 1, 30, profit=5.0, ticket=13),
        _deal(2, "EURUSD", 1, 1, 20, profit=10.0, ticket=12),
        _deal(2, "EURUSD", 1, 0, 10, volume=0.2, ticket=11),
    ]

    row = deals_to_trades(deals).iloc[0]

    assert row["direction"] == "SELL"
    assert row["open_time"] == pd.Timestamp(10, unit="s", tz="UTC")
    assert row["open_ticket"] == 11
    assert row["close_time"] == pd.Timestamp(30, unit="s", tz="UTC")
    assert row["volume"] == 0.2
    assert row["net_pnl"] == Decimal("15.0")


def test_equity_curve_accumulates_from_start() -> None:
    deals = [
        _deal(1, "X", 0, 0, 10),
        _deal(1, "X", 1, 1, 20, profit=50.0),
        _deal(2, "X", 0, 0, 30),
        _deal(2, "X", 1, 1, 40, profit=-30.0),
    ]
    eq = equity_curve(100_000.0, deal_ledger(deals))
    assert list(eq["equity"]) == [100_000.0, 100_050.0, 100_050.0, 100_020.0]


def test_fee_moves_ledger_equity_and_trade_net_pnl() -> None:
    deals = [
        _deal(1, "EURUSD", 0, 0, 10, fee=-2.0, ticket=100),
        _deal(1, "EURUSD", 1, 1, 20, profit=20.0, fee=-3.0, ticket=101),
    ]

    ledger = deal_ledger(deals)
    trades = deals_to_trades(deals)
    equity = equity_curve(Decimal("100000"), ledger)

    assert list(ledger["amount"]) == [Decimal("-2.0"), Decimal("17.0")]
    assert trades.iloc[0]["net_pnl"] == Decimal("15.0")
    assert list(equity["equity"]) == [Decimal("99998.0"), Decimal("100015.0")]
    assert all(isinstance(value, Decimal) for value in ledger["amount"])
    assert isinstance(trades.iloc[0]["net_pnl"], Decimal)


def test_ledger_orders_same_second_deals_by_ticket() -> None:
    deals = [
        _deal(1, "EURUSD", 0, 0, 10, profit=2.0, ticket=12),
        _deal(2, "GBPUSD", 0, 0, 10, profit=1.0, ticket=11),
    ]

    ledger = deal_ledger(deals)

    assert list(ledger.columns) == ["time", "ticket", "sequence", "amount"]
    assert list(ledger["ticket"]) == [11, 12]
    assert list(ledger["sequence"]) == [1, 0]
    assert list(ledger["amount"]) == [Decimal("1.0"), Decimal("2.0")]


def test_empty_ledger_has_the_complete_schema() -> None:
    assert list(deal_ledger([]).columns) == ["time", "ticket", "sequence", "amount"]


def test_live_stats() -> None:
    s = live_stats(np.array([100.0, -50.0, 200.0, -50.0]))
    assert s["trades"] == 4.0
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert abs(s["profit_factor"] - 3.0) < 1e-9  # 300 won / 100 lost
    assert abs(s["expectancy"] - 50.0) < 1e-9
