"""Tests for the pure monitoring logic (deals -> trades, equity, live stats)."""

import numpy as np
import pandas as pd
from monitoring.deals import deals_to_trades, equity_curve, live_stats, per_trade_risk


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
    eq = equity_curve(deals_to_trades(deals), start_balance=100_000.0)
    assert list(eq["equity"]) == [100_050.0, 100_020.0]


def test_live_stats() -> None:
    s = live_stats(np.array([100.0, -50.0, 200.0, -50.0]))
    assert s["trades"] == 4.0
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert abs(s["profit_factor"] - 3.0) < 1e-9  # 300 won / 100 lost
    assert abs(s["expectancy"] - 50.0) < 1e-9


def _seq(opens: list[str], closes: list[str], pnl: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime(opens, utc=True),
            "close_time": pd.to_datetime(closes, utc=True),
            "net_pnl": pnl,
        }
    )


def test_each_trade_is_normalised_off_the_equity_it_was_sized_against() -> None:
    """#20: sizing compounds, so an early 1R win is fewer euros than a later one. Dividing the
    whole history by today's risk would show the early trades as sub-1R -- drift that never
    happened."""
    trades = _seq(
        ["2026-01-01", "2026-01-03", "2026-01-05"],
        ["2026-01-02", "2026-01-04", "2026-01-06"],
        [1_000.0, 1_000.0, 1_000.0],
    )
    risk = per_trade_risk(trades, start_balance=100_000.0, risk_frac=0.01)
    # Sequential trades: sized against 100k, then 101k, then 102k.
    assert list(risk) == [1_000.0, 1_010.0, 1_020.0]


def test_an_overlapping_trade_is_not_credited_with_pnl_that_came_later() -> None:
    """Codex P2: the balance is walked in CLOSE order, but each trade must be charged the balance
    at its OWN OPEN. Trade A opens first and closes last; B opens after A and closes before it.
    Crediting B's win to A would attribute money that did not exist when A was sized -- exactly
    the multi-market overlap this monitor exists to diagnose."""
    trades = _seq(
        ["2026-01-01", "2026-01-02"],  # A opens first ...
        ["2026-01-10", "2026-01-03"],  # ... but closes LAST; B closes early with a win
        [500.0, 5_000.0],
    )
    risk = per_trade_risk(trades, start_balance=100_000.0, risk_frac=0.01)
    assert risk[0] == 1_000.0  # A: sized against the untouched 100k
    assert risk[1] == 1_000.0  # B: opened before anything had closed -> also 100k
