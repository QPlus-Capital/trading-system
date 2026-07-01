"""Tests for the EMACross strategy configuration and guards."""

from decimal import Decimal

import pytest
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId

from qplus.strategies.ema_cross import EMACross, EMACrossConfig

_INSTRUMENT_ID = InstrumentId.from_str("AUDUSD.OANDA")
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-1-DAY-LAST-EXTERNAL")


def _config(fast: int, slow: int) -> EMACrossConfig:
    return EMACrossConfig(
        instrument_id=_INSTRUMENT_ID,
        bar_type=_BAR_TYPE,
        trade_size=Decimal("100_000"),
        fast_ema_period=fast,
        slow_ema_period=slow,
    )


def test_valid_config_builds_strategy() -> None:
    strategy = EMACross(_config(fast=10, slow=20))
    assert strategy.fast_ema.period == 10
    assert strategy.slow_ema.period == 20


def test_rejects_fast_period_not_below_slow() -> None:
    with pytest.raises(ValueError):
        EMACross(_config(fast=20, slow=10))
