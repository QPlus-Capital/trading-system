"""Tests for the pure monitoring logic (deals -> trades, equity, live stats)."""

import numpy as np
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
) -> dict[str, object]:
    return {
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
    }


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
    assert row["symbol"] == "XAUUSD" and row["direction"] == "BUY"
    assert abs(row["net_pnl"] - 97.0) < 1e-9  # 100 - 2 - 1


def test_deals_to_trades_empty() -> None:
    assert deals_to_trades([]).empty


def test_equity_curve_accumulates_from_start() -> None:
    deals = [
        _deal(1, "X", 0, 0, 10),
        _deal(1, "X", 1, 1, 20, profit=50.0),
        _deal(2, "X", 0, 0, 30),
        _deal(2, "X", 1, 1, 40, profit=-30.0),
    ]
    eq = equity_curve(100_000.0, deal_ledger(deals))
    assert list(eq["equity"]) == [100_000.0, 100_050.0, 100_050.0, 100_020.0]


def test_live_stats() -> None:
    s = live_stats(np.array([100.0, -50.0, 200.0, -50.0]))
    assert s["trades"] == 4.0
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert abs(s["profit_factor"] - 3.0) < 1e-9  # 300 won / 100 lost
    assert abs(s["expectancy"] - 50.0) < 1e-9
