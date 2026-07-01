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

import math
from collections import deque
from collections.abc import Sequence
from decimal import Decimal

from nautilus_trader.config import PositiveInt, StrategyConfig
from nautilus_trader.indicators.averages import ExponentialMovingAverage, MovingAverageType
from nautilus_trader.indicators.momentum import RelativeStrengthIndex
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, OrderType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


def williams_r(highs: Sequence[float], lows: Sequence[float], close: float) -> float:
    """Return Williams %R (range -100..0) over the given high/low window.

    ``%R = 100 * (close - highest_high) / (highest_high - lowest_low)``.
    Returns 0.0 if the window has no range (to avoid division by zero).
    """
    highest = max(highs)
    lowest = min(lows)
    span = highest - lowest
    if span == 0:
        return 0.0
    return 100.0 * (close - highest) / span


def bollinger(closes: Sequence[float], mult: float) -> tuple[float, float, float]:
    """Return (upper, middle, lower) Bollinger Bands over ``closes``.

    Uses a simple moving average and the population standard deviation (matching
    TradingView's ``ta.stdev`` default), computed on the close price.
    """
    n = len(closes)
    mean = math.fsum(closes) / n
    variance = math.fsum((c - mean) ** 2 for c in closes) / n
    std = math.sqrt(variance)
    return mean + mult * std, mean, mean - mult * std


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

    # Risk management (0 disables). stop_loss_pct / take_profit_pct are percent of
    # the entry price; when both are > 0 a bracket (market entry + stop-loss +
    # take-profit) is used. risk_per_trade_pct sizes the position so a stop-out
    # loses that percent of account equity; 0 falls back to the fixed trade_size.
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    risk_per_trade_pct: float = 0.0


