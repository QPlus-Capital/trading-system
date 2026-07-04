"""Tests for the live risk-control layer (safety-critical)."""

from qplus.live.risk_control import RiskController, RiskLimits, position_volume


def test_position_volume_sizes_to_risk() -> None:
    # loss_per_lot = (stop/tick)*tick_value = (20/0.01)*0.01 = 20 -> 400/20 = 20 lots.
    assert position_volume(400, 20, 0.01, 0.01, min_lot=0.01, lot_step=0.01, max_lot=100) == 20.0


def test_position_volume_below_min_lot_returns_zero() -> None:
    # Smallest lot would over-risk -> skip (never silently over-risk).
    assert position_volume(0.005, 1.0, 0.01, 0.01, min_lot=0.01, lot_step=0.01, max_lot=100) == 0.0


def test_position_volume_clamps_to_max_lot() -> None:
    assert position_volume(1e9, 1.0, 0.01, 0.01, min_lot=0.01, lot_step=0.01, max_lot=5) == 5.0


def test_trailing_floor_caps_at_start() -> None:
    c = RiskController(RiskLimits(), 200_000)
    assert c.trailing_floor() == 190_000  # start - 5%
    c.on_eod(220_000)
    assert c.trailing_floor() == 200_000  # caps at the starting balance


def test_daily_floor() -> None:
    assert RiskController(RiskLimits(), 200_000).daily_floor() == 195_000  # start - 2.5%


def test_must_flatten() -> None:
    c = RiskController(RiskLimits(), 200_000)
    assert c.must_flatten(189_000).allowed  # below the 190k trailing floor
    assert not c.must_flatten(196_000).allowed  # above both floors


def test_check_open_allows_within_budget() -> None:
    c = RiskController(RiskLimits(), 200_000)
    assert c.check_open(400, 200_000).allowed  # 0.2% risk, plenty of room


def test_check_open_blocks_on_open_risk_cap() -> None:
    c = RiskController(RiskLimits(), 200_000)
    c.open_risk = 2_800  # cap is 1.5% of 200k = 3000
    d = c.check_open(400, 200_000)  # 2800 + 400 = 3200 > 3000
    assert not d.allowed and "open-risk" in d.reason


def test_check_open_blocks_on_daily_worst_case() -> None:
    # Already 2% down intraday; a further worst-case stop-out would breach the 2.5% daily stop.
    c = RiskController(RiskLimits(), 200_000)
    c.open_risk = 900  # within the 3000 cap
    d = c.check_open(400, 196_000)  # worst 196000-1300=194700 < daily floor 195000
    assert not d.allowed and "daily" in d.reason
