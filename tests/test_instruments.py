"""Tests for the instrument definitions."""

from qplus.instruments import (
    de40_ttp,
    eurusd_ttp,
    gbpusd_ttp,
    us30_ttp,
    xauusd_ttp,
)


def test_fx_instruments() -> None:
    for factory, symbol in [(eurusd_ttp, "EURUSD"), (gbpusd_ttp, "GBPUSD")]:
        inst = factory()
        assert str(inst.id) == f"{symbol}.TTP"
        assert inst.price_precision == 5
        assert str(inst.price_increment) == "0.00001"


def test_index_instruments() -> None:
    us30 = us30_ttp()
    assert str(us30.id) == "US30.TTP"
    assert us30.price_precision == 2
    assert us30.taker_fee == 0  # indices: cost is in the spread, no commission

    de40 = de40_ttp()
    assert str(de40.id) == "DE40.TTP"
    assert de40.size_precision == 1  # volume step 0.1


def test_gold_instrument_unchanged() -> None:
    gold = xauusd_ttp()
    assert str(gold.id) == "XAUUSD.TTP"
    assert gold.price_precision == 2
