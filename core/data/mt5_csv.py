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

import shutil
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


# The broker's server timezone, VERIFIED (#18) rather than assumed, two independent ways:
#   1. In the exported CSVs the FX week runs Monday 00:00 to Friday 20:00 and the week-start hour
#      does NOT shift across the DST changeover -- the signature of server-local time.
#   2. Against the live terminal: the last tick before the weekend is Friday 23:56:59 server time,
#      while the market closes 17:00 New York = 21:00 UTC. So 24:00 server = 21:00 UTC -> UTC+3 in
#      July, i.e. EEST. With (1)'s DST behaviour that is EET/EEST = Europe/Athens.
MT5_SERVER_TZ = "Europe/Athens"


_FRAME_MARKER = ".timestamp_frame"


def _stamp_catalog_frame(catalog_path: str | Path, server_tz: str | None) -> None:
    """Record which timestamp frame a catalog was written in."""
    (Path(catalog_path) / _FRAME_MARKER).write_text(server_tz or "UTC", encoding="utf-8")


def catalog_frame_is_stale(catalog_path: str | Path, server_tz: str | None = MT5_SERVER_TZ) -> bool:
    """True if the catalog was written in a DIFFERENT timestamp frame than we now parse in.

    Seeding is skipped whenever an instrument is already in the catalog, so without this a
    pre-existing catalog written under the old server-as-UTC assumption would be silently mixed
    with window and day logic parsed in the new frame -- shifting everything by the server offset
    until someone thought to delete ``catalog/`` by hand. An unmarked catalog predates the marker,
    so it is stale by definition.
    """
    marker = Path(catalog_path) / _FRAME_MARKER
    if not marker.exists():
        return Path(catalog_path).exists()  # unmarked but populated -> written before the marker
    return marker.read_text(encoding="utf-8").strip() != (server_tz or "UTC")


def seeded_instruments(catalog_path: str | Path) -> set[str]:
    """Instrument ids present in the catalog -- AFTER discarding a stale-frame catalog.

    This is the gate every seeding decision must pass. Checking staleness only inside the write
    funnel missed the skip path: in the stale case the instrument IS present, so the caller skips
    the write and the funnel never runs. Here the stale catalog is deleted at the presence check
    itself, the instrument set comes back empty, and the caller re-seeds through the write funnel
    (which stamps the new frame).
    """
    path = Path(catalog_path)
    if catalog_frame_is_stale(path):
        print(f"catalog {path} is in a different timestamp frame -> discarding it")
        shutil.rmtree(path, ignore_errors=True)
        return set()
    if not path.exists():
        return set()
    return {str(i.id) for i in ParquetDataCatalog(str(path)).instruments()}


def require_current_frame(catalog_path: str | Path) -> None:
    """Fail closed if the catalog was written in a different timestamp frame.

    For READ paths that never seed (the portfolio stage backtests straight off the catalog): they
    cannot rebuild it themselves without silently redoing hours of study work, so they refuse with
    instructions instead of mixing old-frame bars into new-frame calendar logic.
    """
    if catalog_frame_is_stale(catalog_path):
        raise RuntimeError(
            f"catalog {catalog_path} was written in a different timestamp frame than the code "
            "now parses. Re-seed it (re-run the study, or delete the directory and seed) before "
            "running backtests -- mixing frames shifts every window and day bucket."
        )


def parse_mt5_timestamps(
    df: pd.DataFrame, *, server_tz: str | None = MT5_SERVER_TZ, offset_hours: int = 0
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

    The default IS the verified conversion (``MT5_SERVER_TZ``); the loaders and the catalog writer
    all share it, so importing and calendar logic cannot end up in different frames. Pass
    ``server_tz=None`` only to reproduce a pre-fix result for comparison -- that reads the stamps
    as UTC, which is what every number produced before this change assumed.
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
    server_tz: str | None = MT5_SERVER_TZ,
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
    server_tz: str | None = MT5_SERVER_TZ,
) -> int:
    """Import an MT5 CSV and write the instrument + bid & ask bars into the catalog.

    ``server_tz`` MUST match what the calendar-side loaders use (``_data_span``, the daily
    close/low-high curves). Seeding the catalog in one frame while the window and day logic runs
    in another is worse than not converting at all: trade timestamps and day buckets then drift
    against each other around the server-midnight boundary.

    Returns the number of bars per side (bid and ask have the same count).
    """
    # Staleness is checked HERE, in the one funnel every bar import passes through, rather than at
    # each caller: putting it in the callers meant the walk-forward CLI missed it and kept mixing
    # old-frame bars with new-frame window boundaries. Wipe once, then the fresh marker makes
    # subsequent instruments in the same run non-stale.
    if catalog_frame_is_stale(catalog_path, server_tz):
        print(f"catalog {catalog_path} is in a different timestamp frame -> rebuilding")
        shutil.rmtree(catalog_path, ignore_errors=True)
    Path(catalog_path).mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(str(catalog_path))
    _stamp_catalog_frame(catalog_path, server_tz)

    bid_bars, ask_bars = load_mt5_bid_ask_bars(
        csv_path,
        instrument,
        bar_spec=bar_spec,
        slippage_points=slippage_points,
        server_tz_offset_hours=server_tz_offset_hours,
        server_tz=server_tz,
    )
    catalog.write_data([instrument])
    catalog.write_data(bid_bars)
    catalog.write_data(ask_bars)
    return len(bid_bars)
