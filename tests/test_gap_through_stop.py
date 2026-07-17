"""Regression test locking in NautilusTrader's gap-through-stop fill behaviour.

Our cost model relies on the engine filling a stop-loss at the *gapped* price when a bar opens
beyond the stop (so a weekend/news gap that jumps the SL is charged in full), while a bar that
merely trades through the stop fills at the trigger (no false gap penalty). This is native
NautilusTrader behaviour -- this test guards it against silent changes on upgrade.
"""

from core.instruments import us30
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import TraderId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

_INSTR = us30()
_BAR_TYPE = BarType.from_str(f"{_INSTR.id}-1-HOUR-LAST-EXTERNAL")
_H = 3_600_000_000_000  # 1 hour in ns


class _GapCfg(StrategyConfig, frozen=True):  # type: ignore[misc,call-arg]
    pass


class _GapStrat(Strategy):  # type: ignore[misc]
    """Enter long at 100 on the first bar with a bracket SL at 95 (TP at 200, never hit)."""

    def __init__(self) -> None:
        super().__init__(_GapCfg())
        self.entered = False

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(_INSTR.id)
        self.subscribe_bars(_BAR_TYPE)

    def on_bar(self, bar: Bar) -> None:
        if not self.entered:
            self.entered = True
            self.submit_order_list(
                self.order_factory.bracket(
                    instrument_id=_INSTR.id,
                    order_side=OrderSide.BUY,
                    quantity=self.instrument.make_qty(1),
                    sl_trigger_price=self.instrument.make_price(95.00),
                    tp_price=self.instrument.make_price(200.00),
                )
            )


def _bar(o: float, h: float, low: float, c: float, ts: int) -> Bar:
    p = _INSTR.make_price
    return Bar(_BAR_TYPE, p(o), p(h), p(low), p(c), _INSTR.make_qty(1), ts, ts)


def _sl_fill_price(third_bar: Bar) -> float:
    """Run entry-at-100, SL-at-95, then ``third_bar``; return the stop-loss fill price."""
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
    engine.add_data(
        [
            _bar(100, 100, 100, 100, 1 * _H),  # submit bracket
            _bar(100, 100, 100, 100, 2 * _H),  # entry fills at 100; SL(95)/TP(200) rest
            third_bar,
            _bar(90, 90, 90, 90, 4 * _H),  # settle
        ]
    )
    engine.add_strategy(_GapStrat())
    try:
        engine.run()
        fills = engine.trader.generate_order_fills_report()
        sl = fills[fills["type"] == "STOP_MARKET"]
        assert len(sl) == 1, "expected exactly one stop-loss fill"
        return float(sl["avg_px"].iloc[0])
    finally:
        engine.dispose()


def test_gap_through_stop_fills_at_the_gapped_price() -> None:
    # Bar opens at 90 -- its whole range is below the SL(95). The full gap loss must be taken:
    # the fill is at ~90, NOT the optimistic trigger 95.
    px = _sl_fill_price(_bar(90, 91, 89, 90, 3 * _H))
    assert abs(px - 90.0) < 0.1, f"gap-through should fill near the gap open 90, got {px}"
    assert px < 93.0, f"gap-through must not fill at the optimistic trigger 95, got {px}"


def test_trade_through_stop_fills_at_the_trigger() -> None:
    # Bar opens at 96 (above the SL) and dips to 89 -- price genuinely trades through 95, so the
    # fill is at the trigger 95 (no false gap penalty).
    px = _sl_fill_price(_bar(96, 96, 89, 90, 3 * _H))
    assert abs(px - 95.0) < 0.1, f"trade-through should fill near the trigger 95, got {px}"
