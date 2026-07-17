"""Tests for the instrument definitions."""

from core.instruments import (
    audusd,
    de40,
    eurusd,
    gbpusd,
    us30,
    us500,
    usdcad,
    usdchf,
    usdjpy,
    ustec,
    xagusd,
    xauusd,
)


def test_fx_instruments() -> None:
    for factory, symbol in [
        (eurusd, "EURUSD"),
        (gbpusd, "GBPUSD"),
        (audusd, "AUDUSD"),
        (usdchf, "USDCHF"),
        (usdcad, "USDCAD"),
    ]:
        inst = factory()
        assert str(inst.id) == f"{symbol}.TTP"
        assert inst.price_precision == 5
        assert str(inst.price_increment) == "0.00001"
        assert inst.lot_size == 100_000


def test_usdjpy_has_three_decimals() -> None:
    jpy = usdjpy()
    assert str(jpy.id) == "USDJPY.TTP"
    assert jpy.price_precision == 3  # JPY pairs quote with 3 decimals
    assert str(jpy.price_increment) == "0.001"


def test_silver_instrument() -> None:
    silver = xagusd()
    assert str(silver.id) == "XAGUSD.TTP"
    assert silver.price_precision == 3
    assert silver.lot_size == 5_000  # 1 lot = 5000 oz
    assert silver.taker_fee > 0  # metal: small commission per side


def test_index_instruments() -> None:
    us30_inst = us30()
    assert str(us30_inst.id) == "US30.TTP"
    assert us30_inst.price_precision == 2
    assert us30_inst.taker_fee == 0  # indices: cost is in the spread, no commission

    de40_inst = de40()
    assert str(de40_inst.id) == "DE40.TTP"
    assert de40_inst.size_precision == 1  # volume step 0.1

    for factory, symbol in [(us500, "US500"), (ustec, "USTEC")]:
        idx = factory()
        assert str(idx.id) == f"{symbol}.TTP"
        assert idx.price_precision == 2
        assert idx.taker_fee == 0
        assert idx.size_precision == 2  # volume step 0.01


def test_gold_instrument_unchanged() -> None:
    gold = xauusd()
    assert str(gold.id) == "XAUUSD.TTP"
    assert gold.price_precision == 2
