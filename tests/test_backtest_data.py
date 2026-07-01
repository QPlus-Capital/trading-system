"""Tests for the deterministic synthetic bar generator."""

from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from qplus.backtest.config import BacktestConfig
from qplus.backtest.data import make_synthetic_bars

_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-1-DAY-LAST-EXTERNAL")


def test_generates_requested_bar_count() -> None:
    config = BacktestConfig(bar_count=50)
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, config)
    assert len(bars) == 50


def test_timestamps_increase_by_bar_step() -> None:
    config = BacktestConfig(bar_count=10)
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, config)
    step = int(_BAR_TYPE.spec.timedelta.value)
    diffs = {bars[i + 1].ts_event - bars[i].ts_event for i in range(len(bars) - 1)}
    assert diffs == {step}


def test_bars_are_never_single_price() -> None:
    # Single-price bars carry no directional info and are skipped by the strategy.
    config = BacktestConfig(bar_count=100)
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, config)
    assert all(not bar.is_single_price() for bar in bars)


def test_generation_is_deterministic() -> None:
    config = BacktestConfig(bar_count=40)
    first = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, config)
    second = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, config)
    assert [str(b) for b in first] == [str(b) for b in second]
