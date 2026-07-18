"""Import MetaTrader 5 "Export Bars" CSV files into the Parquet catalog.

MT5's bar export is tab-separated with this header::

    <DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>

The OHLC are **bid** prices (MT5 charts "by bid price") and ``<SPREAD>`` is the
spread in points. We therefore write TWO bar series into the catalog per instrument:

- a **BID** series (the raw OHLC), used by the strategy for its signals, and
- an **ASK** series (bid + spread), so the simulated exchange fills buys at the ask
  and sells at the bid -- capturing the real, per-bar spread cost.

An optional ``slippage_points`` widens the effective quote symmetrically around the
mid to model execution slippage on top of the raw spread.

Prices are parsed as strings into ``Decimal`` and rounded via ``make_price`` -- no
float is used for prices.
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

# A bar's volume gates how much a PASSIVE order (limit / market-if-touched) may fill against it in
# the backtest -- aggressive orders (market, stop-market) ignore it. MT5's <TICKVOL> is a count of
# price ticks, not tradeable size: it is typically a few hundred, while our CFD positions run into
# millions of units. Feeding it in silently capped every take-profit at a sliver of the position,
# so the stop later closed the remainder and one trade exited on both legs.
#
# For a CFD at a prop broker, liquidity at our size is effectively unbounded, so the honest model is
# a bar volume that never binds. (Slippage and spread -- which DO cost us -- are modelled separately
# by the broker profile.) Re-seed the catalog after changing this.
_BAR_VOLUME = 1_000_000_000


def _bar_types(instrument: Instrument, bar_spec: str) -> tuple[BarType, BarType]:
    """Return the (bid, ask) bar types for ``instrument`` and a spec like ``4-HOUR``."""
    bid = BarType.from_str(f"{instrument.id}-{bar_spec}-BID-EXTERNAL")
    ask = BarType.from_str(f"{instrument.id}-{bar_spec}-ASK-EXTERNAL")
    return bid, ask


def parse_mt5_timestamps(
    df: pd.DataFrame, *, server_tz: str | None = None, offset_hours: int = 0
) -> pd.Series:
    """Bar open times from an MT5 export, as real UTC.

    **The exported timestamps are the BROKER SERVER's wall clock, not UTC** (#18). Verified from
    the data itself: the FX week starts Monday 00:00 and ends Friday 20:00 in these files, and the
    week-start hour does NOT shift across the DST changeover. In real UTC an EET server's week
    would begin Sunday 21:00 in summer and 22:00 in winter -- the absence of that one-hour shift is
    the signature of server-local time.

    ``server_tz`` is an IANA name (e.g. ``"Europe/Athens"`` for a standard EET/EEST server) and is
    the correct way to convert, because the server's own offset changes with DST -- which a fixed
    ``offset_hours`` cannot express. ``offset_hours`` is kept only for the legacy fixed-shift path.

    Both default to "no conversion", which reproduces the historical behaviour EXACTLY: every
    number produced so far assumed these stamps were UTC, so flipping the default would silently
    re-date the whole research history. Set it deliberately, and re-run, once the server zone has
    been confirmed against the terminal.
    """
    naive = pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S")
    if server_tz:
        local = naive.dt.tz_localize(server_tz, ambiguous=True, nonexistent="shift_forward")
        return local.dt.tz_convert("UTC")
    return naive.dt.tz_localize("UTC") - pd.Timedelta(hours=offset_hours)


def load_mt5_bid_ask_bars(
    csv_path: str | Path,
    instrument: Instrument,
    *,
    bar_spec: str = "4-HOUR",
    slippage_points: float = 0.0,
    server_tz_offset_hours: int = 0,
    server_tz: str | None = None,
) -> tuple[list[Bar], list[Bar]]:
    """Parse an MT5 bar-export CSV into (bid_bars, ask_bars).

    The ask is reconstructed as ``bid + spread`` (per bar), and ``slippage_points``
    widens both sides around the mid. Rows with a non-positive recorded spread fall
    back to the median positive spread in the file.
    """
    bid_bar_type, ask_bar_type = _bar_types(instrument, bar_spec)
    tick = Decimal(str(instrument.price_increment))

    df = pd.read_csv(
        csv_path,
        sep="\t",
        dtype={"<OPEN>": str, "<HIGH>": str, "<LOW>": str, "<CLOSE>": str},
    )
    timestamps = parse_mt5_timestamps(df, server_tz=server_tz, offset_hours=server_tz_offset_hours)

    spreads = df["<SPREAD>"].astype(int).tolist()
    positive = [s for s in spreads if s > 0]
    fallback = int(pd.Series(positive).median()) if positive else 0

    half_slip = Decimal(str(slippage_points)) * tick / 2

    opens, highs = df["<OPEN>"].tolist(), df["<HIGH>"].tolist()
    lows, closes = df["<LOW>"].tolist(), df["<CLOSE>"].tolist()
    bar_volume = instrument.make_qty(_BAR_VOLUME)

    bid_bars: list[Bar] = []
    ask_bars: list[Bar] = []
    for i, ts in enumerate(timestamps):
        ns = dt_to_unix_nanos(ts)
        spread_pts = spreads[i] if spreads[i] > 0 else fallback
        up = Decimal(spread_pts) * tick + half_slip  # bid -> ask shift
        volume = bar_volume
        o, h, low_, c = Decimal(opens[i]), Decimal(highs[i]), Decimal(lows[i]), Decimal(closes[i])

        bid_bars.append(
            Bar(
                bid_bar_type,
                instrument.make_price(o - half_slip),
                instrument.make_price(h - half_slip),
                instrument.make_price(low_ - half_slip),
                instrument.make_price(c - half_slip),
                volume,
                ns,
                ns,
            ),
        )
        ask_bars.append(
            Bar(
                ask_bar_type,
                instrument.make_price(o + up),
                instrument.make_price(h + up),
                instrument.make_price(low_ + up),
                instrument.make_price(c + up),
                volume,
                ns,
                ns,
            ),
        )
    return bid_bars, ask_bars


def write_mt5_catalog(
    csv_path: str | Path,
    catalog_path: str | Path,
    *,
    instrument: Instrument,
    bar_spec: str = "4-HOUR",
    slippage_points: float = 0.0,
    server_tz_offset_hours: int = 0,
) -> int:
    """Import an MT5 CSV and write the instrument + bid & ask bars into the catalog.

    Returns the number of bars per side (bid and ask have the same count).
    """
    Path(catalog_path).mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(str(catalog_path))

    bid_bars, ask_bars = load_mt5_bid_ask_bars(
        csv_path,
        instrument,
        bar_spec=bar_spec,
        slippage_points=slippage_points,
        server_tz_offset_hours=server_tz_offset_hours,
    )
    catalog.write_data([instrument])
    catalog.write_data(bid_bars)
    catalog.write_data(ask_bars)
    return len(bid_bars)
