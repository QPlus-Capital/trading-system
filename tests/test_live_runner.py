"""Tests for the pure runner helpers and the paper-config factories."""

from qplus.live.mt5_bridge import Position, SymbolInfo
from qplus.live.runner import (
    markets_from_paper_config,
    position_risk,
    signal_params_from_paper_config,
    size_order,
)

# A gold-like symbol: 0.01 tick, $1 per tick per lot, 0.01..100 lots.
_GOLD = SymbolInfo(
    name="XAUUSD",
    digits=2,
    point=0.01,
    tick_size=0.01,
    tick_value=1.0,
    volume_min=0.01,
    volume_step=0.01,
    volume_max=100.0,
)


def test_size_order_long_sets_sl_tp_and_volume() -> None:
    # ref 2000, SL 1% -> stop 20 -> loss_per_lot=(20/0.01)*1=2000 -> 400/2000=0.2 lots.
    order = size_order("BUY", 2000.0, 1.0, 3.0, _GOLD, risk_amount=400.0)
    assert order is not None
    assert order.volume == 0.20
    assert order.sl == 1980.0  # 2000 * (1 - 1%)
    assert order.tp == 2060.0  # 2000 * (1 + 3%)
    assert abs(order.risk_amount - 400.0) < 1e-6


def test_size_order_short_flips_sl_tp() -> None:
    order = size_order("SELL", 2000.0, 1.0, 3.0, _GOLD, risk_amount=400.0)
    assert order is not None
    assert order.sl == 2020.0  # above entry for a short
    assert order.tp == 1940.0  # below entry for a short


def test_size_order_returns_none_when_below_min_lot() -> None:
    # Tiny risk budget -> volume rounds below the 0.01 min lot -> skip.
    assert size_order("BUY", 2000.0, 1.0, 3.0, _GOLD, risk_amount=1.0) is None


def test_position_risk_from_stop_distance() -> None:
    pos = Position(
        ticket=1,
        symbol="XAUUSD",
        side="BUY",
        volume=0.20,
        price_open=2000.0,
        sl=1980.0,
        tp=2060.0,
        profit=0.0,
    )
    # (|2000-1980|/0.01)*1 * 0.20 lots = 2000 * 0.20 = 400.
    assert abs(position_risk(pos, _GOLD) - 400.0) < 1e-6


def test_position_risk_zero_without_stop() -> None:
    pos = Position(1, "XAUUSD", "BUY", 0.20, 2000.0, 0.0, 0.0, 0.0)
    assert position_risk(pos, _GOLD) == 0.0


def test_markets_from_paper_config_maps_all_nine() -> None:
    specs = markets_from_paper_config()
    names = {s.name for s in specs}
    assert len(specs) == 9
    assert "USTEC" in names  # our research name; the bridge maps it to UT100
    for s in specs:
        assert s.stop_loss_pct > 0 and s.take_profit_pct > 0


def test_signal_params_from_paper_config_is_no_bb_wpr() -> None:
    p = signal_params_from_paper_config()
    assert p.use_bb_confirm is False
    assert p.use_wpr_confirm is False
    assert p.use_rsi_filter is True
