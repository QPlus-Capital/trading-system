"""Stage 3/4 support: build daily realized-balance and mark-to-market equity curves.

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
:mod:`qplus.backtest.portfolio.drawdown`. See ``docs/backtesting-framework.md`` (Stage 3).
"""

import numpy as np
import pandas as pd

DAY_NS = 86_400_000_000_000
_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def to_day(ts_ns: int) -> int:
    """Calendar-day number (days since epoch) from a nanosecond UTC timestamp."""
    return int(ts_ns) // DAY_NS


def load_daily_close(csv_path: str) -> pd.Series:
    """Last close per calendar day from an MT5 H4 CSV, indexed by day number.

    Uses unit-safe day math (``(ts - epoch) // 1 day``) rather than
    ``ts.astype(int64) // DAY_NS``, which is wrong when pandas parses to microseconds.
    """
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>", "<CLOSE>"])
    ts = pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S", utc=True)
    day = ((ts - _EPOCH) // pd.Timedelta(days=1)).to_numpy()
    return pd.Series(df["<CLOSE>"].to_numpy(dtype=float), index=day).groupby(level=0).last()


def load_daily_extremes(csv_path: str) -> tuple[pd.Series, pd.Series]:
    """Per-day (high, low) from an MT5 H4 CSV, indexed by day number (for intraday DD, H1).

    The daily high/low bound the intraday equity swing of open positions, so the drawdown
    breach test can use each day's *adverse* extreme instead of only the close (which can miss
    an intraday breach that recovers by end of day).
    """
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>", "<HIGH>", "<LOW>"])
    ts = pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S", utc=True)
    day = ((ts - _EPOCH) // pd.Timedelta(days=1)).to_numpy()
    high = pd.Series(df["<HIGH>"].to_numpy(dtype=float), index=day).groupby(level=0).max()
    low = pd.Series(df["<LOW>"].to_numpy(dtype=float), index=day).groupby(level=0).min()
    return high, low


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
    unrealized``.
    """
    n = d1 - d0 + 1
    od = trades["od"].to_numpy()
    cd = trades["cd"].to_numpy()
    pnl = trades["pnl_base"].to_numpy(dtype=float)
    entry = trades["entry"].to_numpy(dtype=float)
    exit_ = trades["exit"].to_numpy(dtype=float)
    mk = trades["market"].to_numpy()
    span = np.where(np.abs(exit_ - entry) < 1e-12, 1.0, exit_ - entry)

    realized_step = np.zeros(n)
    np.add.at(realized_step, np.clip(cd - d0, 0, n - 1), pnl)
    realized = np.cumsum(realized_step)

    unrealized = np.zeros(n)
    for i in range(len(trades)):
        lo, hi = od[i] - d0, cd[i] - d0  # open on [lo, hi)
        if hi <= lo:
            continue
        unrealized[lo:hi] += pnl[i] / span[i] * (prices[mk[i]][lo:hi] - entry[i])
    return realized, unrealized


def worst_unrealized(
    trades: pd.DataFrame,
    highs: dict[str, np.ndarray],
    lows: dict[str, np.ndarray],
    d0: int,
    d1: int,
) -> np.ndarray:
    """Daily *worst-case* unrealized (risk multiple 1.0): open positions at their adverse extreme.

    Marks each open position at the day's adverse price -- the low for a long, the high for a
    short -- so ``realized + worst_unrealized`` is the intraday-worst equity for the breach test
    (H1). Direction comes from the sign of ``pnl/span``: positive for longs (they profit as
    price rises), negative for shorts. Needs each market's aligned daily high/low arrays.
    """
    n = d1 - d0 + 1
    od = trades["od"].to_numpy()
    cd = trades["cd"].to_numpy()
    pnl = trades["pnl_base"].to_numpy(dtype=float)
    entry = trades["entry"].to_numpy(dtype=float)
    exit_ = trades["exit"].to_numpy(dtype=float)
    mk = trades["market"].to_numpy()
    span = np.where(np.abs(exit_ - entry) < 1e-12, 1.0, exit_ - entry)

    worst = np.zeros(n)
    for i in range(len(trades)):
        lo, hi = od[i] - d0, cd[i] - d0  # open on [lo, hi)
        if hi <= lo:
            continue
        k = pnl[i] / span[i]  # >0 long, <0 short
        adverse = lows[mk[i]] if k > 0 else highs[mk[i]]  # long worst at low, short worst at high
        worst[lo:hi] += k * (adverse[lo:hi] - entry[i])
    return worst
