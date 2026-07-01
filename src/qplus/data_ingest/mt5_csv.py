"""Import MetaTrader 5 "Export Bars" CSV files into the Parquet catalog.

MT5's bar export is tab-separated with this header::

    <DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>

Dates look like ``2020.01.02`` and times like ``04:00:00``. Timestamps are in the
broker's server time; pass ``server_tz_offset_hours`` to shift them to UTC (the
strategy maths are timezone-agnostic, so 0 is fine for a first pass).

Prices are parsed as strings into ``Decimal`` and rounded via ``make_price`` -- no
float is used for prices.
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def load_mt5_bars(
    csv_path: str | Path,
    instrument: Instrument,
    bar_type: BarType,
    *,
    server_tz_offset_hours: int = 0,
) -> list[Bar]:
    """Parse an MT5 bar-export CSV into a list of NautilusTrader bars."""
    df = pd.read_csv(
        csv_path,
        sep="\t",
        dtype={"<OPEN>": str, "<HIGH>": str, "<LOW>": str, "<CLOSE>": str},
    )
    timestamps = pd.to_datetime(
        df["<DATE>"] + " " + df["<TIME>"],
        format="%Y.%m.%d %H:%M:%S",
        utc=True,
    ) - pd.Timedelta(hours=server_tz_offset_hours)

    opens = df["<OPEN>"].tolist()
    highs = df["<HIGH>"].tolist()
    lows = df["<LOW>"].tolist()
    closes = df["<CLOSE>"].tolist()
    volumes = df["<TICKVOL>"].tolist()

    bars: list[Bar] = []
    for i, ts in enumerate(timestamps):
        ns = dt_to_unix_nanos(ts)
        bars.append(
            Bar(
                bar_type,
                instrument.make_price(Decimal(opens[i])),
                instrument.make_price(Decimal(highs[i])),
                instrument.make_price(Decimal(lows[i])),
                instrument.make_price(Decimal(closes[i])),
                Quantity.from_int(int(volumes[i])),
                ns,
                ns,
            ),
        )
    return bars


def write_mt5_catalog(
    csv_path: str | Path,
    catalog_path: str | Path,
    *,
    instrument: Instrument,
    bar_type: BarType,
    server_tz_offset_hours: int = 0,
) -> int:
    """Import an MT5 CSV and write the instrument + bars into a Parquet catalog."""
    Path(catalog_path).mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(str(catalog_path))

    bars = load_mt5_bars(
        csv_path, instrument, bar_type, server_tz_offset_hours=server_tz_offset_hours
    )
    catalog.write_data([instrument])
    catalog.write_data(bars)
    return len(bars)
