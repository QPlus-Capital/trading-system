"""Tests for the live risk-control layer (safety-critical)."""

from live.risk_control import RiskController, RiskLimits, position_volume


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
    c.open_risk = 3_800  # cap is 2.0% of 200k = 4000
    d = c.check_open(400, 200_000)  # 3800 + 400 = 4200 > 4000
    assert not d.allowed and "open-risk" in d.reason


def test_check_open_blocks_on_daily_worst_case() -> None:
    # Already 2% down intraday; a further worst-case stop-out would breach the 2.5% daily stop.
    c = RiskController(RiskLimits(), 200_000)
    c.open_risk = 900  # within the 3000 cap
    d = c.check_open(400, 196_000)  # worst 196000-1300=194700 < daily floor 195000
    assert not d.allowed and "daily" in d.reason


def test_check_open_exclude_risk_allows_reversal() -> None:
    # M2: the position being closed on a reversal must not count against its replacement.
    c = RiskController(RiskLimits(), 200_000)
    c.open_risk = 3_800  # near the 4000 cap; e.g. a large opposite position we will close
    assert not c.check_open(400, 200_000).allowed  # 3800 + 400 > 4000 -> blocked
    assert c.check_open(400, 200_000, exclude_risk=3_800).allowed  # excluded -> 0 + 400, fine


def test_the_gate_budget_admits_a_full_book_but_blocks_beyond_it() -> None:
    # #5: the pre-trade budget is gate_daily_stop (2.7%), sized so a FULL book of 10 markets
    # @ 0.18% fits its stressed tail exactly: day-start 50k -> budget 1350; 10 x 90 = 900
    # nominal, 1.5 * 900 = 1350. An 11th entry (1.5 * 990 = 1485) breaches it.
    c = RiskController(RiskLimits(), 50_000)
    c.open_risk = 810  # 9 markets already open @ 90
    assert c.check_open(90, 50_000).allowed  # 10th: 1.5*900 = 1350 <= 1350
    c.open_risk = 900  # the full book of 10
    d = c.check_open(90, 50_000)  # an 11th: 1.5*990 = 1485 > 1350
    assert not d.allowed and "daily" in d.reason


def test_the_halt_stays_stricter_than_the_gate_budget() -> None:
    # The gate pre-authorises a 2.7% tail, but the HALT must still fire at 2.5% so flattening
    # starts early and keeps the full execution buffer below TTP's hard 3%.
    c = RiskController(RiskLimits(), 50_000)
    assert c.daily_floor() == 48_750  # halt at -2.5%
    assert c.gate_daily_floor() == 48_650  # gate budget reaches -2.7%
    assert c.prop_daily_floor() == 48_500  # TTP's hard -3% stays the outer bound
    assert c.must_flatten(48_700).allowed  # between the two -> already halting


def test_floating_profit_does_not_enlarge_the_loss_budget() -> None:
    # #5: day starts at 50k, floating profit lifts equity to 55k. Sizing is off 55k but the loss
    # budget stays anchored to the 50k day-start -- a gap can wipe the floating profit first. So an
    # entry whose stressed tail (1650) exceeds the day-start daily budget (1250) is BLOCKED even
    # though it would fit a naive 55k-based budget (6250).
    c = RiskController(RiskLimits(), 50_000)
    c.open_risk = 1_000
    d = c.check_open(100, 55_000)  # 1.5*(1000+100)=1650 > 1250 (day-start), < 6250 (equity)
    assert not d.allowed and "daily" in d.reason
