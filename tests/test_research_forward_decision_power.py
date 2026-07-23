"""Deterministic clustered power fixture for the forward-test bootstrap bound."""

from __future__ import annotations

from decimal import Decimal

from research.forward_decision import bootstrap_mean_bounds
from research.portfolio.resample import select_block_length

_DAYS_PER_YEAR = Decimal("365.25")
_TRADES_PER_DAY = Decimal("2.70")
_TEST_REPLICATIONS = 199


def _clustered_daily_r(days: int, per_trade_edge: Decimal) -> tuple[Decimal, ...]:
    """Return exact deterministic clustered daily R without binary-float statistics."""
    state = 116
    cluster = Decimal("0")
    noise: list[Decimal] = []
    for _ in range(days):
        state = (1_103_515_245 * state + 12_345) % (2**31)
        innovation = Decimal(state % 20_001 - 10_000) / Decimal("10000")
        cluster = Decimal("0.55") * cluster + innovation
        noise.append(cluster)
    noise_mean = sum(noise, Decimal("0")) / Decimal(days)
    return tuple(
        per_trade_edge * _TRADES_PER_DAY + Decimal("5") * (daily_noise - noise_mean)
        for daily_noise in noise
    )


def _detected(days: int, edge: Decimal) -> bool:
    values = _clustered_daily_r(days, edge)
    block_length = select_block_length({"clustered-power": tuple(map(str, values))})
    bounds = bootstrap_mean_bounds(
        values,
        block_length,
        Decimal("0.95"),
        replications=_TEST_REPLICATIONS,
    )
    return bounds.lower > Decimal("0")


def test_clustered_power_fixture_reproduces_detection_horizons() -> None:
    one_point_one_years = int(_DAYS_PER_YEAR * Decimal("1.1"))
    one_point_two_years = int(_DAYS_PER_YEAR * Decimal("1.2"))
    two_point_five_years = int(_DAYS_PER_YEAR * Decimal("2.5"))
    two_point_seven_years = int(_DAYS_PER_YEAR * Decimal("2.7"))

    assert not _detected(one_point_one_years, Decimal("0.15"))
    assert _detected(one_point_two_years, Decimal("0.15"))
    assert not _detected(two_point_five_years, Decimal("0.10"))
    assert _detected(two_point_seven_years, Decimal("0.10"))
