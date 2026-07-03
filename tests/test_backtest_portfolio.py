"""Tests for the Stage 3/4 portfolio feasibility scorecard."""

import math

import pandas as pd

from qplus.backtest.portfolio import score
from qplus.backtest.portfolio_sim import DAY_NS


def _trade(
    market: str, open_day: int, close_day: int, pnl: float, entry: float, exit_: float
) -> dict[str, object]:
    return {
        "market": market,
        "ts_opened": open_day * DAY_NS,
        "ts_closed": close_day * DAY_NS,
        "pnl_1pct": pnl,
        "entry": entry,
        "exit": exit_,
    }


def test_monotonic_winner_hits_the_risk_cap() -> None:
    # A trade that is never underwater can never breach -> flat risk hits the bisection cap.
    trades = pd.DataFrame([_trade("X", 0, 2, 100.0, 10.0, 11.0)])
    prices = {"X": pd.Series({0: 10.0, 1: 10.5, 2: 11.0})}
    res = score(trades, prices, throttle_bases=(1.0, 3.0))
    assert res.n_trades == 1
    assert math.isclose(res.flat_risk, 4.0)  # default bisection cap, never breaches
    assert math.isclose(res.flat_return_pct, round(4.0 * 100 / 200_000 * 100, 1))


def test_deep_floating_dip_forces_low_risk() -> None:
    # Big floating loss mid-trade (-50,000 per unit on day 1) binds the 6% (12,000) budget:
    # breach when m*50,000 >= 12,000 -> max safe m ~ 0.24.
    trades = pd.DataFrame([_trade("Y", 0, 2, 10_000.0, 10.0, 11.0)])
    prices = {"Y": pd.Series({0: 10.0, 1: 5.0, 2: 11.0})}
    res = score(trades, prices, throttle_bases=(0.1, 0.2, 0.3))
    assert math.isclose(res.flat_risk, 0.24, abs_tol=0.01)
    assert 0.0 < res.flat_risk < 1.0
