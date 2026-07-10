"""The risk system: an account context + a pluggable, tail-capped sizing policy.

Principle (framework-wide): *nothing strategy-specific is baked in.* The framework never
hardcodes a risk like "0.15%" -- it sizes against an :class:`AccountProfile` (the account /
prop-firm rules) using a chosen :class:`RiskPolicy`. Two policies today, both interchangeable:

* :class:`FlatRisk` -- one constant risk every trade (the special case "policy = constant");
* :class:`ThrottleRisk` -- dynamic risk that runs at the ceiling with a fresh buffer and tapers
  toward a floor near the drawdown wall (Jan's idea).

Every policy is hard-capped by the strategy's OWN tail: :func:`tail_cap` is the largest risk whose
``stress_mult`` x worst-day gap still fits the hard daily limit (see :mod:`stress`). The crisis sets
the CEILING; within it a policy is free to move risk between a floor and that ceiling in normal
times -- so a single fixed risk (over-conservative in good times) is no longer forced on us.

A resolved policy yields a ``risk_fn`` in *multiples of the account's base risk*, which the daily
path simulation (:func:`sizing.throttle_curves`) consumes directly; ``FlatRisk`` reproduces flat
sizing exactly (a constant ``risk_fn``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from qplus.backtest.portfolio.curves import align_prices, to_day
from qplus.backtest.portfolio.drawdown import daily_breach, evaluate
from qplus.backtest.portfolio.sizing import flat, simulate, throttle
from qplus.backtest.portfolio.stress import tail_safe_risk, worst_day_r


@dataclass(frozen=True)
class AccountProfile:
    """The account / prop-firm context the framework sizes against -- NOT strategy-specific.

    ``base_risk_frac`` is the per-trade risk the backtest itself sized at (so PnL curves can be
    re-expressed as multiples of it); the hard limits are the account's death/trailing rules.
    """

    start_balance: float = 200_000.0
    daily_hard: float = 0.03  # hard daily loss limit (fraction of balance) -- account death
    trailing_hard: float = 0.06  # hard trailing max-drawdown limit
    base_risk_frac: float = 0.01  # the risk the backtest sized each trade at (recovers multiples)


# The Trading Pit hard limits (3% daily / 6% trailing) on the study's 200k account.
TTP_ACCOUNT = AccountProfile()


def tail_cap(
    trades: pd.DataFrame, account: AccountProfile, *, stress_mult: float = 1.5
) -> float:
    """Largest flat risk fraction whose ``stress_mult`` x worst-day gap still fits the hard limits.

    The binding real constraint for a gap-exposed strategy: a single catastrophic day cannot be
    tapered, so it caps every policy. Run on the FULL history (all crises present); needs an ``r``
    column. This ceiling is what a :class:`RiskPolicy` may never exceed.
    """
    return tail_safe_risk(
        worst_day_r(trades),
        stress_mult=stress_mult,
        daily_hard=account.daily_hard,
        trailing_hard=account.trailing_hard,
    )


@dataclass(frozen=True)
class ResolvedRisk:
    """A policy resolved against an account + its tail cap: ready for the daily simulation."""

    label: str
    risk_fn: Callable[[float], float]  # risk multiple given used-budget fraction (throttle_curves)
    ceiling_pct: float  # the largest risk the policy runs at, as % of the start balance
    floor_pct: float  # the smallest risk the policy tapers to (== ceiling for flat)


@dataclass(frozen=True)
class FlatRisk:
    """Constant risk on every trade -- the special case "policy = constant"."""

    pct: float  # fixed risk as a percent of the start balance

    def resolve(self, cap_frac: float, account: AccountProfile) -> ResolvedRisk:
        frac = min(self.pct / 100.0, cap_frac)  # a policy may never exceed the tail cap
        mult = frac / account.base_risk_frac
        return ResolvedRisk("flat", flat(mult), round(frac * 100, 4), round(frac * 100, 4))


@dataclass(frozen=True)
class ThrottleRisk:
    """Dynamic risk: at the ceiling (the tail cap) with a fresh buffer, tapering to ``floor_pct``
    near the drawdown wall. The crisis sets the ceiling; good times run full risk."""

    floor_pct: float  # risk floored to this (% of start) at the wall

    def resolve(self, cap_frac: float, account: AccountProfile) -> ResolvedRisk:
        ceil_mult = cap_frac / account.base_risk_frac
        floor_of_ceiling = min(1.0, (self.floor_pct / 100.0) / cap_frac) if cap_frac > 0 else 0.0
        return ResolvedRisk(
            "throttle", throttle(ceil_mult, floor_of_ceiling), round(cap_frac * 100, 4),
            self.floor_pct,
        )


# A risk policy is anything that resolves to a ResolvedRisk against an account + tail cap.
RiskPolicy = FlatRisk | ThrottleRisk


def flat_base_pnl(trades: pd.DataFrame, account: AccountProfile) -> np.ndarray:
    """Each trade's EUR contribution at exactly the base risk, sized FLAT off the start balance.

    Built from ``r`` (not ``pnl_base``, which compounds with the backtest's growing equity), so the
    daily simulation can scale it linearly by any risk multiple without inventing compounding.
    """
    r = trades["r"].to_numpy(dtype=float)
    out: np.ndarray = r * account.base_risk_frac * account.start_balance
    return out


@dataclass(frozen=True)
class PolicyResult:
    """What one policy earns and risks on a trade stream, honestly (flat in R, net of costs)."""

    label: str
    ceiling_pct: float
    floor_pct: float
    n_trades: int
    years: float
    total_return_pct: float
    ann_return_pct: float
    ann_return_eur: float
    max_drawdown_pct: float
    breached: bool  # did it ever break the account's hard daily or trailing limit?
    trade_pnl: np.ndarray  # each trade's EUR contribution AT the policy's size (for edge metrics)


def evaluate_policy(
    trades: pd.DataFrame,
    daily_close: dict[str, pd.Series],
    account: AccountProfile,
    policy: RiskPolicy,
    cap_frac: float,
) -> PolicyResult:
    """Run ``policy`` over the trade stream day by day and report its honest return / drawdown.

    Uses the path-dependent daily simulation (:func:`sizing.throttle_curves`), which sizes each
    trade as it opens from how much of the drawdown budget is already used -- so a throttle really
    runs bigger with a fresh buffer and brakes near the wall, while a flat policy is the constant
    special case. PnL is booked from ``r`` at the flat base risk, so nothing compounds.
    """
    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    t["pnl_base"] = flat_base_pnl(t, account)  # linear in R: safe to scale by a risk multiple
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}

    resolved = policy.resolve(cap_frac, account)
    realized, equity, sizes = simulate(
        t, prices, d0, d1, account.start_balance, account.trailing_hard, resolved.risk_fn
    )
    breached = bool(
        evaluate(equity, realized, account.start_balance, account.trailing_hard).breached
        or daily_breach(equity, account.daily_hard)
    )
    years = max((d1 - d0) / 365.25, 1e-9)
    total = (float(realized[-1]) - account.start_balance) / account.start_balance
    peak = np.maximum.accumulate(equity)
    return PolicyResult(
        label=resolved.label,
        ceiling_pct=resolved.ceiling_pct,
        floor_pct=resolved.floor_pct,
        n_trades=len(t),
        years=round(years, 2),
        total_return_pct=round(total * 100, 1),
        ann_return_pct=round(total / years * 100, 1),
        ann_return_eur=round(float(realized[-1]) - account.start_balance, 0) / years,
        max_drawdown_pct=round(float(((equity - peak) / peak).min()) * 100, 2),
        breached=breached,
        trade_pnl=t["pnl_base"].to_numpy(dtype=float) * sizes,
    )
