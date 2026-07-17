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


def _events(trades: pd.DataFrame) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    openers: dict[int, list[int]] = defaultdict(list)
    closers: dict[int, list[int]] = defaultdict(list)
    for i, (o, c) in enumerate(zip(trades["od"].to_numpy(), trades["cd"].to_numpy(), strict=True)):
        openers[int(o)].append(i)
        closers[int(c)].append(i)
    return openers, closers


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    openers, closers = _events(trades)
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
    realized_series = np.empty(d1 - d0 + 1)
    equity_series = np.empty(d1 - d0 + 1)

    for k, day in enumerate(range(d0, d1 + 1)):
        # 1. size & open today's openers FIRST (before closers), so a trade that opens and
        # closes the same day is sized before it is realized -- otherwise it would book at
        # size 0 and linger in open_set forever with bogus unrealized PnL.
        if openers.get(day):
            peak_bal = max(peak_bal, start_balance + realized)
            floor = min(start_balance, peak_bal - budget)
            unreal = sum(pnl[j] * size[j] * frac(j, day) for j in open_set)
            equity = start_balance + realized + unreal
            used = min(1.0, max(0.0, 1.0 - (equity - floor) / budget))
            r = risk_fn(used)
            if compound:
                r *= equity / start_balance  # fixed-fractional: risk tracks current equity
            for i in openers[day]:
                size[i] = r
                open_set.add(i)
        for i in closers.get(day, ()):  # 2. realize closers (now correctly sized) + their swap
            realized += (pnl[i] + swap[i]) * size[i]
            open_set.discard(i)
        peak_bal = max(peak_bal, start_balance + realized)
        unreal = sum(pnl[j] * size[j] * frac(j, day) for j in open_set)  # 3. EOD mark
        realized_series[k] = start_balance + realized
        equity_series[k] = start_balance + realized + unreal
    return realized_series, equity_series, size


def flat(multiple: float) -> Callable[[float], float]:
    """A constant sizing policy (ignores the used-budget fraction)."""
    return lambda _used: multiple


def throttle(base: float, floor_frac: float = 0.15) -> Callable[[float], float]:
    """Linear throttle: ``base`` at a fresh buffer, tapering to ``base*floor_frac`` at the wall."""
    return lambda used: base * max(floor_frac, 1.0 - used)
