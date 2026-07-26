"""Position-sizing simulation: the per-trade risk function + the daily path.

Sizing only *scales* trade PnL, so it is applied last, against the prop-firm drawdown limit. The
per-trade risk multiple comes from a ``risk_fn`` (see :func:`flat` / :func:`throttle`); the risk
policies in :mod:`research.portfolio.risk` build those. :func:`simulate` runs the
path-dependent daily simulation and returns the daily realized-balance and equity series (for the
drawdown check) plus the size each trade was given (for honest per-trade metrics). A constant
``risk_fn`` reproduces flat sizing exactly (covered by tests).
"""

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import numpy.typing as npt
import pandas as pd

from research.portfolio.curves import interval_loss_days
from research.portfolio.drawdown import trailing_floor

_OPEN, _CLOSE = 0, 1
_H4_NS = 14_400_000_000_000
_H4_UPPER_BOUND = (
    "H4 upper bound: contemporaneous positions may hit their direction-adverse "
    "extremes within the same H4 interval"
)
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class DailyDiagnostics:
    """One shared daily risk path for sizing, gates, verdicts, and reports.

    Monetary arrays are the established NumPy boundary used by the portfolio API. H4 price and
    money aggregation is performed in :class:`~decimal.Decimal` before the result crosses that
    boundary. The minimum is an H4 upper bound: positions open in the same H4 interval may all be
    marked at their direction-adverse extreme simultaneously.
    """

    days: np.ndarray
    opening_balance: np.ndarray
    close_balance: np.ndarray
    close_equity: np.ndarray
    minimum_equity: np.ndarray
    daily_loss: np.ndarray
    trailing_floor: np.ndarray
    daily_breach: np.ndarray
    trailing_breach: np.ndarray
    h4_upper_bound: str = _H4_UPPER_BOUND

    @property
    def breached(self) -> bool:
        """Whether either hard account-limit path breached."""
        return bool(self.daily_breach.any() or self.trailing_breach.any())

    @property
    def max_drawdown_pct(self) -> float:
        """Worst H4 minimum from the running close-equity peak, including opening capital."""
        if not self.minimum_equity.size:
            return 0.0
        prior_peak = np.maximum.accumulate(
            np.concatenate([[self.opening_balance[0]], self.close_equity])
        )[:-1]
        peak = np.maximum(prior_peak, self.close_equity)
        return round(float(((self.minimum_equity - peak) / peak).min()) * 100.0, 2)


def _events(trades: pd.DataFrame) -> dict[int, list[tuple[int, int]]]:
    """Per day, the ``(kind, trade-index)`` events in TRUE intraday order.

    One merged stream, sorted by ``(timestamp, kind)`` -- not separate open/close lists. Sorting
    the lists separately still processed every open before any close, so a trade closing at 08:00
    could not inform the sizing of one opening at 20:00 (Codex round 5). At equal timestamps opens
    sort first, which keeps the invariant a same-bar round trip depends on: it opens before it
    closes. Streams without timestamp columns fall back to day numbers, where all of a day's
    stamps tie and the old opens-then-closes order is reproduced.
    """
    od, cd = trades["od"].to_numpy(), trades["cd"].to_numpy()
    ts_o = trades["ts_opened"].to_numpy() if "ts_opened" in trades.columns else od
    ts_c = trades["ts_closed"].to_numpy() if "ts_closed" in trades.columns else cd
    raw: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    for i in range(len(trades)):
        raw[int(od[i])].append((int(ts_o[i]), _OPEN, i))
        raw[int(cd[i])].append((int(ts_c[i]), _CLOSE, i))
    return {day: [(kind, i) for _, kind, i in sorted(evs)] for day, evs in raw.items()}


