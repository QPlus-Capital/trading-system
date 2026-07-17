"""Tests for the pure runner helpers, the paper-config factories, and risk-state persistence."""

from pathlib import Path
from typing import cast

from core.strategies.rsi_wpr_bb_signals import SignalParams
from live.mt5_bridge import Mt5Bridge, Position, Side, SymbolInfo
from live.risk_control import RiskController, RiskLimits
from live.runner import (
    LiveRunner,
    exit_prices,
    long_only_from_paper_config,
    markets_from_paper_config,
    position_risk,
    risk_per_trade_from_paper_config,
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


def test_live_and_backtest_place_their_exits_at_identical_prices() -> None:
    """The guard on "live == backtest": both must derive SL/TP from the fill by the same rule.

    They are separate code paths (a NautilusTrader strategy and an MT5 runner), so nothing but a
    test stops them drifting apart -- and a drift here silently changes the risk per trade.
    """
    from core.strategies.rsi_wpr_bb import exit_prices as backtest_exit_prices
    from nautilus_trader.model.enums import OrderSide

    sides: list[tuple[Side, OrderSide]] = [("BUY", OrderSide.BUY), ("SELL", OrderSide.SELL)]
    for side, order_side in sides:
        live_sl, live_tp = exit_prices(side, 2002.0, 1.0, 3.0)
        _exit_side, bt_sl, bt_tp = backtest_exit_prices(2002.0, order_side, 1.0, 3.0)
        assert live_sl == bt_sl
        assert live_tp == bt_tp


def test_exit_prices_anchor_a_long_below_and_a_short_above() -> None:
    assert exit_prices("BUY", 2000.0, 1.0, 3.0) == (1980.0, 2060.0)
    assert exit_prices("SELL", 2000.0, 1.0, 3.0) == (2020.0, 1940.0)


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


def test_position_risk_without_stop_is_worst_case() -> None:
    # H5: no stop-loss -> charged the worst case (price to zero), never 0.
    pos = Position(1, "XAUUSD", "BUY", 0.20, 2000.0, 0.0, 0.0, 0.0)
    # (2000/0.01)*1 * 0.20 lots = 200000 * 0.20 = 40_000.
    assert position_risk(pos, _GOLD) == 40_000.0


def test_risk_amount_compounds_off_current_equity() -> None:
    # Fixed-fractional: sizing risk is a fixed fraction of the CURRENT equity, so it grows
    # with the account (compounding), not pinned to the initial balance.
    bridge = cast(Mt5Bridge, object())
    risk = RiskController(RiskLimits(), 100_000)  # default risk_per_trade = 0.18%
    runner = LiveRunner(bridge, [], SignalParams(), risk)
    assert abs(runner._risk_amount(100_000) - 180.0) < 1e-6  # 0.18% of the starting equity
    assert abs(runner._risk_amount(150_000) - 270.0) < 1e-6  # grows with equity: 0.18% of 150k


def test_markets_from_paper_config_maps_all_ten() -> None:
    specs = markets_from_paper_config()
    names = {s.name for s in specs}
    assert len(specs) == 10
    assert "USTEC" in names  # our research name; the bridge maps it to UT100
    assert "XAGUSD" in names  # silver, added with a robust 0.5% stop (not the tight 0.3% fit)
    for s in specs:
        assert s.stop_loss_pct > 0 and s.take_profit_pct > 0


def test_signal_params_from_paper_config_is_no_bb_wpr() -> None:
    p = signal_params_from_paper_config()
    assert p.use_bb_confirm is False
    assert p.use_wpr_confirm is False
    assert p.use_rsi_filter is True


def test_long_only_from_paper_config_is_false() -> None:
    # The frozen config trades both directions (long/short reversal).
    assert long_only_from_paper_config() is False


def test_risk_per_trade_from_paper_config() -> None:
    # The config is the single source; sized at the framework's gap tail cap for no_bb_wpr
    # (3% daily / (1.5 x -11.1R worst day) = 0.18%), the largest flat risk a 1.5x-COVID gap day
    # still keeps inside the hard 3% daily limit.
    r = risk_per_trade_from_paper_config()
    assert abs(r - 0.0018) < 1e-9  # 0.18%
    assert 0 < r <= 0.0018  # at the tail cap, never above it


def test_risk_snapshot_restore_roundtrip() -> None:
    c = RiskController(RiskLimits(), 100_000)
    c.on_eod(105_000)  # HWM banked at 105k
    c.on_new_day(103_000)  # a new trading day started at 103k
    other = RiskController(RiskLimits(), 1.0)
    other.restore(c.snapshot())
    assert other.start_balance == 100_000
    assert other.hwm_balance == 105_000
    assert other.day_start_balance == 103_000


def test_risk_state_survives_restart(tmp_path: Path) -> None:
    # K1: a restart must NOT reset the trailing HWM / start balance to the current balance.
    state = tmp_path / "risk_state.json"
    # The runner only touches the bridge during cycles, not on load/persist.
    bridge = cast(Mt5Bridge, object())

    r1 = RiskController(RiskLimits(), 100_000)
    run1 = LiveRunner(bridge, [], SignalParams(), r1, state_path=state)  # persists initial 100k
    r1.on_eod(105_000)  # account grew during the day -> true HWM 105k
    run1._persist()  # a live day-roll persists this

    # Restart while in drawdown at 102k; the SAVED state must win over the provisional balance.
    r2 = RiskController(RiskLimits(), 102_000)
    LiveRunner(bridge, [], SignalParams(), r2, state_path=state)
    assert r2.start_balance == 100_000  # not the 102k restart balance
    assert r2.hwm_balance == 105_000  # true HWM preserved
    # Trailing floor stays at the true reference (capped at start), not the reset-down value.
    assert r2.trailing_floor() == 100_000  # min(100k, 105k - 5% of 100k); buggy reset gave 96_900