class RsiWprBb(Strategy):  # type: ignore[misc]
    """Long/short reversal strategy driven by the ported 4H signals."""

    def __init__(self, config: RsiWprBbConfig) -> None:
        super().__init__(config)
        self.instrument: Instrument | None = None

        self._ema = ExponentialMovingAverage(config.ema_length)
        self._rsi = RelativeStrengthIndex(config.rsi_length, ma_type=MovingAverageType.WILDER)

        # How many bars of history we need before any signal can be evaluated.
        self._warmup = (
            max(
                config.buy_lookback_below_bb + config.bb_length,
                config.buy_wpr_lookback + config.wpr_length,
                config.pending_lookback + 2,
                config.ema_length + 2,
                config.rsi_length + 2,
            )
            + 2
        )
        maxlen = self._warmup + 2
        self._open: deque[float] = deque(maxlen=maxlen)
        self._high: deque[float] = deque(maxlen=maxlen)
        self._low: deque[float] = deque(maxlen=maxlen)
        self._close: deque[float] = deque(maxlen=maxlen)
        self._wpr: deque[float] = deque(maxlen=maxlen)
        self._ema_hist: deque[float] = deque(maxlen=maxlen)
        self._rsi_hist: deque[float] = deque(maxlen=maxlen)

        # Rising-edge detection ("raw and not raw[1]" in Pine).
        self._prev_buy_raw = False
        self._prev_sell_base_raw = False

        # Deferred "Fall C" sell state machine.
        self._pending_high = 0.0
        self._pending_low = 0.0
        self._pending_bars_left = 0
        self._pending_low_breached = False

    def on_start(self) -> None:
        """Resolve the instrument and subscribe to bars."""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument {self.config.instrument_id}")
            self.stop()
            return
        self.subscribe_bars(self.config.bar_type)

    # -- helpers over the rolling history (index 0 = current bar, i = i bars ago) --

    def _wpr_at(self, i: int) -> float:
        n = self.config.wpr_length
        highs = [self._high[-1 - (i + j)] for j in range(n)]
        lows = [self._low[-1 - (i + j)] for j in range(n)]
        return williams_r(highs, lows, self._close[-1 - i])

    def _bb_at(self, i: int) -> tuple[float, float, float]:
        n = self.config.bb_length
        closes = [self._close[-1 - (i + j)] for j in range(n)]
        return bollinger(closes, self.config.bb_mult)

    def on_bar(self, bar: Bar) -> None:
        """Update indicators, evaluate the 4H signals and trade the reversal."""
        o, h, low_, c = (
            bar.open.as_double(),
            bar.high.as_double(),
            bar.low.as_double(),
            bar.close.as_double(),
        )
        self._open.append(o)
        self._high.append(h)
        self._low.append(low_)
        self._close.append(c)

        self._ema.update_raw(c)
        self._rsi.update_raw(c)
        self._ema_hist.append(self._ema.value)
        self._rsi_hist.append(self._rsi.value)
        self._wpr.append(
            self._wpr_at(0) if len(self._close) >= self.config.wpr_length else 0.0,
        )

        # Wait until fully warmed up so every lookback index is valid.
        if (
            len(self._close) < self._warmup
            or not self._ema.initialized
            or not self._rsi.initialized
        ):
            return

        buy_signal = self._eval_buy(o, h, low_, c)
        sell_signal = self._eval_sell(o, h, low_, c)

        if buy_signal and not sell_signal:
            self._go_long(c)
        elif sell_signal and not buy_signal:
            self._go_short(c)

    def _eval_buy(self, o: float, h: float, low_: float, c: float) -> bool:
        cfg = self.config
        _, _, bb_lower = self._bb_at(0)

        was_below_lower_bb = any(
            self._low[-1 - k] < self._bb_at(k)[2] for k in range(1, cfg.buy_lookback_below_bb + 1)
        )
        wpr_was_oversold = any(
            self._wpr[-1 - k] < cfg.buy_wpr_threshold for k in range(cfg.buy_wpr_lookback)
        )
        buy_raw = (
            c > o  # green candle
            and low_ <= bb_lower
            and h >= bb_lower
            and was_below_lower_bb
            and wpr_was_oversold
            and self._rsi_hist[-1] < cfg.buy_rsi_threshold
        )
        signal = buy_raw and not self._prev_buy_raw
        self._prev_buy_raw = buy_raw
        return signal

    def _eval_sell(self, o: float, h: float, low_: float, c: float) -> bool:
        cfg = self.config
        wpr0, wpr1 = self._wpr[-1], self._wpr[-2]
        ema0, ema1 = self._ema_hist[-1], self._ema_hist[-2]
        ema_falling, ema_rising = ema0 < ema1, ema0 > ema1
        candle_pct = abs(c - o) / o * 100.0 if o != 0 else 0.0

        base_raw = (
            c < o  # red candle
            and wpr0 < wpr1
            and wpr0 < -20
            and wpr1 > -20
            and candle_pct >= cfg.min_candle_size_pct
        )
        base_signal = base_raw and not self._prev_sell_base_raw
        self._prev_sell_base_raw = base_raw

        rsi_above = sum(
            1
            for k in range(1, cfg.pending_lookback + 1)
            if self._rsi_hist[-1 - k] > cfg.rsi_overbought_level
        )
        rsi_condition = rsi_above >= cfg.rsi_min_bars_above

        fall_a = base_signal and ema_falling
        fall_b = base_signal and ema_rising and rsi_condition
        pending_trigger = base_signal and ema_rising and not fall_b

        from_pending = False
        if pending_trigger:
            self._pending_high = h
            self._pending_low = low_
            self._pending_bars_left = cfg.pending_lookback
            self._pending_low_breached = False
        elif self._pending_bars_left > 0:
            if low_ < self._pending_low:
                self._pending_low_breached = True
            if c < o and ema_falling and c < self._pending_high and self._pending_low_breached:
                from_pending = True
                self._pending_bars_left = 0
            else:
                self._pending_bars_left -= 1

        return bool(fall_a or fall_b or from_pending)

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

        if not self._risk_managed():
            order: MarketOrder = self.order_factory.market(
                instrument_id=self.config.instrument_id,
                order_side=side,
                quantity=qty,
            )
            self.submit_order(order)
            return

        cfg = self.config
        if side == OrderSide.BUY:
            sl = ref_price * (1 - cfg.stop_loss_pct / 100.0)
            tp = ref_price * (1 + cfg.take_profit_pct / 100.0)
        else:
            sl = ref_price * (1 + cfg.stop_loss_pct / 100.0)
            tp = ref_price * (1 - cfg.take_profit_pct / 100.0)

        order_list = self.order_factory.bracket(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=qty,
            entry_order_type=OrderType.MARKET,
            sl_trigger_price=self.instrument.make_price(sl),
            tp_price=self.instrument.make_price(tp),
        )
        self.submit_order_list(order_list)

    def on_stop(self) -> None:
        """Flatten and clean up when the strategy stops."""
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        """Reset indicators so the strategy can be re-run."""
        self._ema.reset()
        self._rsi.reset()
