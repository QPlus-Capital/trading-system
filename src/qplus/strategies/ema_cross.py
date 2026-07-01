"""EMA crossover strategy.

A simple trend-following example: two exponential moving averages (a fast and a
slow one) are maintained on the strategy's bar type. When the fast EMA is at or
above the slow EMA the strategy wants to be long; when it is below, short. On
every change of that desired direction it flattens any opposite position and
enters a new market position.

This is a plain demonstration strategy with no proven edge -- it exists so the
backtest skeleton has something realistic to run. The *same* class is used for
backtest and live; only the config differs (see ``config/backtest/``).
"""

from decimal import Decimal

from nautilus_trader.config import PositiveInt, StrategyConfig
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


class EMACrossConfig(StrategyConfig, frozen=True):
    """Configuration for :class:`EMACross`.

    Parameters
    ----------
    instrument_id : InstrumentId
        The instrument to trade.
    bar_type : BarType
        The bar type the EMAs are computed on.
    trade_size : Decimal
        The position size, in units of the instrument, entered per signal.
    fast_ema_period : PositiveInt, default 10
        The period of the fast EMA.
    slow_ema_period : PositiveInt, default 20
        The period of the slow EMA. Must be greater than ``fast_ema_period``.

    """

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: PositiveInt = 10
    slow_ema_period: PositiveInt = 20


class EMACross(Strategy):  # type: ignore[misc]
    """A fast/slow EMA crossover strategy.

    Long while the fast EMA is at or above the slow EMA, short otherwise.

    Raises
    ------
    ValueError
        If ``fast_ema_period`` is not less than ``slow_ema_period``.

    """

    def __init__(self, config: EMACrossConfig) -> None:
        PyCondition.is_true(
            config.fast_ema_period < config.slow_ema_period,
            "fast_ema_period must be less than slow_ema_period",
        )
        super().__init__(config)

        self.instrument: Instrument | None = None
        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)

    def on_start(self) -> None:
        """Resolve the instrument, wire up indicators and subscribe to bars."""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument {self.config.instrument_id}")
            self.stop()
            return

        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        """Act on each new bar once both EMAs are warmed up."""
        if not self.indicators_initialized():
            return

        # Bars with a single price carry no directional information.
        if bar.is_single_price():
            return

        if self.fast_ema.value >= self.slow_ema.value:
            self._go_long()
        else:
            self._go_short()

    def _go_long(self) -> None:
        instrument_id = self.config.instrument_id
        if self.portfolio.is_net_long(instrument_id):
            return
        if self.portfolio.is_net_short(instrument_id):
            self.close_all_positions(instrument_id)
        self._submit_market_order(OrderSide.BUY)

    def _go_short(self) -> None:
        instrument_id = self.config.instrument_id
        if self.portfolio.is_net_short(instrument_id):
            return
        if self.portfolio.is_net_long(instrument_id):
            self.close_all_positions(instrument_id)
        self._submit_market_order(OrderSide.SELL)

    def _submit_market_order(self, side: OrderSide) -> None:
        assert self.instrument is not None  # guaranteed once on_start has run
        order: MarketOrder = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=self.instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)

    def on_stop(self) -> None:
        """Flatten and clean up when the strategy stops."""
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        """Reset indicators so the strategy can be re-run."""
        self.fast_ema.reset()
        self.slow_ema.reset()
