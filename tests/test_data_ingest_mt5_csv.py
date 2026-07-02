"""Tests for the MetaTrader 5 CSV importer (bid + ask reconstruction)."""

from pathlib import Path

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.data_ingest.mt5_csv import load_mt5_bid_ask_bars, write_mt5_catalog
from qplus.instruments import xauusd_ttp

_INSTRUMENT = xauusd_ttp()

# Spread 2 points; tick size 0.01 -> ask = bid + 0.02.
_SAMPLE = (
    "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    "2020.01.02\t00:00:00\t1517.97\t1521.37\t1517.23\t1519.44\t12111\t0\t2\n"
    "2020.01.02\t04:00:00\t1519.44\t1521.21\t1518.44\t1520.30\t8808\t0\t2\n"
)


def _write_sample(tmp_path: Path) -> Path:
    csv = tmp_path / "sample.csv"
    csv.write_text(_SAMPLE, encoding="utf-8")
    return csv


def test_bid_ask_reconstruction(tmp_path: Path) -> None:
    bid_bars, ask_bars = load_mt5_bid_ask_bars(_write_sample(tmp_path), _INSTRUMENT)
    assert len(bid_bars) == len(ask_bars) == 2

    # Bid bars are the raw OHLC; ask = bid + spread (2 points = 0.02).
    assert str(bid_bars[0].close) == "1519.44"
    assert str(ask_bars[0].close) == "1519.46"
    assert str(bid_bars[0].open) == "1517.97"
    assert str(ask_bars[0].open) == "1517.99"

    assert "BID" in str(bid_bars[0].bar_type)
    assert "ASK" in str(ask_bars[0].bar_type)
    # 4 hours between the two bars.
    assert bid_bars[1].ts_event - bid_bars[0].ts_event == 4 * 3600 * 1_000_000_000


def test_write_mt5_catalog_round_trip(tmp_path: Path) -> None:
    catalog_dir = tmp_path / "catalog"
    count = write_mt5_catalog(
        _write_sample(tmp_path), catalog_dir, instrument=_INSTRUMENT, bar_spec="4-HOUR"
    )
    assert count == 2  # bars per side
    catalog = ParquetDataCatalog(str(catalog_dir))
    assert [str(i.id) for i in catalog.instruments()] == ["XAUUSD.TTP"]
