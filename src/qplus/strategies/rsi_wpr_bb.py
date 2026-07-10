"""RSI / Williams %R / Bollinger Bands crossover strategy (4H portion).

Ported from a TradingView Pine *indicator* ("Daily + 4H RSI/Williams %R Buy/Sell
Signals + Bollinger Bands"). The original only draws buy/sell markers; here those
signals drive a long/short **reversal** strategy:

- On a buy signal: go long (closing any short first).
- On a sell signal: go short (closing any long first).

Only the **4H** signal logic is implemented (the Pine script's daily signals only
fire on a daily chart; on H4 data they are inactive). A daily / multi-timeframe
extension can be layered on later.

Indicator note: EMA and RSI (Wilder-smoothed, to match TradingView's ``ta.rsi``)
come from NautilusTrader. Williams %R and the Bollinger Bands are computed here on
the close price -- NautilusTrader's Bollinger uses the typical price ``(H+L+C)/3``,
whereas the Pine script uses the close, so we replicate the close-based version to
stay faithful. Indicator maths use ``float`` (as NautilusTrader's own indicators
do); order sizing still uses ``Decimal`` / ``Quantity``.
"""

from decimal import Decimal

from nautilus_trader.config import PositiveInt, StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import PositionClosed, PositionOpened
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy

from qplus.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams


class RsiWprBbConfig(StrategyConfig, frozen=True):
    """Configuration for :class:`RsiWprBb`.

    All periods/levels mirror the Pine script inputs and are the knobs to optimize.
    """

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

    wpr_length: PositiveInt = 14
    ema_length: PositiveInt = 10
    rsi_length: PositiveInt = 14
    bb_length: PositiveInt = 20
    bb_mult: float = 2.0

    # 4H sell filter
    min_candle_size_pct: float = 0.12
    pending_lookback: PositiveInt = 4
    rsi_overbought_level: float = 70.0
    rsi_min_bars_above: PositiveInt = 3

    # 4H buy filter
    buy_lookback_below_bb: PositiveInt = 4
    buy_wpr_lookback: PositiveInt = 7
    buy_wpr_threshold: float = -80.0
    buy_rsi_threshold: float = 40.0

    # Risk management (0 disables). stop_loss_pct / take_profit_pct are percent of the ACTUAL
    # entry fill price; when both are > 0 the position gets a resting stop-loss and take-profit
    # at the venue, attached once the entry fills (see ``on_position_opened``).
    # risk_per_trade_pct sizes the position so a stop-out loses that percent of account equity;
    # 0 falls back to the fixed trade_size.
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    risk_per_trade_pct: float = 0.0

    # Component switches (for structural ablation studies). Each confirmation filter
    # can be turned off; long_only ignores short signals (flatten instead).
    use_bb_confirm: bool = True  # require "was below lower band" on buys
    use_wpr_confirm: bool = True  # require Williams %R oversold on buys
    use_rsi_filter: bool = True  # require RSI condition on buys and sells
    long_only: bool = False


def exit_prices(
    entry: float, entry_side: OrderSide, stop_loss_pct: float, take_profit_pct: float
) -> tuple[OrderSide, float, float]:
    """``(exit_side, stop_price, target_price)`` for a position filled at ``entry``.

    Both levels are anchored to the price that ACTUALLY filled, never to the signal bar's close --
    that is what guarantees a stop-out costs exactly the risk the position was sized for (1R), and
    what keeps the trigger from being "in the market" at submission.
    """
    sl, tp = stop_loss_pct / 100.0, take_profit_pct / 100.0
    if entry_side == OrderSide.BUY:  # a long position -> both exits are SELLs
        return OrderSide.SELL, entry * (1 - sl), entry * (1 + tp)
    return OrderSide.BUY, entry * (1 + sl), entry * (1 - tp)


