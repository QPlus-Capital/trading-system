"""Tests for the pure swap-cost logic (night counting + per-night pricing)."""

import pandas as pd
from core.broker import SwapSpec, night_units, swap_per_lot_night
from research.portfolio.swap_analysis import market_swaps

_WED = 2  # python weekday for Wednesday


def _ns(day: str) -> int:
    return int(pd.Timestamp(day).value)


def test_night_units_same_day_is_zero() -> None:
    assert night_units(_ns("2024-01-01"), _ns("2024-01-01"), _WED) == 0.0


def test_night_units_one_weekday_night() -> None:
    # Mon -> Tue = one night (Monday's rollover).
    assert night_units(_ns("2024-01-01"), _ns("2024-01-02"), _WED) == 1.0


def test_night_units_full_week_triples_wednesday_skips_weekend() -> None:
    # Mon 2024-01-01 -> next Mon: nights Mon,Tue,Wed(x3),Thu,Fri, weekend 0 -> 1+1+3+1+1 = 7.
    assert night_units(_ns("2024-01-01"), _ns("2024-01-08"), _WED) == 7.0


def test_swap_per_lot_night_points() -> None:
    spec = SwapSpec(
        "POINTS",
        swap_long=-2.0,
        swap_short=-1.0,
        rollover_py=_WED,
        tick_value=0.87,
        tick_size=0.00001,
    )
    assert abs(swap_per_lot_night(spec, is_long=True, price=1.1) - (-1.74)) < 1e-9


def test_swap_per_lot_night_interest_short_is_a_credit() -> None:
    # Index short with a POSITIVE annual rate -> a credit: 40000 * 2.68% / 360 * (0.0087/0.01).
    spec = SwapSpec(
        "INT_CURRENT",
        swap_long=-6.93,
        swap_short=2.68,
        rollover_py=4,
        tick_value=0.0087,
        tick_size=0.01,
    )
    got = swap_per_lot_night(spec, is_long=False, price=40000.0)
    assert got > 0  # short pays nothing, receives
    assert abs(got - (40000.0 * 0.0268 / 360.0 * 0.87)) < 1e-6


def test_market_swaps_direction_and_sign() -> None:
    # One short winner on a POINTS symbol held one weekday night.
    trades = pd.DataFrame(
        {
            "ts_opened": [_ns("2024-01-01")],
            "ts_closed": [_ns("2024-01-02")],
            "entry": [2000.0],
            "exit": [1980.0],
            "r": [1.0],
            "swap_r": [-0.25],
            "net_r": [0.75],
        }  # price fell, r>0 -> short winner
    )
    spec = SwapSpec(
        "POINTS", swap_long=-2.0, swap_short=-1.5, rollover_py=_WED, tick_value=1.0, tick_size=0.01
    )
    m = market_swaps(trades, spec, sl_pct=1.0, risk_amount=300.0)
    assert not bool(m["is_long"].iloc[0])  # inferred short
    assert m["flat_pnl"].iloc[0] == 300.0  # risk_amount * gross r, never pre-netted net_r
    assert m["swap_pnl"].iloc[0] < 0  # one night of the (negative) short swap
