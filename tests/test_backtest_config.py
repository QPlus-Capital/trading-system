"""Tests for BacktestConfig validation and derived values."""

from decimal import Decimal

import pytest

from qplus.backtest.config import BacktestConfig


def test_defaults_are_usable() -> None:
    config = BacktestConfig()
    assert config.bar_type_str == "AUDUSD.OANDA-1-DAY-LAST-EXTERNAL"
    assert config.fast_ema_period < config.slow_ema_period


def test_bar_type_str_combines_instrument_and_spec() -> None:
    config = BacktestConfig(instrument_id="EURUSD.SIM", bar_spec="1-HOUR-MID-EXTERNAL")
    assert config.bar_type_str == "EURUSD.SIM-1-HOUR-MID-EXTERNAL"


def test_fast_period_must_be_below_slow() -> None:
    with pytest.raises(ValueError, match="fast_ema_period must be less than"):
        BacktestConfig(fast_ema_period=20, slow_ema_period=10)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fast_ema_period": 0},
        {"bar_count": 0},
        {"wave_period_bars": 0},
        {"trade_size": Decimal("0")},
        {"starting_balance": Decimal("-1")},
    ],
)
def test_rejects_non_positive_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        BacktestConfig(**kwargs)  # type: ignore[arg-type]
