"""Tests for the instrument definitions."""

from core.instruments import (
    audusd_ttp,
    de40_ttp,
    eurusd_ttp,
    gbpusd_ttp,
    us30_ttp,
    us500_ttp,
    usdcad_ttp,
    usdchf_ttp,
    usdjpy_ttp,
    ustec_ttp,
    xagusd_ttp,
    xauusd_ttp,
)


def test_fx_instruments() -> None:
    for factory, symbol in [
        (eurusd_ttp, "EURUSD"),
        (gbpusd_ttp, "GBPUSD"),
        (audusd_ttp, "AUDUSD"),
        (usdchf_ttp, "USDCHF"),
        (usdcad_ttp, "USDCAD"),
    ]:
        inst = factory()
        assert str(inst.id) == f"{symbol}.TTP"
        assert inst.price_precision == 5
        assert str(inst.price_increment) == "0.00001"
        assert inst.lot_size == 100_000


def test_usdjpy_has_three_decimals() -> None:
    jpy = usdjpy_ttp()
    assert str(jpy.id) == "USDJPY.TTP"
    assert jpy.price_precision == 3  # JPY pairs quote with 3 decimals
    assert str(jpy.price_increment) == "0.001"


def test_silver_instrument() -> None:
    silver = xagusd_ttp()
    assert str(silver.id) == "XAGUSD.TTP"
    assert silver.price_precision == 3
    assert silver.lot_size == 5_000  # 1 lot = 5000 oz
    assert silver.taker_fee > 0  # metal: small commission per side


def test_index_instruments() -> None:
    us30 = us30_ttp()
    assert str(us30.id) == "US30.TTP"
    assert us30.price_precision == 2
    assert us30.taker_fee == 0  # indices: cost is in the spread, no commission

    de40 = de40_ttp()
    assert str(de40.id) == "DE40.TTP"
    assert de40.size_precision == 1  # volume step 0.1

    for factory, symbol in [(us500_ttp, "US500"), (ustec_ttp, "USTEC")]:
        idx = factory()
        assert str(idx.id) == f"{symbol}.TTP"
        assert idx.price_precision == 2
        assert idx.taker_fee == 0
        assert idx.size_precision == 2  # volume step 0.01


def test_gold_instrument_unchanged() -> None:
    gold = xauusd_ttp()
    assert str(gold.id) == "XAUUSD.TTP"
    assert gold.price_precision == 2
