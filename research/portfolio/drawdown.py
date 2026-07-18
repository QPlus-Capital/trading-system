"""Prop-firm portfolio drawdown rule (The Trading Pit hybrid).

The Trading Pit's maximum-drawdown rule is a hybrid (confirmed from their support docs):

* the drawdown **floor** trails the high-water mark of **end-of-day BALANCE** (realized
  P&L only), minus the limit, and **stops rising once it reaches the starting balance** --
  so after ``limit`` of profit is banked the floor is static at the starting balance;
* a **breach** occurs if **EQUITY** (realized balance + unrealized PnL of open positions)
  ever falls to or below the floor. Floating losses can breach; floating gains do not
  raise the floor.

These are pure functions over pre-built daily series (NumPy only); the daily balance/equity
curves are built from a trade stream by :mod:`research.portfolio.sizing` (``simulate``),
and :func:`evaluate` / :func:`daily_breach` are the breach tests the risk system applies.
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
        breach_index=breach_index,
    )


def daily_breach(
    equity: Sequence[float] | np.ndarray,
    day_loss_frac: float,
    prior: Sequence[float] | np.ndarray | None = None,
    start_balance: float | None = None,
) -> bool:
    """True if any day's equity drop exceeds ``day_loss_frac`` of the PRIOR day's equity.

    Proxy for the prop-firm daily loss limit (TTP: 3%). ``equity`` should be the day's WORST mark
    and ``prior`` the end-of-day series it is measured against (#15): the limit reacts to the
    intraday low, so comparing end-of-day closes alone missed a day that dipped through the limit
    and recovered by the close. Passing only ``equity`` keeps the old end-of-day comparison.

    With intraday marks this errs on the conservative side -- it assumes every open position hits
    its extreme together -- which is the right direction for a hard-limit gate. It used to be a
    lower bound while being used as one. ``day_loss_frac <= 0`` disables the check.

    ``start_balance`` closes the first-day hole: comparing consecutive entries never tests day 0
    against anything, so a simulation whose FIRST loss day dipped through the limit reported no
    breach at all.
    """
    eq = np.asarray(equity, dtype=float)
    base = eq if prior is None else np.asarray(prior, dtype=float)
    if eq.size == 0 or day_loss_frac <= 0:
        return False
    # Each day's worst mark against the previous day's baseline; day 0 against the opening balance.
    opening = base[0] if start_balance is None else float(start_balance)
    baselines = np.concatenate([[opening], base[:-1]])
    losses = baselines - eq
    return bool((losses > day_loss_frac * baselines).any())
