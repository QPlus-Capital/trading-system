"""Live risk control -- keep the account within the prop-firm limits (Phase 3).

Pure decision logic; the live runner feeds it the account equity/balance and the open
positions. It enforces, with safety margins BELOW the hard TTP limits (6% trailing / 3%
daily), the values Jan chose:

- **risk per trade** 0.20% (position sizing),
- **daily loss stop** 2.5% (hard limit 3%),
- **trailing max-drawdown stop** 5% (hard limit 6%; floor caps at the starting balance),
- **total-open-risk cap** 1.5% -- the sum of all open stop-risks, so even a same-day full
  stop-out of every open position stays under the daily limit.

Everything here is deterministic and unit-tested; the runner (Phase 4) supplies the live
numbers and acts on the decisions (size / block / flatten).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    """Risk parameters (fractions of balance/equity). Defaults = Jan's chosen values."""

    risk_per_trade: float = 0.0020  # 0.20% of equity risked per trade
    daily_stop: float = 0.025  # halt for the day at 2.5% loss (hard TTP = 3%)
    trailing_stop: float = 0.05  # halt at 5% trailing drawdown (hard TTP = 6%)
    open_risk_cap: float = 0.015  # max combined open stop-risk = 1.5% of equity


@dataclass(frozen=True)
class Decision:
    """Outcome of a risk check."""

    allowed: bool
    reason: str


def position_volume(
    risk_amount: float,
    stop_distance: float,
    tick_size: float,
    tick_value: float,
    *,
    min_lot: float,
    lot_step: float,
    max_lot: float,
) -> float:
    """Lots so a stop-out loses ~``risk_amount``. Rounded DOWN to ``lot_step``; 0 if < min lot.

    ``tick_value`` is the money one lot gains/loses per ``tick_size`` of price move (from the
    MT5 symbol info). Returns 0.0 when the smallest tradeable lot would already exceed the
    target risk -- the caller then skips the trade (never silently over-risks).
    """
    if stop_distance <= 0 or tick_size <= 0 or tick_value <= 0 or lot_step <= 0:
        return 0.0
    loss_per_lot = (stop_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return 0.0
    raw = risk_amount / loss_per_lot
    vol = math.floor(raw / lot_step) * lot_step
    vol = min(vol, max_lot)
    return vol if vol >= min_lot else 0.0


class RiskController:
    """Tracks the account references and gates trading against the limits."""

    def __init__(self, limits: RiskLimits, start_balance: float) -> None:
        self.limits = limits
        self.start_balance = start_balance
        self.day_start_balance = start_balance  # balance at the start of the trading day
        self.hwm_balance = start_balance  # realized end-of-day balance high-water mark
        self.open_risk = 0.0  # sum of the $ stop-risk of all currently open positions

    # -- persistence (survive a runner restart without losing the risk references) --
    def snapshot(self) -> dict[str, float]:
        """The durable references (start / HWM / day-start balance) for saving to disk."""
        return {
            "start_balance": self.start_balance,
            "hwm_balance": self.hwm_balance,
            "day_start_balance": self.day_start_balance,
        }

    def restore(self, snap: Mapping[str, float]) -> None:
        """Reload the durable references from a saved :meth:`snapshot`."""
        self.start_balance = snap["start_balance"]
        self.hwm_balance = snap["hwm_balance"]
        self.day_start_balance = snap["day_start_balance"]

    # -- references the runner keeps updated --
    def on_new_day(self, balance: float) -> None:
        self.day_start_balance = balance

    def on_eod(self, balance: float) -> None:
        self.hwm_balance = max(self.hwm_balance, balance)

    def on_open(self, risk_amount: float) -> None:
        self.open_risk += risk_amount

    def on_close(self, risk_amount: float) -> None:
        self.open_risk = max(0.0, self.open_risk - risk_amount)

    # -- the safety floors --
    def trailing_floor(self) -> float:
        """Equity floor from the trailing stop; caps at the starting balance."""
        return min(
            self.start_balance, self.hwm_balance - self.limits.trailing_stop * self.start_balance
        )

    def daily_floor(self) -> float:
        """Equity floor from the daily stop (relative to the day's starting balance)."""
        return self.day_start_balance - self.limits.daily_stop * self.day_start_balance

    def must_flatten(self, equity: float) -> Decision:
        """Hard stop: if equity is at/below a safety floor, flatten everything and halt."""
        if equity <= self.trailing_floor():
            return Decision(
                True, f"trailing stop: equity {equity:.0f} <= floor {self.trailing_floor():.0f}"
            )
        if equity <= self.daily_floor():
            return Decision(
                True, f"daily stop: equity {equity:.0f} <= daily floor {self.daily_floor():.0f}"
            )
        return Decision(False, "")

    def check_open(
        self, trade_risk: float, equity: float, *, exclude_risk: float = 0.0
    ) -> Decision:
        """Pre-trade gate: block the entry if its worst case could breach a safety limit.

        ``exclude_risk`` (M2) is the stop-risk of a position being CLOSED as part of this action
        (a reversal): it is removed from the open total so a valid reversal is not blocked by the
        risk of the very position it replaces.
        """
        effective_open = max(0.0, self.open_risk - exclude_risk)
        if effective_open + trade_risk > self.limits.open_risk_cap * equity:
            return Decision(
                False, f"open-risk cap {self.limits.open_risk_cap:.1%} would be exceeded"
            )
        worst = equity - (effective_open + trade_risk)  # everything still open + this trade stops
        if worst <= self.daily_floor():
            return Decision(False, "worst case would breach the daily stop")
        if worst <= self.trailing_floor():
            return Decision(False, "worst case would breach the trailing stop")
        return Decision(True, "ok")
