"""Pure logic behind the dashboard's risk header and history window.

Kept out of ``dashboard.py`` because both rules here are the kind that must be tested rather than
eyeballed in a browser: one decides what an operator is told about available risk headroom, the
other decides the basis every displayed R is measured against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from monitoring.deals import balance_at, to_ns


@dataclass(frozen=True)
class OpenRisk:
    """What the dashboard may claim about currently open exposure."""

    total: float
    unpriceable: list[str] = field(default_factory=list)

    @property
    def determinate(self) -> bool:
        """False when any position cannot be priced -- then no headroom may be shown at all."""
        return not self.unpriceable


def summarize_open_risk(priced: list[tuple[str, float | None]]) -> OpenRisk:
    """Total open stop-risk, and the markets whose risk could not be established.

    ``priced`` is ``(market, risk)`` per open position, with ``None`` where neither the broker's
    own order-profit calculation nor the tick-value arithmetic could price the stop.

    The runner charges an unpriceable position as INFINITE risk and refuses to open anything more
    (:func:`live.runner._total_open_risk`). The dashboard must say the same: reporting the sum of
    the positions it *could* price would show headroom under the cap while the account is in fact
    blocked, which is precisely the situation in which an operator might intervene wrongly.
    """
    total = sum(r for _, r in priced if r is not None)
    unpriceable = sorted(m for m, r in priced if r is None)
    return OpenRisk(total=total, unpriceable=unpriceable)


@dataclass(frozen=True)
class HistoryWindow:
    """The trades to display, their risk basis, and the balance entering the window."""

    trades: pd.DataFrame
    risk: np.ndarray
    start_balance: float
    hidden: int


def window_history(
    all_trades: pd.DataFrame,
    all_risk: np.ndarray,
    *,
    window_start: pd.Timestamp,
    current_balance: float,
    ledger: pd.DataFrame | None = None,
) -> HistoryWindow:
    """Restrict a full history to the display window WITHOUT changing any trade's risk basis.

    Each trade is sized against the equity it had at its own open, so the basis has to be walked
    from the account's start over every trade that ever happened. Walking only the window instead
    charges the first displayed trade the account's opening balance no matter how much the account
    had grown or drawn down before it -- distorting expectancy and cumulative R for the whole view,
    and worst exactly where the window is shortest.

    The returned ``start_balance`` is the balance the account actually held entering the window --
    read off the same backwards walk as the risk bases, so it accounts for cash flows before the
    window as well as trades. Deriving it from hidden trade PnL alone would offset the equity
    curve by every earlier payout.
    """
    entering = float(
        balance_at(to_ns(pd.Series([window_start])), current_balance, ledger)[0]
    )
    if all_trades.empty:
        return HistoryWindow(all_trades, all_risk, entering, 0)

    shown = (all_trades["close_time"] >= window_start).to_numpy()
    return HistoryWindow(
        trades=all_trades[shown].reset_index(drop=True),
        risk=all_risk[shown],
        start_balance=entering,
        hidden=int((~shown).sum()),
    )
