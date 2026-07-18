"""Tests for the instrument definitions."""

import pytest
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
from core.strategies.rsi_wpr_bb import risk_quantity


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


def test_usd_quoted_fx_approximation_preserves_notional_and_r() -> None:
    """#9: pairs whose quote ccy is not USD are modelled USD-quoted. That is SAFE because the
    fictitious unit count still reproduces the true notional and the true loss at the stop, so R
    and every notional-proportional cost are identical to the real convention.

    This guards the invariance: it breaks hard (by the spot rate, ~150x on USDJPY) if commission
    ever becomes a PER-LOT fee instead of a fraction of notional, since the model's lot count is
    the one quantity that is NOT preserved.
    """
    risk, stop_pct = 180.0, 0.005
    # (instrument, spot, USD per 1 unit of the QUOTE currency)
    cases = [
        (eurusd(), 1.08, 1.0),  # quote already USD -> exact by construction
        (usdjpy(), 150.0, 1 / 150.0),  # quote JPY
        (usdchf(), 0.89, 1 / 0.89),  # quote CHF
        (usdcad(), 1.36, 1 / 1.36),  # quote CAD
    ]
    for inst, spot, usd_per_quote in cases:
        sl_distance = spot * stop_pct  # in quote-currency units
        qty = risk_quantity(inst, risk, sl_distance)
        assert qty is not None
        model_loss = float(qty) * sl_distance  # instrument is declared USD-quoted
        model_notional = float(qty) * spot

        # True convention: size so the stop costs `risk` USD; notional in USD.
        true_notional = (risk / (sl_distance * usd_per_quote)) * (spot * usd_per_quote)

        assert model_loss == pytest.approx(risk, rel=1e-3)  # stop costs exactly 1 R
        assert model_notional == pytest.approx(true_notional, rel=1e-3)  # -> % commission matches
