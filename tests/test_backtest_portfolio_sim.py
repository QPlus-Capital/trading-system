"""Tests for the daily realized/equity curve construction (Stage 3/4 support)."""

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.curves import (
    DAY_NS,
    align_prices,
    base_curves,
    to_day,
    worst_unrealized,
)


def test_to_day() -> None:
    assert to_day(3 * DAY_NS) == 3
    assert to_day(3 * DAY_NS + DAY_NS // 2) == 3  # within the same day


def test_align_prices_ffill() -> None:
    prices = align_prices(pd.Series({0: 10.0, 2: 12.0}), 0, 3)
    assert list(prices) == [10.0, 10.0, 12.0, 12.0]


def test_base_curves_single_trade() -> None:
    # Long trade: open day 0, close day 2, +100 PnL, entry 10 -> exit 11. Price 10,10.5,11.
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [0],
            "cd": [2],
            "pnl_base": [100.0],
            "entry": [10.0],
            "exit": [11.0],
        }
    )
    prices = {"X": np.array([10.0, 10.5, 11.0])}
    realized, unrealized = base_curves(trades, prices, 0, 2)
    # Realized only books at close day 2; unrealized marks the open days linearly in price.
    assert list(realized) == [0.0, 0.0, 100.0]
    assert list(unrealized) == [0.0, 50.0, 0.0]  # day1: (10.5-10)/(11-10)=0.5 -> +50
    assert list(realized + unrealized) == [0.0, 50.0, 100.0]


def test_base_curves_two_markets_open_together() -> None:
    # Two positions open simultaneously on day 1, both underwater -> equity dip stacks.
    trades = pd.DataFrame(
        {
            "market": ["A", "B"],
            "od": [1, 1],
            "cd": [3, 3],
            "pnl_base": [200.0, -100.0],
            "entry": [100.0, 50.0],
            "exit": [102.0, 49.0],
        }
    )
    prices = {"A": np.array([100.0, 99.0, 99.0, 102.0]), "B": np.array([50.0, 50.5, 50.5, 49.0])}
    realized, unrealized = base_curves(trades, prices, 0, 3)
    # Day 1: A floating (99-100)/2*200 = -100; B floating (50.5-50)/-1*-100 = +50 -> sum -50.
    assert unrealized[1] == -50.0
    assert list(realized) == [0.0, 0.0, 0.0, 100.0]  # both close day 3: +200-100


def test_worst_unrealized_marks_adverse_extreme() -> None:
    # Long (k>0): marked at the day's LOW, not the close -> a deeper intraday dip than base.
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [0],
            "cd": [2],
            "pnl_base": [100.0],  # k = 100/(11-10) = 100 > 0 -> long
            "entry": [10.0],
            "exit": [11.0],
        }
    )
    highs = {"X": np.array([10.0, 10.5, 11.0])}
    lows = {"X": np.array([10.0, 9.5, 11.0])}  # day1 dips to 9.5
    worst = worst_unrealized(trades, highs, lows, 0, 2)
    # Day 1 at the low: 100 * (9.5 - 10) = -50 (worse than the close-based +50).
    assert list(worst) == [0.0, -50.0, 0.0]


def test_worst_unrealized_short_uses_high() -> None:
    # Short (k<0): entry 100, exit 98 (price fell) -> profit; adverse = the day's HIGH.
    trades = pd.DataFrame(
        {
            "market": ["S"],
            "od": [0],
            "cd": [2],
            "pnl_base": [100.0],  # k = 100/(98-100) = -50 < 0 -> short
            "entry": [100.0],
            "exit": [98.0],
        }
    )
    highs = {"S": np.array([100.0, 101.0, 98.0])}  # day1 spikes to 101 (adverse for a short)
    lows = {"S": np.array([100.0, 97.0, 98.0])}
    worst = worst_unrealized(trades, highs, lows, 0, 2)
    # Day 1 at the high: -50 * (101 - 100) = -50.
    assert list(worst) == [0.0, -50.0, 0.0]
