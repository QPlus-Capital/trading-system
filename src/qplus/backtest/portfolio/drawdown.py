"""Stage 3 -- prop-firm portfolio drawdown rule (The Trading Pit hybrid).

The Trading Pit's maximum-drawdown rule is a hybrid (confirmed from their support docs):

* the drawdown **floor** trails the high-water mark of **end-of-day BALANCE** (realized
  P&L only), minus the limit, and **stops rising once it reaches the starting balance** --
  so after ``limit`` of profit is banked the floor is static at the starting balance;
* a **breach** occurs if **EQUITY** (realized balance + unrealized PnL of open positions)
  ever falls to or below the floor. Floating losses can breach; floating gains do not
  raise the floor.

These are pure functions over pre-built daily series (NumPy only); constructing the daily
balance/equity curves from a trade stream lives in the portfolio simulator that calls
these. See ``docs/backtesting-framework.md`` (Stage 3).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def trailing_floor(
    realized_balance: Sequence[float] | np.ndarray, start_balance: float, limit_frac: float
) -> np.ndarray:
    """Daily drawdown floor: ``min(start, running_max(EOD balance) - limit_frac*start)``.

    Trails the realized end-of-day balance high-water mark, capped at the starting
    balance (the floor never rises above ``start_balance``).

    Timing note (F10): the high-water mark includes the *same* day's balance, so on a day
    that both makes a new balance high and dips in equity, the floor is already raised. That
    is deliberately **conservative** -- it can only over-state breach risk, never understate
    it -- so it is the safe side for a feasibility gate (TTP's floor updates at EOD and
    applies from the next day; using a lagged HWM would be marginally more lenient).
    """
    rb = np.asarray(realized_balance, dtype=float)
    hwm = np.maximum.accumulate(rb)
    return np.minimum(start_balance, hwm - limit_frac * start_balance)


@dataclass(frozen=True)
class DrawdownResult:
    """Outcome of checking an equity path against the trailing floor."""

    breached: bool
    min_margin: float  # min(equity - floor) over the path; <= 0 means a breach
    min_margin_frac: float  # min_margin / start_balance
    breach_index: int  # first day index where equity <= floor, else -1


def evaluate(
    equity: Sequence[float] | np.ndarray,
    realized_balance: Sequence[float] | np.ndarray,
    start_balance: float,
    limit_frac: float,
) -> DrawdownResult:
    """Check an equity path against the balance-trailing floor (the hybrid rule)."""
    eq = np.asarray(equity, dtype=float)
    floor = trailing_floor(realized_balance, start_balance, limit_frac)
    margin = eq - floor
    below = margin <= 0
    breach_index = int(np.argmax(below)) if bool(below.any()) else -1
    min_margin = float(margin.min()) if margin.size else 0.0
    return DrawdownResult(
        breached=bool(below.any()),
        min_margin=min_margin,
        min_margin_frac=min_margin / start_balance,
        breach_index=breach_index,
    )


def max_flat_risk(
    realized_excess: Sequence[float] | np.ndarray,
    equity_excess: Sequence[float] | np.ndarray,
    start_balance: float,
    limit_frac: float,
    *,
    hi: float = 4.0,
    iters: int = 50,
) -> float:
    """Largest flat risk multiple (1.0 = base) that never breaches, under flat sizing.

    ``realized_excess`` / ``equity_excess`` are the base (multiple = 1) daily curves of
    *excess over the starting balance* (realized-only, and equity incl. floating). Because
    both scale linearly with the risk multiple while the starting balance does not, the
    breach condition is monotonic in the multiple, so we bisect for the largest safe one.
    """
    r = np.asarray(realized_excess, dtype=float)
    e = np.asarray(equity_excess, dtype=float)
    r_hwm = np.maximum.accumulate(r)

    def breaches(m: float) -> bool:
        floor_excess = np.minimum(0.0, m * r_hwm - limit_frac * start_balance)  # floor - start
        return bool((m * e - floor_excess <= 0.0).any())  # equity_excess - floor_excess <= 0

    if not breaches(hi):
        return hi
    lo = 0.0
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if breaches(mid):
            hi = mid
        else:
            lo = mid
    return lo
