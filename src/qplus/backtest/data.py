"""Deterministic synthetic market data for backtests.

Until real IBKR data is wired in, the backtest skeleton runs on a reproducible
synthetic price series: a sine wave around a baseline price. The wave guarantees
the fast and slow EMAs cross repeatedly, so the strategy actually trades, and the
series is fully deterministic (no randomness) so backtests are reproducible.

Prices are built as :class:`~decimal.Decimal` values and rounded to the
instrument's precision via ``make_price``; the sine term is only a shape function.
"""

import math
from decimal import Decimal

import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity

from qplus.backtest.config import BacktestConfig

_TWO_PI = 2 * math.pi


def make_synthetic_bars(
    instrument: Instrument,
    bar_type: BarType,
    config: BacktestConfig,
) -> list[Bar]:
    """Generate a deterministic sine-wave bar series for ``instrument``.

    Parameters
    ----------
    instrument : Instrument
        The instrument the bars belong to (used for price/quantity rounding).
    bar_type : BarType
        The bar type of the generated bars. Its time step drives the timestamps.
    config : BacktestConfig
        The backtest configuration providing the synthetic-series parameters.

    Returns
    -------
    list[Bar]
        ``config.bar_count`` bars with monotonically increasing timestamps.
    """
    step_nanos = int(bar_type.spec.timedelta.value)
    start_nanos = dt_to_unix_nanos(pd.Timestamp(config.start_time, tz="UTC"))

    half_range = config.bar_half_range
    volume = Quantity.from_int(1_000)

    mids = [_mid_price(config, i) for i in range(config.bar_count)]

    bars: list[Bar] = []
    for i in range(config.bar_count):
        close = mids[i]
        open_ = mids[i - 1] if i > 0 else mids[0]
        high = max(open_, close) + half_range
        low = min(open_, close) - half_range
        ts = start_nanos + i * step_nanos
        bars.append(
            Bar(
                bar_type,
                instrument.make_price(open_),
                instrument.make_price(high),
                instrument.make_price(low),
                instrument.make_price(close),
                volume,
                ts,
                ts,
            ),
        )
    return bars


def _mid_price(config: BacktestConfig, index: int) -> Decimal:
    """Return the baseline sine mid price for the bar at ``index`` as a Decimal."""
    phase = _TWO_PI * index / config.wave_period_bars
    offset = config.wave_amplitude * Decimal(str(math.sin(phase)))
    return config.start_price + offset
