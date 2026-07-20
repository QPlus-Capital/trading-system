"""#32: the strategy honours its parameter schedule inside ONE continuous engine run.

These drive the real :class:`RsiWprBb` -- its sizing, its schedule lookup, its exit attachment --
through a real backtest engine. Only the entry *trigger* is forced, because reverse-engineering
bar sequences that fire the signal engine would test the indicators, not the schedule.

The property under test is the one a stitched walk-forward cannot have: a position opened before a
segment boundary keeps the stop and target that opened it.
"""

from __future__ import annotations

from decimal import Decimal

from core.instruments import us30
from core.strategies.param_schedule import ParamSegment
from core.strategies.rsi_wpr_bb import RsiWprBb, RsiWprBbConfig
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import TraderId, Venue
from nautilus_trader.model.objects import Money

_INSTR = us30()
_BAR_TYPE = BarType.from_str(f"{_INSTR.id}-1-HOUR-LAST-EXTERNAL")
_H = 3_600_000_000_000  # 1 hour in ns
_BOUNDARY = 5 * _H

#: Deliberately far apart, so which one was used is unmistakable in the stop trigger price.
_OLD = ParamSegment(from_ns=0, stop_loss_pct=1.0, take_profit_pct=2.0)
_NEW = ParamSegment(from_ns=_BOUNDARY, stop_loss_pct=5.0, take_profit_pct=10.0)


class _ForcedEntry(RsiWprBb):
    """Real strategy, but the entry fires on a chosen bar instead of on a signal."""

    def __init__(self, config: RsiWprBbConfig, enter_at_ns: int) -> None:
        super().__init__(config)
        self._enter_at = enter_at_ns
        self._done = False

    def on_bar(self, bar: Bar) -> None:
        if self._done or bar.ts_event != self._enter_at:
            return
        self._done = True
        if not self._entries_allowed(bar.ts_event):
            return  # the schedule refuses this instant -- the behaviour under test
        self._go_long(bar.close.as_double(), bar.ts_event)


def _bar(price: float, ts: int) -> Bar:
    p = _INSTR.make_price
    return Bar(_BAR_TYPE, p(price), p(price), p(price), p(price), _INSTR.make_qty(1), ts, ts)


def _run(enter_at_ns: int, segments: tuple[ParamSegment, ...]) -> dict[str, float]:
    """Run a flat market across the boundary; return the resting exit trigger prices."""
    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId("T-001"), logging=LoggingConfig(bypass_logging=True)
        )
    )
    engine.add_venue(
        venue=Venue("TTP"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
        fill_model=FillModel(),
    )
    engine.add_instrument(_INSTR)
    # A perfectly flat market: nothing can hit a stop or target, so both legs stay resting and
    # their trigger prices are readable at the end.
    engine.add_data([_bar(100.0, i * _H) for i in range(1, 11)])
    config = RsiWprBbConfig(
        instrument_id=_INSTR.id,
        bar_type=_BAR_TYPE,
        trade_size=Decimal(1),
        segments=segments,
    )
    engine.add_strategy(_ForcedEntry(config, enter_at_ns))
    try:
        engine.run()
        orders = engine.trader.generate_orders_report()
        out: dict[str, float] = {"entries": 0.0}
        if "type" not in orders:  # no order at all -> an empty report has no columns
            return out
        for kind in ("STOP_MARKET", "MARKET_IF_TOUCHED"):
            rows = orders[orders["type"] == kind]
            if len(rows):
                out[kind] = float(rows["trigger_price"].iloc[0])
        # BUY only: on_stop flattens the position with a closing MARKET order of its own, which
        # would otherwise be counted as a second entry.
        entries = orders[(orders["type"] == "MARKET") & (orders["side"] == "BUY")]
        out["entries"] = float(len(entries))
        return out
    finally:
        engine.dispose()


def test_a_position_opened_before_the_boundary_keeps_the_old_stop_and_target() -> None:
    """The acceptance criterion a stitched walk-forward cannot satisfy.

    Entry fires one bar before the boundary and the position lives across it with a 1% stop --
    the OLD segment's -- rather than the 5% the next segment chose.

    Scope, precisely: a market entry fills inside its own bar, so the position's open time and
    the moment its exits are attached are the same instant. This therefore verifies the OUTCOME
    (a boundary-straddling position keeps its original stop and target) but cannot distinguish
    keying the lookup on ``event.ts_opened`` from keying it on "now". ``ts_opened`` is used
    because it stays correct if attachment ever becomes deferred; that choice is not what this
    test pins.
    """
    exits = _run(enter_at_ns=4 * _H, segments=(_OLD, _NEW))
    assert exits["entries"] == 1
    assert abs(exits["STOP_MARKET"] - 99.0) < 0.01, "stop must be the OLD segment's 1%"
    assert abs(exits["MARKET_IF_TOUCHED"] - 102.0) < 0.01, "target must be the OLD segment's 2%"


def test_a_position_opened_after_the_boundary_uses_the_new_parameters() -> None:
    exits = _run(enter_at_ns=6 * _H, segments=(_OLD, _NEW))
    assert abs(exits["STOP_MARKET"] - 95.0) < 0.01, "stop must be the NEW segment's 5%"
    assert abs(exits["MARKET_IF_TOUCHED"] - 110.0) < 0.01, "target must be the NEW segment's 10%"


def test_no_entry_is_placed_in_an_interval_no_window_owns() -> None:
    """Acceptance: no order opens during an embargo or gap."""
    closed = ParamSegment(from_ns=3 * _H, stop_loss_pct=0.0, take_profit_pct=0.0,
                          entries_allowed=False)
    exits = _run(enter_at_ns=6 * _H, segments=(_OLD, closed))
    assert exits["entries"] == 0


def test_nothing_opens_before_the_schedule_begins() -> None:
    """The pre-roll warms indicators; it must not be handed a default parameter set to trade."""
    later = ParamSegment(from_ns=8 * _H, stop_loss_pct=1.0, take_profit_pct=2.0)
    exits = _run(enter_at_ns=4 * _H, segments=(later,))
    assert exits["entries"] == 0


def test_without_a_schedule_the_static_config_still_governs() -> None:
    """The single-window path must be untouched: an empty schedule changes nothing."""
    engine_exits = _run_static()
    assert abs(engine_exits["STOP_MARKET"] - 99.5) < 0.01
    assert abs(engine_exits["MARKET_IF_TOUCHED"] - 103.0) < 0.01


def _run_static() -> dict[str, float]:
    engine = BacktestEngine(
        BacktestEngineConfig(
            trader_id=TraderId("T-002"), logging=LoggingConfig(bypass_logging=True)
        )
    )
    engine.add_venue(
        venue=Venue("TTP"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
        fill_model=FillModel(),
    )
    engine.add_instrument(_INSTR)
    engine.add_data([_bar(100.0, i * _H) for i in range(1, 11)])
    config = RsiWprBbConfig(
        instrument_id=_INSTR.id,
        bar_type=_BAR_TYPE,
        trade_size=Decimal(1),
        stop_loss_pct=0.5,
        take_profit_pct=3.0,
    )
    engine.add_strategy(_ForcedEntry(config, 4 * _H))
    try:
        engine.run()
        orders = engine.trader.generate_orders_report()
        return {
            kind: float(orders[orders["type"] == kind]["trigger_price"].iloc[0])
            for kind in ("STOP_MARKET", "MARKET_IF_TOUCHED")
        }
    finally:
        engine.dispose()
