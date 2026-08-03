"""The exits must fill at their own levels -- the assumption risk-based position sizing rests on.

Sizing computes the quantity so a stop-out loses exactly ``risk_per_trade_pct`` of equity ("1R").
That promise breaks if the exit does not fill at the stop: the realised loss becomes a multiple of
the intended risk, every downstream R-multiple is fiction, and a parameter search will pin the stop
to the tightest grid value to farm the inflated R. (It did: losses reached -25R and the walk-forward
chose the grid's minimum stop in 98% of windows.)

Three links, tested separately:

1. ``exit_prices`` anchors both levels to the ACTUAL fill price (pure, here);
2. a resting ``STOP_MARKET`` fills at its trigger on a trade-through and at the gapped price on a
   genuine gap (``test_gap_through_stop.py``);
3. end-to-end, a position exits on exactly ONE leg, at that leg's price -- not on the next bar's
   open, and not split across both legs (here).

Together: stop-out cost == the stop distance == 1R, except across a real gap, where losing more is
correct and unavoidable.
"""

from pathlib import Path

import pandas as pd
import pytest
from core.instruments import eurusd, us30
from core.strategies.rsi_wpr_bb import exit_prices, risk_quantity
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from research.engine.config import parse_money

from tests.helpers.synthetic import write_synthetic_catalog

_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-4-HOUR-LAST-EXTERNAL")
_SL_PCT = 1.0
_TP_PCT = 2.0


# -- link 1: the levels are anchored to the fill --------------------------------------------------


def test_exit_prices_anchor_to_the_fill_price_for_a_long() -> None:
    side, sl, tp = exit_prices(100.0, OrderSide.BUY, stop_loss_pct=1.0, take_profit_pct=2.0)
    assert side == OrderSide.SELL  # a long exits by selling
    assert sl == pytest.approx(99.0)  # 1% below the fill -> a stop-out costs exactly 1R
    assert tp == pytest.approx(102.0)


def test_exit_prices_anchor_to_the_fill_price_for_a_short() -> None:
    side, sl, tp = exit_prices(100.0, OrderSide.SELL, stop_loss_pct=1.0, take_profit_pct=2.0)
    assert side == OrderSide.BUY
    assert sl == pytest.approx(101.0)  # mirrored: the stop sits ABOVE a short's fill
    assert tp == pytest.approx(98.0)


# -- link 0: a tradeable size is never refused -----------------------------------------------------


def test_a_fractional_index_size_is_tradeable_not_skipped() -> None:
    # US30 steps in 0.01 lots. On a 100k account a 2% stop near the index's high needs ~0.95 lots
    # -- valid, but an old `>= 1` floor refused it and dropped the trade in silence.
    us30_inst = us30()
    assert float(us30_inst.size_increment) == 0.01
    qty = risk_quantity(us30_inst, risk_amount=1_000.0, sl_distance=52_725.0 * 0.02)
    assert qty is not None and float(qty) == pytest.approx(0.95, abs=0.01)


def test_a_size_below_one_increment_is_refused_rather_than_rounded_to_zero() -> None:
    # make_qty raises instead of rounding to zero, so sizes under one increment must be refused.
    assert risk_quantity(us30(), risk_amount=1.0, sl_distance=1_000.0) is None
    # EURUSD steps in whole units -> anything under 1 unit is genuinely untradeable.
    assert float(eurusd().size_increment) == 1.0
    assert risk_quantity(eurusd(), risk_amount=0.5, sl_distance=1.0) is None


def test_whole_unit_instruments_keep_their_effective_floor() -> None:
    qty = risk_quantity(eurusd(), risk_amount=1_000.0, sl_distance=0.0021)
    assert qty is not None and float(qty) == pytest.approx(476_190, abs=1)


# -- link 3: end-to-end, one leg, at its own price -------------------------------------------------


def _run(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    write_synthetic_catalog(tmp_path, instrument=_INSTRUMENT, bar_type=_BAR_TYPE, bar_count=800)
    cfg = BacktestRunConfig(
        venues=[
            BacktestVenueConfig(
                name=_INSTRUMENT.id.venue.value,
                oms_type="HEDGING",  # one closed Position per round trip -> clean per-trade R
                account_type="MARGIN",
                base_currency="USD",
                starting_balances=["1_000_000 USD"],
                default_leverage=30.0,
            )
        ],
        data=[
            BacktestDataConfig(
                catalog_path=str(tmp_path),
                data_cls="nautilus_trader.model.data:Bar",
                instrument_id=str(_INSTRUMENT.id),
                bar_types=[str(_BAR_TYPE)],
            )
        ],
        engine=BacktestEngineConfig(
            strategies=[
                ImportableStrategyConfig(
                    strategy_path="core.strategies.rsi_wpr_bb:RsiWprBb",
                    config_path="core.strategies.rsi_wpr_bb:RsiWprBbConfig",
                    config={
                        "instrument_id": str(_INSTRUMENT.id),
                        "bar_type": str(_BAR_TYPE),
                        "trade_size": "100_000",
                        "stop_loss_pct": _SL_PCT,
                        "take_profit_pct": _TP_PCT,
                        "risk_per_trade_pct": 1.0,
                    },
                )
            ],
            logging=LoggingConfig(bypass_logging=True),
        ),
        dispose_on_completion=False,
    )
    node = BacktestNode(configs=[cfg])
    try:
        node.run()
        trader = node.get_engines()[0].trader
        return trader.generate_positions_report(), trader.generate_order_fills_report()
    finally:
        node.dispose()  # type: ignore[no-untyped-call]


def test_each_position_exits_on_exactly_one_leg(tmp_path: Path) -> None:
    # A passive LIMIT target is capped by the BAR's volume in a bar backtest. With MT5 tick counts
    # as volume that cap bound hard: the target filled a sliver, the stop closed the remainder, and
    # one trade exited on both legs. Exits are now taker orders against a non-binding bar volume.
    _pos, fills = _run(tmp_path)
    exits = fills[(fills["status"] == "FILLED") & (fills["is_reduce_only"])]
    assert not exits.empty, "expected reduce-only exit fills"
    legs = exits.groupby("position_id").size()
    assert legs.max() == 1, f"a position exited on {legs.max()} legs: {legs[legs > 1].to_dict()}"


def test_exits_fill_at_their_own_level_not_the_next_bar_open(tmp_path: Path) -> None:
    # Every trade here runs to its target. Filled AT the target, the payoff is exactly TP/SL in R.
    # Closed on the following bar's open instead, R would scatter around that ratio.
    pos, _fills = _run(tmp_path)
    closed = pos[pos["ts_closed"].notna()].copy()
    assert len(closed) > 5, "need a few closed trades to judge"

    pnl = closed["realized_pnl"].map(parse_money)
    qty = closed["peak_qty"].astype(float)  # 'quantity' is 0 on a closed (flat) position
    risk = qty * closed["avg_px_open"].astype(float) * (_SL_PCT / 100.0)
    r = pnl / risk

    expected = _TP_PCT / _SL_PCT  # +2R at TP 2% / SL 1%
    assert r.min() > 0, "on this rising-target series no trade should stop out"
    # Within costs (spread + commission), every winner pays exactly the target's R.
    assert abs(r.mean() - expected) < 0.05, f"mean {r.mean():.3f}R, expected ~{expected}R"
    assert r.std() < 0.02, f"R must be near-constant when exits fill at the level: {r.std():.3f}"