def _decimal(value: object) -> Decimal:
    """Exact decimal representation at the pandas/NumPy input boundary."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _validated_h4_prices(
    h4_prices: Mapping[str, pd.DataFrame],
) -> dict[str, dict[int, tuple[Decimal, Decimal, Decimal]]]:
    """Validate and index H4 lows/highs by exact market timestamp."""
    required = {"timestamp_ns", "low", "high", "close"}
    indexed: dict[str, dict[int, tuple[Decimal, Decimal, Decimal]]] = {}
    for market, frame in h4_prices.items():
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{market} H4 prices are missing columns: {sorted(missing)}")
        rows: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
        previous: int | None = None
        for row in frame.itertuples(index=False):
            timestamp = int(row.timestamp_ns)
            if previous is not None and timestamp <= previous:
                raise ValueError(f"{market} H4 timestamps must be strictly increasing")
            previous = timestamp
            low, high, close = _decimal(row.low), _decimal(row.high), _decimal(row.close)
            if not low.is_finite() or not high.is_finite() or not close.is_finite():
                raise ValueError(f"{market} has non-finite H4 prices at timestamp {timestamp}")
            if low > high or not low <= close <= high:
                raise ValueError(f"{market} has invalid H4 OHLC bounds at timestamp {timestamp}")
            rows[timestamp] = (low, high, close)
        indexed[str(market)] = rows
    return indexed


def _synchronized_h4_minima(
    trades: pd.DataFrame,
    sizes: FloatArray,
    h4_prices: Mapping[str, pd.DataFrame] | None,
    days: npt.NDArray[np.int64],
    opening_balance: FloatArray,
    close_equity: FloatArray,
    start_balance: float,
) -> FloatArray:
    """Minimum equity by loss day from synchronized, lifetime-filtered H4 adverse marks."""
    minimum: FloatArray = np.minimum(opening_balance, close_equity)
    if h4_prices is None:
        return minimum
    if "ts_opened" not in trades or "ts_closed" not in trades:
        raise ValueError("synchronized H4 reconstruction requires ts_opened and ts_closed")

    indexed = _validated_h4_prices(h4_prices)
    opened = trades["ts_opened"].to_numpy(dtype=np.int64)
    closed = trades["ts_closed"].to_numpy(dtype=np.int64)
    markets = trades["market"].astype(str).to_numpy()
    pnl = trades["pnl_base"].to_numpy(dtype=float)
    swap = (
        trades["swap_base"].to_numpy(dtype=float)
        if "swap_base" in trades.columns
        else np.zeros(len(trades), dtype=float)
    )
    entry = trades["entry"].to_numpy(dtype=float)
    exit_ = trades["exit"].to_numpy(dtype=float)
    if "is_long" in trades.columns:
        is_long = trades["is_long"].to_numpy(dtype=bool)
    else:
        won = pnl > 0
        is_long = won == (exit_ > entry)

    opens_at: dict[int, list[int]] = defaultdict(list)
    closes_at: dict[int, list[int]] = defaultdict(list)
    bar_starts: dict[int, dict[str, tuple[Decimal, Decimal, Decimal]]] = defaultdict(dict)
    bar_ends: dict[int, list[tuple[str, Decimal]]] = defaultdict(list)
    timeline: set[int] = set()
    for index in range(len(trades)):
        opens_at[int(opened[index])].append(index)
        closes_at[int(closed[index])].append(index)
        timeline.update((int(opened[index]), int(closed[index])))
    for market, rows in indexed.items():
        for timestamp, row in rows.items():
            bar_starts[timestamp][market] = row
            bar_ends[timestamp + _H4_NS].append((market, row[2]))
            timeline.update((timestamp, timestamp + _H4_NS))

    active: set[int] = set()
    observed = np.zeros(len(trades), dtype=bool)
    active_bars: dict[str, tuple[int, Decimal, Decimal, Decimal]] = {}
    last_close: dict[str, Decimal] = {}
    realized = Decimal("0")
    start = _decimal(start_balance)
    day_to_index = {int(day): index for index, day in enumerate(days)}

    ordered_times = sorted(timeline)
    for cursor, timestamp in enumerate(ordered_times):
        # A bar's close becomes observable at its interval end. Expire it before selecting the
        # mark for the next half-open interval.
        for market, close_price in bar_ends.get(timestamp, ()):
            active_bar = active_bars.get(market)
            if active_bar is not None and active_bar[0] == timestamp:
                last_close[market] = close_price
                del active_bars[market]

        # A position closing exactly on a boundary is absent from the following interval. Its
        # realized PnL and swap are then available to every later mark.
        for index in closes_at.get(timestamp, ()):
            realized += (_decimal(pnl[index]) + _decimal(swap[index])) * _decimal(sizes[index])
            active.discard(index)

        # A position opening exactly on a boundary participates in that bar, but a zero-duration
        # position is only realized and never receives an H4 mark.
        for index in opens_at.get(timestamp, ()):
            if closed[index] > timestamp:
                active.add(index)

        for market, (low, high, close_price) in bar_starts.get(timestamp, {}).items():
            active_bars[market] = (timestamp + _H4_NS, low, high, close_price)

        if cursor + 1 >= len(ordered_times):
            continue
        interval_end = ordered_times[cursor + 1]
        if interval_end <= timestamp or not active:
            continue

        adverse = Decimal("0")
        for index in sorted(active):
            market = str(markets[index])
            active_row = active_bars.get(market)
            if active_row is None or active_row[0] < interval_end:
                # The market is closed while another market advances. Its observable equity mark
                # is unchanged; carrying its last close (or entry before the first post-entry bar)
                # never borrows an adverse extreme from another interval.
                price = last_close.get(market, _decimal(entry[index]))
            else:
                _bar_end, low, high, _close = active_row
                price = low if is_long[index] else high
                observed[index] = True
            entry_price = _decimal(entry[index])
            exit_price = _decimal(exit_[index])
            span = exit_price - entry_price
            if abs(span) < Decimal("1e-12"):
                span = Decimal("1")
            fraction = (price - entry_price) / span
            adverse += _decimal(pnl[index]) * _decimal(sizes[index]) * fraction
        mark = float(start + realized + adverse)
        for day in interval_loss_days(timestamp, interval_end):
            day_index = day_to_index.get(day)
            if day_index is not None:
                minimum[day_index] = min(minimum[day_index], mark)

    missing_observations = [
        index
        for index in range(len(trades))
        if opened[index] < closed[index] and not observed[index]
    ]
    if missing_observations:
        detail = ", ".join(
            f"{markets[index]} trade {index}" for index in missing_observations[:5]
        )
        raise ValueError(f"no H4 observation overlaps {detail}")
    return np.asarray(minimum, dtype=np.float64)


def _daily_diagnostics(
    trades: pd.DataFrame,
    sizes: np.ndarray,
    h4_prices: Mapping[str, pd.DataFrame] | None,
    d0: int,
    start_balance: float,
    trailing_limit_frac: float,
    daily_limit_frac: float,
    opening_balance: np.ndarray,
    close_balance: np.ndarray,
    close_equity: np.ndarray,
) -> DailyDiagnostics:
    """Build the sole account-limit and drawdown diagnostic path."""
    days = np.arange(d0, d0 + len(close_balance), dtype=np.int64)
    minimum = _synchronized_h4_minima(
        trades,
        sizes,
        h4_prices,
        days,
        opening_balance,
        close_equity,
        start_balance,
    )
    loss_money = np.maximum(0.0, opening_balance - minimum)
    daily_loss = np.divide(
        loss_money,
        opening_balance,
        out=np.full_like(loss_money, np.inf),
        where=opening_balance > 0,
    )
    floor = trailing_floor(close_balance, start_balance, trailing_limit_frac)
    daily_flags = (
        loss_money > daily_limit_frac * opening_balance
        if daily_limit_frac > 0
        else np.zeros(len(minimum), dtype=bool)
    )
    trailing_flags = minimum <= floor
    return DailyDiagnostics(
        days=days,
        opening_balance=opening_balance,
        close_balance=close_balance,
        close_equity=close_equity,
        minimum_equity=minimum,
        daily_loss=daily_loss,
        trailing_floor=floor,
        daily_breach=np.asarray(daily_flags, dtype=bool),
        trailing_breach=np.asarray(trailing_flags, dtype=bool),
    )


def simulate(
    trades: pd.DataFrame,
    prices: dict[str, np.ndarray],
    d0: int,
    d1: int,
    start_balance: float,
    limit_frac: float,
    risk_fn: Callable[[float], float],
    *,
    compound: bool = False,
    h4_prices: Mapping[str, pd.DataFrame] | None = None,
    daily_limit_frac: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, DailyDiagnostics]:
    """Daily (realized_balance, equity) plus the risk multiple each trade was SIZED at.

    Each opening trade is sized ``risk_fn(used)`` where ``used`` in [0, 1] is the fraction
    of the drawdown budget consumed at that moment: ``used = clip(1 - (equity - floor) /
    (limit_frac*start), 0, 1)`` with the hybrid floor (realized-balance HWM minus the
    limit, capped at the starting balance). ``risk_fn`` maps a base risk multiple.

    With ``compound=True`` the risk multiple is additionally scaled by ``equity/start_balance``
    at the moment each trade opens, so the money risked tracks the *current* equity (fixed-
    fractional) instead of the fixed starting balance -- the returns then compound. ``pnl_base``
    is booked flat off the start balance, so this equity ratio is exactly the compounding factor.

    The returned ``sizes`` array (aligned to ``trades``' rows) is what makes per-trade metrics
    honest under a dynamic policy: each trade's PnL contribution is ``pnl_base * size``.
    """
    day_events = _events(trades)
    mk = trades["market"].to_numpy()
    pnl = trades["pnl_base"].to_numpy(dtype=float)
    # Swap is a REALIZED cost of carry -- booked at close, never marked to market (see base_curves).
    swap = (
        trades["swap_base"].to_numpy(dtype=float)
        if "swap_base" in trades.columns
        else np.zeros(len(trades))
    )
    entry = trades["entry"].to_numpy(dtype=float)
    exit_ = trades["exit"].to_numpy(dtype=float)
    span = np.where(np.abs(exit_ - entry) < 1e-12, 1.0, exit_ - entry)
    budget = limit_frac * start_balance

    def frac(i: int, day: int) -> float:
        return float((prices[mk[i]][day - d0] - entry[i]) / span[i])

    size = np.zeros(len(trades))
    open_set: set[int] = set()
    realized = 0.0  # excess over start
    peak_bal = start_balance  # realized-balance high-water mark
    opening_series = np.empty(d1 - d0 + 1)
    realized_series = np.empty(d1 - d0 + 1)
    equity_series = np.empty(d1 - d0 + 1)

    for k, day in enumerate(range(d0, d1 + 1)):
        opening_series[k] = start_balance + realized
        # 1. Replay the day's events in TRUE intraday order: a close at 08:00 books its PnL
        # before an open at 20:00 sizes off the balance. Each open is sized off the equity at
        # ITS moment (realized so far + the current open set's mark), so a morning loss can no
        # longer be invisible to an evening entry -- which overstated compound/throttle sizes
        # and understated the chance of hitting the daily/trailing limits.
        for kind, i in day_events.get(day, ()):
            if kind == _OPEN:
                peak_bal = max(peak_bal, start_balance + realized)
                floor = min(start_balance, peak_bal - budget)
                unreal = sum(pnl[j] * size[j] * frac(j, day) for j in open_set)
                equity = start_balance + realized + unreal
                used = min(1.0, max(0.0, 1.0 - (equity - floor) / budget))
                r = risk_fn(used)
                if compound:
                    r *= equity / start_balance  # fixed-fractional: risk tracks current equity
                size[i] = r
                open_set.add(i)
            else:  # 2. realize the closer (sized at its own open) + its swap
                realized += (pnl[i] + swap[i]) * size[i]
                open_set.discard(i)
        peak_bal = max(peak_bal, start_balance + realized)
        unreal = sum(pnl[j] * size[j] * frac(j, day) for j in open_set)  # 3. EOD mark
        realized_series[k] = start_balance + realized
        equity_series[k] = start_balance + realized + unreal
    diagnostics = _daily_diagnostics(
        trades,
        size,
        h4_prices,
        d0,
        start_balance,
        limit_frac,
        daily_limit_frac,
        opening_series,
        realized_series,
        equity_series,
    )
    return realized_series, equity_series, size, diagnostics


def flat(multiple: float) -> Callable[[float], float]:
    """A constant sizing policy (ignores the used-budget fraction)."""
    return lambda _used: multiple


def throttle(base: float, floor_frac: float = 0.15) -> Callable[[float], float]:
    """Linear throttle: ``base`` at a fresh buffer, tapering to ``base*floor_frac`` at the wall."""
    return lambda used: base * max(floor_frac, 1.0 - used)
