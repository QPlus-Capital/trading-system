"""Tests for the pure monitoring logic (deals -> trades, equity, live stats)."""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
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
        _deal(2, "EURUSD", 0, 1, 20, profit=10.0, ticket=12),
        _deal(2, "EURUSD", 1, 0, 10, volume=0.2, ticket=11),
    ]

    row = deals_to_trades(deals).iloc[0]

    assert row["direction"] == "SELL"
    assert row["open_time"] == pd.Timestamp(10, unit="s", tz="UTC")
    assert row["open_ticket"] == 11
    assert row["close_time"] == pd.Timestamp(30, unit="s", tz="UTC")
    assert row["volume"] == 0.2
    assert row["net_pnl"] == Decimal("15.0")


@pytest.mark.parametrize("invalid_type", [13, True])
def test_symbol_bearing_non_trade_deal_type_fails_closed(invalid_type: object) -> None:
    deals = [
        {
            **_deal(41, "EURUSD", 0, 0, 10, ticket=101),
            "type": invalid_type,
        },
        _deal(41, "EURUSD", 1, 1, 20, ticket=102),
    ]

    with pytest.raises(
        ValueError,
        match=r"type=.*ticket=101.*entry=0.*position_id=41",
    ):
        deals_to_trades(deals)


def test_empty_symbol_cash_deal_stays_ledger_only() -> None:
    cash = _deal(0, "", 2, 0, 10, profit=500.0, ticket=100)

    assert deals_to_trades([cash]).empty
    assert list(deal_ledger([cash])["amount"]) == [Decimal("500.0")]


@pytest.mark.parametrize("invalid_entry", [4, True])
def test_symbol_bearing_unknown_entry_mode_fails_closed(invalid_entry: object) -> None:
    deal = {
        **_deal(42, "EURUSD", 0, 0, 10, ticket=103),
        "entry": invalid_entry,
    }

    with pytest.raises(ValueError, match=r"ticket=103.*entry=.*position_id=42"):
        deals_to_trades([deal])


def test_inout_reversal_emits_two_directionally_correct_segments() -> None:
    deals = [
        _deal(7, "XAUUSD", 0, 0, 10, volume=1.0, commission=-1.0, ticket=100),
        _deal(
            7,
            "XAUUSD",
            1,
            2,
            20,
            volume=1.5,
            profit=100.0,
            swap=-2.0,
            commission=-3.0,
            ticket=101,
        ),
        _deal(
            7,
            "XAUUSD",
            0,
            1,
            30,
            volume=0.5,
            profit=20.0,
            fee=-1.0,
            ticket=102,
        ),
    ]

    trades = deals_to_trades(deals)

    assert list(trades["position_id"]) == [7, 7]
    assert list(trades["direction"]) == ["BUY", "SELL"]
    assert list(trades["open_ticket"]) == [100, 101]
    assert list(trades["volume"]) == [1.0, 0.5]
    assert list(trades["net_pnl"]) == [Decimal("94.0"), Decimal("19.0")]
    assert trades.iloc[0]["close_time"] == trades.iloc[1]["open_time"]
    assert sum(trades["net_pnl"], Decimal("0")) == sum(
        deal_ledger(deals)["amount"],
        Decimal("0"),
    )


def test_out_by_deals_close_their_own_position_ids() -> None:
    deals = [
        _deal(11, "EURUSD", 0, 0, 10, volume=0.3, ticket=100),
        _deal(22, "EURUSD", 1, 0, 11, volume=0.3, ticket=101),
        _deal(11, "EURUSD", 1, 3, 20, volume=0.3, profit=12.0, ticket=102),
        _deal(22, "EURUSD", 0, 3, 20, volume=0.3, profit=-7.0, ticket=103),
    ]

    trades = deals_to_trades(deals).set_index("position_id")

    assert trades.loc[11, "direction"] == "BUY"
    assert trades.loc[11, "net_pnl"] == Decimal("12.0")
    assert trades.loc[22, "direction"] == "SELL"
    assert trades.loc[22, "net_pnl"] == Decimal("-7.0")


def test_scale_ins_and_partial_exits_preserve_volume_and_money() -> None:
    deals = [
        _deal(5, "GBPUSD", 0, 0, 10, volume=0.1, commission=-1.0, ticket=100),
        _deal(5, "GBPUSD", 0, 0, 11, volume=0.2, commission=-2.0, ticket=101),
        _deal(
            5,
            "GBPUSD",
            1,
            1,
            20,
            volume=0.15,
            profit=10.0,
            fee=-1.0,
            ticket=102,
        ),
        _deal(
            5,
            "GBPUSD",
            1,
            1,
            21,
            volume=0.15,
            profit=20.0,
            fee=-1.0,
            ticket=103,
        ),
    ]

    row = deals_to_trades(deals).iloc[0]

    assert row["direction"] == "BUY"
    assert row["volume"] == 0.3
    assert row["close_time"] == pd.Timestamp(21, unit="s", tz="UTC")
    assert row["net_pnl"] == Decimal("25.0")
    assert row["net_pnl"] == sum(deal_ledger(deals)["amount"], Decimal("0"))


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
