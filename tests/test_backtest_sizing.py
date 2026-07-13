"""Tests for the sizing policies (flat vs drawdown-throttle)."""

import math

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.curves import base_curves
from qplus.backtest.portfolio.sizing import flat, simulate, throttle

_TRADES = pd.DataFrame(
    {
        "market": ["A", "B", "C"],
        "od": [1, 1, 2],
        "cd": [3, 3, 2],  # C opens AND closes on day 2 (same-day -> must not corrupt the sim)
        "pnl_base": [200.0, -100.0, 75.0],
        "entry": [100.0, 50.0, 20.0],
        "exit": [102.0, 49.0, 20.5],
    }
)
_PRICES = {
    "A": np.array([100.0, 99.0, 99.0, 102.0]),
    "B": np.array([50.0, 50.5, 50.5, 49.0]),
    "C": np.array([20.0, 20.0, 20.5, 20.5]),
}


def test_constant_throttle_reproduces_flat_scaling() -> None:
    # A constant risk_fn must give exactly start + m * base curves (validation of the loop).
    start, m = 200_000.0, 0.5
    realized_base, unreal_base = base_curves(_TRADES, _PRICES, 0, 3)
    equity_base = realized_base + unreal_base
    realized, equity, _sizes = simulate(_TRADES, _PRICES, 0, 3, start, 0.06, flat(m))
    assert np.allclose(realized, start + m * realized_base)
    assert np.allclose(equity, start + m * equity_base)


def test_compound_grows_geometrically_vs_flat() -> None:
    # Two sequential (non-overlapping) winning trades: the second opens AFTER the first realized
    # a gain, so compound sizes it up by equity/start -> compound ends above flat.
    trades = pd.DataFrame(
        {
            "market": ["A", "A"],
            "od": [0, 2],
            "cd": [1, 3],
            "pnl_base": [1000.0, 1000.0],
            "entry": [100.0, 100.0],
            "exit": [110.0, 110.0],
        }
    )
    prices = {"A": np.array([100.0, 110.0, 100.0, 110.0])}
    start, m = 100_000.0, 1.0
    flat_real, _e, _s = simulate(trades, prices, 0, 3, start, 0.06, flat(m), compound=False)
    comp_real, _e2, sizes = simulate(trades, prices, 0, 3, start, 0.06, flat(m), compound=True)
    assert comp_real[-1] > flat_real[-1]  # the grown equity compounded the second trade
    assert sizes[1] > m  # the later trade was sized up (equity/start = 1.01)


def test_throttle_policy_shape() -> None:
    fn = throttle(2.0, floor_frac=0.15)
    assert math.isclose(fn(0.0), 2.0)  # fresh buffer -> full base risk
    assert math.isclose(fn(0.5), 1.0)  # half budget used -> half risk
    assert math.isclose(fn(1.0), 0.3)  # at the wall -> floor (2.0 * 0.15)
