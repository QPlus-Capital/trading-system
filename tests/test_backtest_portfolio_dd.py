"""Tests for the prop-firm hybrid drawdown rule (Stage 3)."""

import math

from qplus.backtest.portfolio.drawdown import (
    daily_breach,
    evaluate,
    max_flat_risk,
    trailing_floor,
)


def test_daily_breach() -> None:
    assert not daily_breach([200_000, 197_000, 200_000], 0.03)  # 1.5% down day -> ok
    assert daily_breach([200_000, 193_000], 0.03)  # 3.5% down day -> breach
    assert not daily_breach([200_000, 100_000], 0.0)  # disabled


def test_max_flat_risk_daily_limit_binds() -> None:
    # A big day-2 drop (-100k per unit). Trailing (6%) allows m up to 0.12; the daily 3%
    # limit (6k of the 200k day-start) binds first at m ~ 0.06.
    r, e = [0.0, 0.0], [0.0, -100_000.0]
    assert math.isclose(max_flat_risk(r, e, 200_000, 0.06), 0.12, abs_tol=1e-3)
    assert math.isclose(max_flat_risk(r, e, 200_000, 0.06, day_loss_frac=0.03), 0.06, abs_tol=1e-3)


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


def test_max_flat_risk_bisects_to_the_limit() -> None:
    # Excess curves at multiple 1: no realized change, a -24k floating dip on day 2.
    # Floor excess = -12k (6% of 200k). Breach when m*24k >= 12k -> m >= 0.5.
    m = max_flat_risk([0.0, 0.0], [0.0, -24_000.0], 200_000, 0.06)
    assert math.isclose(m, 0.5, abs_tol=1e-2)


def test_max_flat_risk_returns_cap_when_never_breached() -> None:
    m = max_flat_risk([0.0, 100.0], [0.0, 100.0], 200_000, 0.06, hi=3.0)
    assert m == 3.0
