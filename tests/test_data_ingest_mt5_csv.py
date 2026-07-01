"""Tests for the MetaTrader 5 CSV importer."""

from pathlib import Path

from nautilus_trader.model.data import BarType
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.data_ingest.mt5_csv import load_mt5_bars, write_mt5_catalog
from qplus.instruments import xauusd_ttp

_INSTRUMENT = xauusd_ttp()
_BAR_TYPE = BarType.from_str("XAUUSD.TTP-4-HOUR-LAST-EXTERNAL")

_SAMPLE = (
    "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    "2020.01.02\t00:00:00\t1517.97\t1521.37\t1517.23\t1519.44\t12111\t0\t2\n"
    "2020.01.02\t04:00:00\t1519.44\t1521.21\t1518.44\t1520.30\t8808\t0\t2\n"
)


def _write_sample(tmp_path: Path) -> Path:
    csv = tmp_path / "sample.csv"
    csv.write_text(_SAMPLE, encoding="utf-8")
    return csv


def test_load_mt5_bars_parses_ohlcv(tmp_path: Path) -> None:
    bars = load_mt5_bars(_write_sample(tmp_path), _INSTRUMENT, _BAR_TYPE)
    assert len(bars) == 2
    first = bars[0]
    assert str(first.open) == "1517.97"
    assert str(first.high) == "1521.37"
    assert str(first.low) == "1517.23"
    assert str(first.close) == "1519.44"
    # 4 hours between the two bars.
    assert bars[1].ts_event - bars[0].ts_event == 4 * 3600 * 1_000_000_000


def test_write_mt5_catalog_round_trip(tmp_path: Path) -> None:
    catalog_dir = tmp_path / "catalog"
    count = write_mt5_catalog(
        _write_sample(tmp_path), catalog_dir, instrument=_INSTRUMENT, bar_type=_BAR_TYPE
    )
    assert count == 2
    catalog = ParquetDataCatalog(str(catalog_dir))
    assert [str(i.id) for i in catalog.instruments()] == ["XAUUSD.TTP"]
