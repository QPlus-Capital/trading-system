"""Portfolio-stage support: build daily realized-balance and mark-to-market equity curves.

Given a combined, timestamped OOS trade stream for one account (all selected markets) at a
base risk (1 unit = the extraction's ``risk_per_trade``), this reconstructs the two daily
series the prop-firm rule needs:

* **realized** excess over the starting balance (closed trades only) -> feeds the balance
  high-water-mark floor;
* **unrealized** excess (open positions marked to the daily price) -> equity = realized +
  unrealized -> feeds the equity breach test.

Unrealized PnL is exact and linear in price for a fixed-size position:
``pnl * (price_today - entry) / (exit - entry)``. Day numbers are computed unit-safely
(MT5 CSVs parse to ``datetime64[us]``, so ``.astype(int64)//DAY_NS`` would be wrong).

These are pure functions (NumPy/pandas); pass the resulting curves to
:mod:`research.portfolio.drawdown`.
"""

from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from core.data.mt5_csv import parse_mt5_timestamps

DAY_NS = 86_400_000_000_000
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
_EPOCH_DATE = date(1970, 1, 1)
# The prop firm's loss day resets at 16:15 America/Chicago (DST-aware) -- the same constants the
# live runner uses. Kept here so research and live cannot drift apart on the day boundary.
_CHICAGO = ZoneInfo("America/Chicago")
_DAILY_RESET = time(16, 15)


def to_day(ts_ns: int) -> int:
    """Prop-firm LOSS-day number (days since epoch) from a nanosecond UTC timestamp.

    Not the UTC calendar day: the account's day resets at 16:15 America/Chicago, mirroring
    ``live.runner.loss_day`` exactly. Bucketing the daily-limit check by UTC midnight instead
    measured an adverse evening move against the wrong day's baseline, so a configuration that
    would breach TTP's 3% rule could pass the simulated gate.

    Everything on this day axis -- trade open/close days AND the daily price series -- must use
    this one function, or trades and prices index different days.
    """
    local = pd.Timestamp(int(ts_ns), unit="ns", tz="UTC").tz_convert(_CHICAGO)
    day = local.date() + (timedelta(days=1) if local.time() >= _DAILY_RESET else timedelta(0))
    return int((day - _EPOCH_DATE).days)


def to_calendar_day(ts_ns: int) -> int:
    """Plain UTC calendar-day number -- for display axes, never for the daily-limit maths."""
    return int(ts_ns) // DAY_NS


def _loss_day_numbers(ts: pd.Series) -> np.ndarray:
    """Vectorised :func:`to_day` for a tz-aware series -- the price series must share the axis."""
    local = ts.dt.tz_convert(_CHICAGO)
    rolls = local.dt.time >= _DAILY_RESET
    days = local.dt.normalize().dt.tz_localize(None) + pd.to_timedelta(rolls.astype(int), unit="D")
    nums: np.ndarray = ((days - pd.Timestamp("1970-01-01")) // pd.Timedelta(days=1)).to_numpy()
    return nums


def load_daily_close(csv_path: str) -> pd.Series:
    """Last close per calendar day from an MT5 H4 CSV, indexed by day number.

    Uses unit-safe day math (``(ts - epoch) // 1 day``) rather than
    ``ts.astype(int64) // DAY_NS``, which is wrong when pandas parses to microseconds.
    """
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>", "<CLOSE>"])
    ts = parse_mt5_timestamps(df)  # #18: server wall time -> real UTC
    day = _loss_day_numbers(ts)  # same axis as the trades (16:15 CT reset), not UTC midnight
    return pd.Series(df["<CLOSE>"].to_numpy(dtype=float), index=day).groupby(level=0).last()


def load_daily_low_high(csv_path: str) -> tuple[pd.Series, pd.Series]:
    """Per-day (low, high) from an MT5 H4 CSV, indexed by day number.

    The daily extremes are the closest thing to an intraday path the H4 data gives us, and they
    are what the prop firm's *intraday* equity rule actually reacts to (#15): a day can dip 3%
    and close at -0.5%, which an end-of-day series cannot see.
    """
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>", "<LOW>", "<HIGH>"])
    ts = parse_mt5_timestamps(df)  # #18: server wall time -> real UTC
    day = _loss_day_numbers(ts)  # same axis as the trades (16:15 CT reset), not UTC midnight
    low = pd.Series(df["<LOW>"].to_numpy(dtype=float), index=day).groupby(level=0).min()
    high = pd.Series(df["<HIGH>"].to_numpy(dtype=float), index=day).groupby(level=0).max()
    return low, high


def align_prices(daily_close: pd.Series, d0: int, d1: int) -> np.ndarray:
    """Reindex a per-day close series onto the contiguous ``[d0, d1]`` range (ffill/bfill)."""
    aligned = daily_close.reindex(range(d0, d1 + 1)).ffill().bfill().to_numpy()
    return np.asarray(aligned, dtype=float)


def base_curves(
    trades: pd.DataFrame, prices: dict[str, np.ndarray], d0: int, d1: int
) -> tuple[np.ndarray, np.ndarray]:
    """Daily (realized_excess, unrealized) at risk multiple 1.0, over ``[d0, d1]``.

    ``trades`` needs columns ``market, od, cd, pnl_base, entry, exit`` where ``od``/``cd``
    are open/close day numbers. ``prices[market]`` is that market's daily close aligned to
    ``[d0, d1]`` (see :func:`align_prices`). ``equity_excess = realized_excess +
    unrealized``. An optional ``swap_base`` column is booked as a REALIZED cost at close --
    never marked to market (marking a fixed swap via the price fraction blows up the floating
    on tiny-span trades, so the mark-to-market drawdown stays on the gross price PnL).
    """
    n = d1 - d0 + 1
    od = trades["od"].to_numpy()
    cd = trades["cd"].to_numpy()
    pnl = trades["pnl_base"].to_numpy(dtype=float)
    swap = (
        trades["swap_base"].to_numpy(dtype=float)
        if "swap_base" in trades.columns
        else np.zeros(len(trades))
    )
    entry = trades["entry"].to_numpy(dtype=float)
    exit_ = trades["exit"].to_numpy(dtype=float)
    mk = trades["market"].to_numpy()
    span = np.where(np.abs(exit_ - entry) < 1e-12, 1.0, exit_ - entry)

    realized_step = np.zeros(n)
    np.add.at(realized_step, np.clip(cd - d0, 0, n - 1), pnl + swap)  # swap realized at close
    realized = np.cumsum(realized_step)

    unrealized = np.zeros(n)
    for i in range(len(trades)):
        lo, hi = od[i] - d0, cd[i] - d0  # open on [lo, hi)
        if hi <= lo:
            continue
        unrealized[lo:hi] += pnl[i] / span[i] * (prices[mk[i]][lo:hi] - entry[i])
    return realized, unrealized


