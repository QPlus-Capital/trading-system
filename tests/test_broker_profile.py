"""Tests for the swappable broker profile and its wiring into the sweep recipe."""

from pathlib import Path

import pandas as pd
from core.broker import (
    FRICTIONLESS,
    MEX_ATLANTIC,
    BrokerProfile,
    SwapSpec,
    dump_swap_snapshot,
    load_swap_snapshot,
    swap_r_per_trade,
)


def test_frictionless_profile_has_no_fill_model() -> None:
    # No slippage -> no FillModel -> identical to the historical baseline venue.
    assert FRICTIONLESS.fill_model_config() is None


def test_slippage_profile_builds_a_fill_model() -> None:
    cfg = MEX_ATLANTIC.fill_model_config()
    assert cfg is not None
    assert cfg.config["prob_slippage"] == MEX_ATLANTIC.prob_slippage
    assert cfg.config["prob_fill_on_limit"] == 1.0


def test_fill_model_config_is_constructible_by_nautilus() -> None:
    # The importable config must actually resolve into a live FillModel (path + fields correct).
    from nautilus_trader.backtest.config import FillModelFactory

    cfg = MEX_ATLANTIC.fill_model_config()
    assert cfg is not None
    fill_model = FillModelFactory.create(cfg)
    assert fill_model is not None


def test_profile_is_frozen() -> None:
    p = BrokerProfile(name="x", prob_slippage=0.1)
    try:
        p.prob_slippage = 0.2  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("BrokerProfile should be immutable")


def test_recipe_default_venue_is_frictionless() -> None:
    # Default recipe (no broker) must carry no fill model -> baseline unchanged.
    from core.instruments import xauusd
    from research.engine.recipe import SweepRecipe

    recipe = SweepRecipe(xauusd(), "data/dummy.csv", leverage=100)
    assert recipe.VENUE.fill_model is None


def test_recipe_with_broker_wires_the_fill_model() -> None:
    from core.instruments import xauusd
    from research.engine.recipe import SweepRecipe

    recipe = SweepRecipe(xauusd(), "data/dummy.csv", leverage=100, broker=MEX_ATLANTIC)
    assert recipe.VENUE.fill_model is not None
    assert recipe.VENUE.fill_model.config["prob_slippage"] == MEX_ATLANTIC.prob_slippage


def _spec() -> SwapSpec:
    return SwapSpec(
        mode="POINTS",
        swap_long=-2.0,
        swap_short=-1.5,
        rollover_py=2,
        tick_value=1.0,
        tick_size=0.01,
    )


def test_swap_snapshot_round_trips(tmp_path: Path) -> None:
    specs = {"XAUUSD": _spec(), "EURUSD": _spec()}
    path = tmp_path / "snap.json"
    dump_swap_snapshot(specs, path)
    back = load_swap_snapshot(path)
    assert back == specs  # frozen dataclasses compare by value


def test_with_swaps_attaches_specs_and_accessor_finds_them() -> None:
    profile = MEX_ATLANTIC.with_swaps({"XAUUSD": _spec()})
    assert profile.swap_spec("XAUUSD") == _spec()
    assert profile.swap_spec("NOPE") is None
    assert MEX_ATLANTIC.swap_specs == {}  # original is untouched (frozen copy)


def test_swap_r_per_trade_matches_hand_calc() -> None:
    # One short winner (price fell, r>0), one weekday night, POINTS mode.
    trades = pd.DataFrame(
        {
            "ts_opened": [int(pd.Timestamp("2024-01-01").value)],
            "ts_closed": [int(pd.Timestamp("2024-01-02").value)],
            "entry": [2000.0],
            "exit": [1980.0],
            "sl_pct": [1.0],
            "r": [1.0],
        }
    )
    swap_r = swap_r_per_trade(trades, _spec())
    # loss_per_lot = (2000*1%/0.01)*1.0 = 2000; 1 night * short swap(-1.5) / 2000
    assert abs(swap_r[0] - (-1.5 / 2000.0)) < 1e-15
    assert swap_r[0] < 0  # a cost


def test_instrument_spec_drives_commission_and_is_swappable() -> None:
    from decimal import Decimal

    from core.broker import TTP_MARKETS, InstrumentSpec
    from core.instruments import xauusd

    # Default profile reproduces the historical gold commission/margin (baseline preserved).
    assert xauusd().maker_fee == Decimal("0.000007")
    assert xauusd().margin_init == Decimal("0.10")

    # Swapping the profile swaps the broker terms -- no edit to instruments.py.
    cheap = TTP_MARKETS.with_instruments(
        {"XAUUSD": InstrumentSpec(Decimal("0.000001"), Decimal("0.000001"), Decimal("0.05"))}
    )
    assert xauusd(cheap).maker_fee == Decimal("0.000001")
    assert xauusd(cheap).margin_init == Decimal("0.05")


def test_instrument_spec_missing_fails_fast() -> None:
    import pytest
    from core.broker import FRICTIONLESS
    from core.instruments import xauusd

    empty = FRICTIONLESS.with_instruments({})
    with pytest.raises(KeyError, match="no instrument spec for 'XAUUSD'"):
        xauusd(empty)
