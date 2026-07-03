"""Tests for the Stage 3/4 portfolio feasibility scorecard."""

import math

import pandas as pd

from qplus.backtest.portfolio.curves import DAY_NS
from qplus.backtest.portfolio.scorecard import PortfolioResult, acceptance_verdict, score


def _result(**kw: float) -> PortfolioResult:
    base: dict[str, float] = {
        "n_trades": 50,
        "years": 2.0,
        "flat_risk": 1.0,
        "flat_return_pct": 20.0,
        "flat_ann_pct": 10.0,
        "throttle_base": 1.0,
        "throttle_return_pct": 25.0,
        "throttle_ann_pct": 12.5,
        "throttle_gain_pct": 25.0,
    }
    base.update(kw)
    return PortfolioResult(**base)  # type: ignore[arg-type]


def test_acceptance_verdict_pass_and_fail() -> None:
    trades = pd.DataFrame({"pnl_1pct": [200.0] * 50})  # all-positive -> MC prob ~1
    ok = acceptance_verdict(_result(), trades, start_balance=200_000.0)
    assert ok.passed and ok.prob_profit > 0.9

    # An infeasible config (no flat risk fits the DD limit) must fail the gate.
    bad = acceptance_verdict(
        _result(flat_risk=0.0, flat_return_pct=0.0), trades, start_balance=200_000.0
    )
    assert not bad.passed


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
