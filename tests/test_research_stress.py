"""Tests for the tail-stress ceiling."""

import pandas as pd
from research.portfolio.curves import DAY_NS
from research.portfolio.stress import (
    stress_ceiling,
    survives,
    tail_safe_risk,
    worst_day_r,
    worst_trade_r,
)


def _trades() -> pd.DataFrame:
    # Two trades on day 0 (-2R and -3R -> worst day -5R), one -4R trade on day 1.
    d0, d1 = 0, 1 * DAY_NS
    return pd.DataFrame(
        {"ts_closed": [d0, d0, d1], "r": [-2.0, -3.0, -4.0]}
    )


def test_worst_trade_and_day() -> None:
    t = _trades()
    assert worst_trade_r(t) == -4.0  # worst single trade
    assert worst_day_r(t) == -5.0  # day 0 summed (-2 + -3)


def test_tail_safe_risk_binds_on_the_daily_limit() -> None:
    # A -10R worst-day event at stress 1.5 -> 15R; 3% daily / 15 = 0.2% max flat risk.
    assert abs(tail_safe_risk(-10.0, stress_mult=1.5) - 0.03 / 15.0) < 1e-12
    # No stress just needs to survive the raw worst day: 3% / 10 = 0.3%.
    assert abs(tail_safe_risk(-10.0, stress_mult=1.0) - 0.03 / 10.0) < 1e-12


def test_stress_ceiling_uses_worst_day() -> None:
    r = stress_ceiling(_trades(), stress_mult=2.0)
    # worst day -5R x 2 = 10R; 3% / 10 = 0.3% safe risk.
    assert r.worst_day_r == -5.0
    assert abs(r.tail_safe_risk_pct - 0.3) < 1e-9


def test_survives_gate() -> None:
    t = _trades()  # worst day -5R; at stress 1.5 -> 7.5R; safe = 3%/7.5 = 0.4%
    assert survives(t, 0.003, stress_mult=1.5)  # 0.3% <= 0.4% -> survives
    assert not survives(t, 0.005, stress_mult=1.5)  # 0.5% > 0.4% -> breaches under stress
