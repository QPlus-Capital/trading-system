"""Tests for the daily realized/equity curve construction (portfolio-stage support)."""

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.curves import (
    DAY_NS,
    align_prices,
    base_curves,
    to_day,
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


def test_base_curves_books_swap_realized_not_marked() -> None:
    # A swap must hit REALIZED at close only, never the floating (frac). That separation is what
    # keeps the mark-to-market drawdown stable when swaps are large (a fixed swap on a tiny-span
    # trade otherwise explodes the frac). See the TTP-swap incident.
    trades = pd.DataFrame(
        {
            "market": ["A"],
            "od": [0],
            "cd": [2],
            "pnl_base": [100.0],
            "swap_base": [-50.0],
            "entry": [100.0],
            "exit": [110.0],
        }
    )
    prices = {"A": np.array([100.0, 105.0, 110.0])}
    realized, unrealized = base_curves(trades, prices, 0, 2)
    assert list(realized) == [0.0, 0.0, 50.0]  # pnl+swap booked at close: 100 - 50
    assert unrealized[1] == 50.0  # open day 1, frac 0.5 on GROSS pnl (100*0.5); swap NOT marked


