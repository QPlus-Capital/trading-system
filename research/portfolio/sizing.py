"""Position-sizing simulation: the per-trade risk function + the daily path.

Sizing only *scales* trade PnL, so it is applied last, against the prop-firm drawdown limit. The
per-trade risk multiple comes from a ``risk_fn`` (see :func:`flat` / :func:`throttle`); the risk
policies in :mod:`research.portfolio.risk` build those. :func:`simulate` runs the
path-dependent daily simulation and returns the daily realized-balance and equity series (for the
drawdown check) plus the size each trade was given (for honest per-trade metrics). A constant
``risk_fn`` reproduces flat sizing exactly (covered by tests).
"""

from collections import defaultdict
from collections.abc import Callable

import numpy as np
import pandas as pd

_OPEN, _CLOSE = 0, 1


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
    adverse: tuple[dict[str, np.ndarray], dict[str, np.ndarray]] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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

    if "is_long" in trades.columns:
        is_long = trades["is_long"].to_numpy(dtype=bool)
    else:
        # Legacy streams (written before is_long existed): direction has to be inferred, and
        # `exit > entry` alone is WRONG -- it calls every losing long a short and vice versa,
        # which then marks the position at the wrong daily extreme and can hide an intraday
        # breach. Combine the price move with the outcome, as core.broker does.
        won = trades["pnl_base"].to_numpy(dtype=float) > 0
        is_long = won == (exit_ > entry)

    def frac_adverse(i: int, day: int) -> float:
        """Mark at the day's WORST price for this position's direction (#15).

        A long suffers at the day's LOW, a short at its HIGH -- so the extreme is chosen per
        trade, not per market: two positions on the same symbol can face opposite ways.
        """
        if adverse is None:
            return frac(i, day)
        lows, highs = adverse
        px = lows[mk[i]][day - d0] if is_long[i] else highs[mk[i]][day - d0]
        return float((px - entry[i]) / span[i])

    size = np.zeros(len(trades))
    open_set: set[int] = set()
    realized = 0.0  # excess over start
    peak_bal = start_balance  # realized-balance high-water mark
    realized_series = np.empty(d1 - d0 + 1)
    equity_series = np.empty(d1 - d0 + 1)
    min_equity_series = np.empty(d1 - d0 + 1)  # worst intraday mark, for the daily-limit gate

    for k, day in enumerate(range(d0, d1 + 1)):
        # Everything open at ANY point today feeds the intraday worst mark below -- positions
        # carried in, plus every open that happens during the day (added as it occurs).
        active_today = set(open_set)
        realized_before = realized  # the day's opening balance -- see the worst mark below
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
                active_today.add(i)
            else:  # 2. realize the closer (sized at its own open) + its swap
                realized += (pnl[i] + swap[i]) * size[i]
                open_set.discard(i)
        peak_bal = max(peak_bal, start_balance + realized)
        unreal = sum(pnl[j] * size[j] * frac(j, day) for j in open_set)  # 3. EOD mark
        # 4. Worst intraday mark: every position that traded today at its own adverse extreme, and
        # NONE of today's closers booked yet -- at the worst moment they had not closed. Marking
        # them adversely while also counting their realized PnL would double-count them.
        # Assuming they all bottom at the same instant OVERSTATES the dip, deliberately: this
        # feeds a hard-limit gate, and the previous EOD-only estimate understated it (a day can
        # dip 3% and close at -0.5%). Conservative is the correct side to err on here.
        worst = sum(pnl[j] * size[j] * frac_adverse(j, day) for j in active_today)
        realized_series[k] = start_balance + realized
        equity_series[k] = start_balance + realized + unreal
        min_equity_series[k] = min(
            equity_series[k], start_balance + realized_before + worst
        )
    return realized_series, equity_series, size, min_equity_series


def flat(multiple: float) -> Callable[[float], float]:
    """A constant sizing policy (ignores the used-budget fraction)."""
    return lambda _used: multiple


def throttle(base: float, floor_frac: float = 0.15) -> Callable[[float], float]:
    """Linear throttle: ``base`` at a fresh buffer, tapering to ``base*floor_frac`` at the wall."""
    return lambda used: base * max(floor_frac, 1.0 - used)
