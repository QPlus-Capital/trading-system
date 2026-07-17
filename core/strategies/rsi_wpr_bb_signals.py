"""Pure signal engine for RsiWprBb — the single source of truth shared by backtest and live.

Everything except order placement lives here: the NautilusTrader `RsiWprBb` strategy AND the
MT5 live runner both drive this engine, so live signals are byte-identical to the backtest.
It reuses NautilusTrader's EMA/RSI indicator classes (standalone — no trading node needed) so
the maths match exactly; Williams %R and Bollinger are computed here on the close price.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from nautilus_trader.indicators.averages import ExponentialMovingAverage, MovingAverageType
from nautilus_trader.indicators.momentum import RelativeStrengthIndex


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
    """Return (upper, middle, lower) Bollinger Bands over ``closes`` (close-based, pop. stdev)."""
    n = len(closes)
    mean = math.fsum(closes) / n
    variance = math.fsum((c - mean) ** 2 for c in closes) / n
    std = math.sqrt(variance)
    return mean + mult * std, mean, mean - mult * std


@dataclass(frozen=True)
class SignalParams:
    """Signal-relevant subset of RsiWprBbConfig (the knobs the engine reads)."""

    wpr_length: int = 14
    ema_length: int = 10
    rsi_length: int = 14
    bb_length: int = 20
    bb_mult: float = 2.0
    min_candle_size_pct: float = 0.12
    pending_lookback: int = 4
    rsi_overbought_level: float = 70.0
    rsi_min_bars_above: int = 3
    buy_lookback_below_bb: int = 4
    buy_wpr_lookback: int = 7
    buy_wpr_threshold: float = -80.0
    buy_rsi_threshold: float = 40.0
    use_bb_confirm: bool = True
    use_wpr_confirm: bool = True
    use_rsi_filter: bool = True

    @classmethod
    def from_config(cls, config: Any) -> SignalParams:
        """Build from any object exposing the same attribute names (e.g. RsiWprBbConfig)."""
        return cls(**{f.name: getattr(config, f.name) for f in fields(cls)})


class RsiWprBbSignals:
    """Stateful 4H signal engine: feed bars one at a time, get (buy, sell) each bar."""

    def __init__(self, params: SignalParams) -> None:
        self.p = params
        self._ema = ExponentialMovingAverage(params.ema_length)
        self._rsi = RelativeStrengthIndex(params.rsi_length, ma_type=MovingAverageType.WILDER)

        self._warmup = (
            max(
                params.buy_lookback_below_bb + params.bb_length,
                params.buy_wpr_lookback + params.wpr_length,
                params.pending_lookback + 2,
                params.ema_length + 2,
                params.rsi_length + 2,
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

        self._prev_buy_raw = False
        self._prev_sell_base_raw = False
        self._pending_high = 0.0
        self._pending_low = 0.0
        self._pending_bars_left = 0
        self._pending_low_breached = False

    def reset(self) -> None:
        """Reset to the pre-warmup state (indicators, history, flags, pending)."""
        self.__init__(self.p)  # type: ignore[misc]

    @property
    def warmed_up(self) -> bool:
        """True once enough history and both indicators are initialized."""
        return len(self._close) >= self._warmup and self._ema.initialized and self._rsi.initialized

    def update(self, o: float, h: float, low_: float, c: float) -> tuple[bool, bool]:
        """Feed one closed bar (OHLC); return (buy_signal, sell_signal)."""
        self._open.append(o)
        self._high.append(h)
        self._low.append(low_)
        self._close.append(c)
        self._ema.update_raw(c)
        self._rsi.update_raw(c)
        self._ema_hist.append(self._ema.value)
        self._rsi_hist.append(self._rsi.value)
        self._wpr.append(self._wpr_at(0) if len(self._close) >= self.p.wpr_length else 0.0)
        if not self.warmed_up:
            return (False, False)
        return (self._eval_buy(o, h, low_, c), self._eval_sell(o, h, low_, c))

    # -- helpers over the rolling history (index 0 = current bar, i = i bars ago) --

    def _wpr_at(self, i: int) -> float:
        n = self.p.wpr_length
        highs = [self._high[-1 - (i + j)] for j in range(n)]
        lows = [self._low[-1 - (i + j)] for j in range(n)]
        return williams_r(highs, lows, self._close[-1 - i])

    def _bb_at(self, i: int) -> tuple[float, float, float]:
        n = self.p.bb_length
        closes = [self._close[-1 - (i + j)] for j in range(n)]
        return bollinger(closes, self.p.bb_mult)

    def _eval_buy(self, o: float, h: float, low_: float, c: float) -> bool:
        p = self.p
        _, _, bb_lower = self._bb_at(0)
        was_below_lower_bb = any(
            self._low[-1 - k] < self._bb_at(k)[2] for k in range(1, p.buy_lookback_below_bb + 1)
        )
        wpr_was_oversold = any(
            self._wpr[-1 - k] < p.buy_wpr_threshold for k in range(p.buy_wpr_lookback)
        )
        buy_raw = (
            c > o
            and low_ <= bb_lower
            and h >= bb_lower
            and (not p.use_bb_confirm or was_below_lower_bb)
            and (not p.use_wpr_confirm or wpr_was_oversold)
            and (not p.use_rsi_filter or self._rsi_hist[-1] < p.buy_rsi_threshold)
        )
        signal = buy_raw and not self._prev_buy_raw
        self._prev_buy_raw = buy_raw
        return signal

    def _eval_sell(self, o: float, h: float, low_: float, c: float) -> bool:
        p = self.p
        wpr0, wpr1 = self._wpr[-1], self._wpr[-2]
        ema0, ema1 = self._ema_hist[-1], self._ema_hist[-2]
        ema_falling, ema_rising = ema0 < ema1, ema0 > ema1
        candle_pct = abs(c - o) / o * 100.0 if o != 0 else 0.0

        base_raw = (
            c < o
            and wpr0 < wpr1
            and wpr0 < -20
            and wpr1 > -20
            and candle_pct >= p.min_candle_size_pct
        )
        base_signal = base_raw and not self._prev_sell_base_raw
        self._prev_sell_base_raw = base_raw

        rsi_above = sum(
            1
            for k in range(1, p.pending_lookback + 1)
            if self._rsi_hist[-1 - k] > p.rsi_overbought_level
        )
        rsi_condition = rsi_above >= p.rsi_min_bars_above

        fall_a = base_signal and ema_falling
        fall_b = base_signal and ema_rising and (not p.use_rsi_filter or rsi_condition)
        pending_trigger = base_signal and ema_rising and not fall_b

        from_pending = False
        if pending_trigger:
            self._pending_high = h
            self._pending_low = low_
            self._pending_bars_left = p.pending_lookback
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
