"""Tests for the prop-firm hybrid drawdown rule."""

import math

from qplus.backtest.portfolio.drawdown import daily_breach, evaluate, trailing_floor


def test_daily_breach() -> None:
    assert not daily_breach([200_000, 197_000, 200_000], 0.03)  # 1.5% down day -> ok
    assert daily_breach([200_000, 193_000], 0.03)  # 3.5% down day -> breach
    assert not daily_breach([200_000, 100_000], 0.0)  # disabled


def test_floor_trails_balance_and_caps_at_start() -> None:
    # Balance rises to 212k then dips; floor = min(start, hwm - 12k), capped at 200k.
    floor = trailing_floor([200_000, 205_000, 212_000, 208_000], 200_000, 0.06)
    assert list(floor) == [188_000, 193_000, 200_000, 200_000]


def test_equity_breach_uses_floating() -> None:
    # Floor is 188k (no realized gains). Equity dips to 187k on floating loss -> breach.
    breached = evaluate([200_000, 187_000], [200_000, 200_000], 200_000, 0.06)
    assert breached.breached
    assert breached.breach_index == 1

    # A shallower floating dip to 190k stays above the 188k floor -> no breach.
    ok = evaluate([200_000, 190_000], [200_000, 200_000], 200_000, 0.06)
    assert not ok.breached
    assert ok.breach_index == -1
    assert math.isclose(ok.min_margin, 2_000.0)
