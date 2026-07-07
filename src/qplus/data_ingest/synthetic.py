"""Deterministic synthetic market data for offline backtests.

Used by the tests / smoke checks: a reproducible synthetic price series (a sine wave
around a baseline price). The wave guarantees the fast and slow EMAs cross repeatedly
(so the strategy trades), and it is fully deterministic (no randomness) so backtests are
reproducible. Real backtests use the MetaTrader 5 CSV data (see ``mt5_csv``).

The data is written into a NautilusTrader ``ParquetDataCatalog`` -- the same catalog
format the real MT5 CSV data is ingested into. This keeps the "data lives in the catalog,
config points at it" separation identical for synthetic and real data.

Prices are built as :class:`~decimal.Decimal` and rounded to the instrument's
precision via ``make_price``; the sine term is only a shape function.
"""

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

_TWO_PI = 2 * math.pi


def make_synthetic_bars(
    instrument: Instrument,
    bar_type: BarType,
    *,
    bar_count: int = 300,
    start_time: str = "2020-01-01",
    start_price: Decimal = Decimal("0.70000"),
    wave_amplitude: Decimal = Decimal("0.03"),
    wave_period_bars: int = 40,
    bar_half_range: Decimal = Decimal("0.0005"),
) -> list[Bar]:
    """Generate a deterministic sine-wave bar series for ``instrument``.

    Parameters
    ----------
    instrument : Instrument
        The instrument the bars belong to (used for price/quantity rounding).
    bar_type : BarType
        The bar type of the generated bars. Its time step drives the timestamps.
    bar_count : int
        The number of bars to generate.
    start_time : str
        The UTC timestamp of the first bar (parsed by pandas).
    start_price : Decimal
        The baseline mid price of the series.
    wave_amplitude : Decimal
        The peak deviation of the sine wave from ``start_price``.
    wave_period_bars : int
        The number of bars in one full sine cycle. Drives how often EMAs cross.
    bar_half_range : Decimal
        Half the high-low range of each bar. Kept above the price increment so
        bars are never single-price.

    Returns
    -------
    list[Bar]
        ``bar_count`` bars with monotonically increasing timestamps.
    """
    if bar_count <= 0:
        raise ValueError("bar_count must be positive")
    if wave_period_bars <= 0:
        raise ValueError("wave_period_bars must be positive")

    step_nanos = int(bar_type.spec.timedelta.value)
    start_nanos = dt_to_unix_nanos(pd.Timestamp(start_time, tz="UTC"))
    volume = Quantity.from_int(1_000)

    mids = [
        start_price + wave_amplitude * Decimal(str(math.sin(_TWO_PI * i / wave_period_bars)))
        for i in range(bar_count)
    ]

    bars: list[Bar] = []
    for i in range(bar_count):
        close = mids[i]
        open_ = mids[i - 1] if i > 0 else mids[0]
        high = max(open_, close) + bar_half_range
        low = min(open_, close) - bar_half_range
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


def write_synthetic_catalog(
    catalog_path: str | Path,
    *,
    instrument: Instrument,
    bar_type: BarType,
    **bar_kwargs: object,
) -> int:
    """Write ``instrument`` and a synthetic bar series into a Parquet catalog.

    Parameters
    ----------
    catalog_path : str or Path
        The directory of the ``ParquetDataCatalog`` to write into (created if needed).
    instrument : Instrument
        The instrument to store (so the backtest node can load it).
    bar_type : BarType
        The bar type of the generated bars.
    **bar_kwargs
        Forwarded to :func:`make_synthetic_bars` (e.g. ``bar_count``, ``start_price``).

    Returns
    -------
    int
        The number of bars written.
    """
    Path(catalog_path).mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(str(catalog_path))

    bars = make_synthetic_bars(instrument, bar_type, **bar_kwargs)  # type: ignore[arg-type]
    catalog.write_data([instrument])
    catalog.write_data(bars)
    return len(bars)
