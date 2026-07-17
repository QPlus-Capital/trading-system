"""Tests for the deterministic synthetic data generator and catalog writer."""

from pathlib import Path

from nautilus_trader.model.data import BarType
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from tests.helpers.synthetic import make_synthetic_bars, write_synthetic_catalog

_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-1-DAY-LAST-EXTERNAL")


def test_generates_requested_bar_count() -> None:
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, bar_count=50)
    assert len(bars) == 50


def test_timestamps_increase_by_bar_step() -> None:
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, bar_count=10)
    step = int(_BAR_TYPE.spec.timedelta.value)
    diffs = {bars[i + 1].ts_event - bars[i].ts_event for i in range(len(bars) - 1)}
    assert diffs == {step}


def test_bars_are_never_single_price() -> None:
    # Single-price bars carry no directional info and are skipped by the strategy.
    bars = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, bar_count=100)
    assert all(not bar.is_single_price() for bar in bars)


def test_generation_is_deterministic() -> None:
    first = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, bar_count=40)
    second = make_synthetic_bars(_INSTRUMENT, _BAR_TYPE, bar_count=40)
    assert [str(b) for b in first] == [str(b) for b in second]


def test_write_synthetic_catalog_round_trip(tmp_path: Path) -> None:
    count = write_synthetic_catalog(
        tmp_path, instrument=_INSTRUMENT, bar_type=_BAR_TYPE, bar_count=60
    )
    assert count == 60

    catalog = ParquetDataCatalog(str(tmp_path))
    stored_ids = [str(i.id) for i in catalog.instruments()]
    assert stored_ids == ["AUDUSD.OANDA"]