class RsiWprBb(Strategy):  # type: ignore[misc]
    """Long/short reversal strategy driven by the ported 4H signals."""

    def __init__(self, config: RsiWprBbConfig) -> None:
        super().__init__(config)
        self.instrument: Instrument | None = None
        # The pure signal engine (shared with the live MT5 runner -> live == backtest).
        self._signals = RsiWprBbSignals(SignalParams.from_config(config))

    def on_start(self) -> None:
        """Resolve the instrument and subscribe to bars."""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument {self.config.instrument_id}")
            self.stop()
            return
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        """Feed EVERY bar to the signal engine, then trade. Exits rest at the venue (see below)."""
        # The signal engine keeps rolling indicators (RSI/EMA/BB/WPR) and MUST see every bar, or it
        # desyncs from the price series -- so update it FIRST, unconditionally (live == backtest).
        c = bar.close.as_double()
        buy_signal, sell_signal = self._signals.update(
            bar.open.as_double(), bar.high.as_double(), bar.low.as_double(), c
        )
        if buy_signal and not sell_signal:
            self._go_long(c)
        elif sell_signal and not buy_signal:
            if self.config.long_only:
                self._go_flat()
            else:
                self._go_short(c)

    def on_position_opened(self, event: PositionOpened) -> None:
        """Attach stop-loss / take-profit to the position, anchored to its ACTUAL fill price.

        These must be real resting venue orders, not a synthetic bar check. The venue fills a stop
        at the trigger when price trades through it, and only at the gapped price when a bar opens
        beyond it (locked in by ``tests/test_gap_through_stop.py``). Closing synthetically on the
        next bar's open instead turns *every* stop-out into a full-bar overshoot, so a nominal "1R"
        loss routinely cost several R -- which makes the risk-based position sizing a fiction and
        lets a parameter search pin the stop to the tightest grid value to farm the artifact.

        Anchoring to ``avg_px_open`` (not the signal bar's close) is what makes this safe: the
        trigger sits a full ``stop_loss_pct`` away from the price that actually filled, so it can
        never be "in the market" at submission -- the rejection that originally forced the
        synthetic stop.
        """
        if not self._risk_managed() or self.instrument is None:
            return
        if event.instrument_id != self.config.instrument_id:
            return
        cfg = self.config
        exit_side, sl_px, tp_px = exit_prices(
            float(event.avg_px_open), event.entry, cfg.stop_loss_pct, cfg.take_profit_pct
        )
        qty: Quantity = self.instrument.make_qty(event.quantity)
        # Stop submitted first: if one bar spans both levels, the conservative exit wins.
        stop = self.order_factory.stop_market(
            instrument_id=self.config.instrument_id,
            order_side=exit_side,
            quantity=qty,
            trigger_price=self.instrument.make_price(sl_px),
            reduce_only=True,
        )
        # The target is MARKET_IF_TOUCHED, not LIMIT: a resting limit is passive, so the backtest
        # caps its fill at the bar's VOLUME -- meaningless for CFD bars (MT5 tick counts). That let
        # the target fill a sliver while the stop took the rest, closing one position on both legs.
        # A touched-market order is a taker: it fills the whole position at the trigger.
        target = self.order_factory.market_if_touched(
            instrument_id=self.config.instrument_id,
            order_side=exit_side,
            quantity=qty,
            trigger_price=self.instrument.make_price(tp_px),
            reduce_only=True,
        )
        self.submit_order(stop, position_id=event.position_id)
        self.submit_order(target, position_id=event.position_id)

    def on_position_closed(self, event: PositionClosed) -> None:
        """Whichever exit filled, cancel the OTHER leg of *that* position.

        Scoped to the closed position on purpose. A blanket ``cancel_all_orders`` would, on a
        reversal, race the newly opened position: if its exits are attached before the old
        position's close event arrives, they would be cancelled and the new position would ride
        unprotected. Cancelling only the closed position's own legs cannot do that.
        """
        if event.instrument_id != self.config.instrument_id:
            return
        for order in self.cache.orders_open(instrument_id=self.config.instrument_id):
            if order.position_id == event.position_id:
                self.cancel_order(order)

    # -- position management (long/short reversal) --

    def _go_long(self, ref_price: float) -> None:
        instrument_id = self.config.instrument_id
        if self.portfolio.is_net_long(instrument_id):
            return
        if self.portfolio.is_net_short(instrument_id):
            self.cancel_all_orders(instrument_id)
            self.close_all_positions(instrument_id)
        self._enter(OrderSide.BUY, ref_price)

    def _go_short(self, ref_price: float) -> None:
        instrument_id = self.config.instrument_id
        if self.portfolio.is_net_short(instrument_id):
            return
        if self.portfolio.is_net_long(instrument_id):
            self.cancel_all_orders(instrument_id)
            self.close_all_positions(instrument_id)
        self._enter(OrderSide.SELL, ref_price)

    def _go_flat(self) -> None:
        """Close any open position and cancel working orders (used by long_only)."""
        instrument_id = self.config.instrument_id
        if not self.portfolio.is_flat(instrument_id):
            self.cancel_all_orders(instrument_id)
            self.close_all_positions(instrument_id)

    def _risk_managed(self) -> bool:
        return bool(self.config.stop_loss_pct > 0 and self.config.take_profit_pct > 0)

    def _account_equity(self) -> float | None:
        assert self.instrument is not None
        account = self.portfolio.account(self.instrument.id.venue)
        if account is None:
            return None
        balance = account.balance_total(USD)
        if balance is None:
            return None
        equity: float = balance.as_double()
        return equity

    def _position_qty(self, ref_price: float) -> Quantity | None:
        assert self.instrument is not None
        cfg = self.config
        if self._risk_managed() and cfg.risk_per_trade_pct > 0:
            equity = self._account_equity()
            sl_distance = ref_price * cfg.stop_loss_pct / 100.0
            if equity is not None and sl_distance > 0:
                risk_amount = equity * cfg.risk_per_trade_pct / 100.0
                risk_qty: Quantity = self.instrument.make_qty(risk_amount / sl_distance)
                return risk_qty if risk_qty.as_double() >= 1 else None
        fixed_qty: Quantity = self.instrument.make_qty(cfg.trade_size)
        return fixed_qty

    def _enter(self, side: OrderSide, ref_price: float) -> None:
        assert self.instrument is not None
        qty = self._position_qty(ref_price)
        if qty is None:
            return
        # Plain market entry; the stop-loss / take-profit are enforced synthetically in on_bar
        # (see there -- venue stop/limit orders proved unreliable under the reversal/netting flow).
        order: MarketOrder = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=qty,
        )
        self.submit_order(order)

    def on_stop(self) -> None:
        """Flatten and clean up when the strategy stops."""
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        """Reset the signal engine so the strategy can be re-run."""
        self._signals.reset()
