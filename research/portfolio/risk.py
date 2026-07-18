"""The risk system: an account context + a pluggable, tail-capped sizing policy.

Principle (framework-wide): *nothing strategy-specific is baked in.* The framework never
hardcodes a risk like "0.15%" -- it sizes against an :class:`AccountProfile` (the account /
prop-firm rules) using a chosen :class:`RiskPolicy`. Three policies today:

* :class:`FlatRisk` -- one constant risk every trade (the special case "policy = constant");
* :class:`ThrottleRisk` -- dynamic risk that runs at the ceiling with a fresh buffer and tapers
  toward a floor near the drawdown wall;
* :class:`KellyRisk` -- risk-constrained Kelly: the growth-optimal flat fraction derived from the
  trade distribution under a drawdown-probability bound (see :func:`rck_fraction`).

Every policy is hard-capped by the strategy's OWN tail: :func:`tail_cap` is the largest risk whose
``stress_mult`` x worst-day gap still fits the hard daily limit (see :mod:`stress`). The crisis sets
the CEILING; within it a policy is free to move risk between a floor and that ceiling in normal
times -- so a single fixed risk (over-conservative in good times) is no longer forced on us.

A resolved policy yields a ``risk_fn`` in *multiples of the account's base risk*, which the daily
path simulation (:func:`sizing.simulate`) consumes directly; ``FlatRisk`` reproduces flat
sizing exactly (a constant ``risk_fn``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.portfolio.curves import align_prices, to_day
from research.portfolio.drawdown import daily_breach, evaluate
from research.portfolio.sizing import flat, simulate, throttle
from research.portfolio.stress import tail_safe_risk, worst_day_r


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
    risk_fn: Callable[[float], float]  # risk multiple given the used-budget fraction (simulate)
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
        cap_pct = cap_frac * 100.0
        ceil_mult = cap_frac / account.base_risk_frac
        # A throttle only means something when its floor sits BELOW the tail cap: it runs between
        # the floor and the ceiling. If the requested floor is already at or above the cap, the
        # policy is pinned to the cap -- it degenerates to flat sizing there. Report it honestly
        # (floor == ceiling == cap) instead of the nonsensical "0.15% -> 0.04%" inverted range.
        if self.floor_pct >= cap_pct:
            capped = round(cap_pct, 4)
            return ResolvedRisk("throttle(flat@cap)", flat(ceil_mult), capped, capped)
        floor_of_ceiling = (self.floor_pct / 100.0) / cap_frac if cap_frac > 0 else 0.0
        return ResolvedRisk(
            "throttle",
            throttle(ceil_mult, floor_of_ceiling),
            round(cap_pct, 4),
            self.floor_pct,
        )


def _golden_max(f: Callable[[float], float], lo: float, hi: float, iters: int = 100) -> float:
    """argmax of a unimodal (concave) ``f`` on ``[lo, hi]`` by golden-section search."""
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - gr * (b - a), a + gr * (b - a)
    for _ in range(iters):
        if f(c) < f(d):
            a = c
        else:
            b = d
        c, d = b - gr * (b - a), a + gr * (b - a)
    return (a + b) / 2.0


def _bisect_root(f: Callable[[float], float], lo: float, hi: float, iters: int = 100) -> float:
    """Root of ``f`` on ``[lo, hi]`` where ``f(lo) < 0 <= f(hi)`` (monotone crossing)."""
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def rck_fraction(
    r_multiples: Sequence[float], *, alpha: float, beta: float, max_frac: float = 0.05
) -> float:
    """Growth-optimal per-trade risk fraction under a drawdown-probability constraint.

    Risk-constrained Kelly (Busseti, Ryu, Boyd 2016): maximize the expected log growth
    ``E[ln(1 + phi*r)]`` subject to the drawdown bound ``P(ever fall to alpha*W0) <= beta``,
    enforced convexly via ``E[(1 + phi*r)^(-lambda)] <= 1`` with ``lambda = ln(beta)/ln(alpha)``.

    ``r_multiples`` are the per-trade returns in units of the risk taken (R-multiples); ``phi`` is
    the fraction of capital risked per trade (0.002 = 0.2%). ``alpha`` is the wealth floor (e.g.
    0.94 = the 6% trailing wall), ``beta`` the tolerance for ever touching it. Returns 0 when no
    growth-positive feasible bet exists. Capped at ``max_frac`` as a sanity bound.
    """
    r = np.asarray(r_multiples, dtype=float)
    if r.size < 2 or not (0.0 < alpha < 1.0) or not (0.0 < beta < 1.0):
        return 0.0
    lam = math.log(beta) / math.log(alpha)  # > 0 since both logs are negative
    worst = float(r.min())
    # Keep the wealth ratio (1 + phi*r) strictly positive -- it is the base of a fractional power.
    hi = max_frac if worst >= 0.0 else min(max_frac, 0.98 / -worst)
    if hi <= 0.0:
        return 0.0

    def growth(phi: float) -> float:
        return float(np.mean(np.log1p(phi * r)))

    def risk_excess(phi: float) -> float:  # E[(1+phi r)^-lambda] - 1; <= 0 is feasible
        return float(np.mean((1.0 + phi * r) ** (-lam))) - 1.0

    phi_kelly = _golden_max(growth, 0.0, hi)
    if phi_kelly <= 0.0 or growth(phi_kelly) <= 0.0:
        return 0.0
    # risk_excess(0)=0, dips negative for a profitable strategy, then rises back through 0 at the
    # feasible ceiling. Find that ceiling; the answer is the smaller of it and the Kelly optimum.
    if risk_excess(hi) <= 0.0:
        phi_max = hi
    else:
        probe = hi * 1e-4
        if risk_excess(probe) >= 0.0:  # not even a tiny bet is feasible
            return 0.0
        phi_max = _bisect_root(risk_excess, probe, hi)
    return max(0.0, min(phi_kelly, phi_max))


@dataclass(frozen=True)
class KellyRisk:
    """Risk-constrained Kelly sizing: the growth-optimal flat fraction under a drawdown bound.

    ``beta`` is the tolerance for EVER touching the wealth floor ``alpha = 1 - trailing_hard`` (the
    prop firm's trailing drawdown wall). Unlike Flat/Throttle it is data-driven -- it reads the
    trade R-distribution -- so the stage calls :meth:`fraction` and then sizes flat at that fraction
    (still capped by the single-day gap tail, which this trade-sequence bound does not see).
    """

    beta: float

    def fraction(self, trades: pd.DataFrame, account: AccountProfile) -> float:
        alpha = 1.0 - account.trailing_hard
        return rck_fraction(net_r(trades).tolist(), alpha=alpha, beta=self.beta)


# A risk policy the stage can request. Flat/Throttle resolve directly against the tail cap;
# KellyRisk first derives its flat fraction from the trade distribution, then is sized flat.
RiskPolicy = FlatRisk | ThrottleRisk | KellyRisk


def net_r(trades: pd.DataFrame) -> np.ndarray:
    """Each trade's R **net of every modelled cost** -- the one return the whole stack must use.

    ``r`` is gross price R (spread/commission/slippage are already inside it, swap is not, because
    swap is a realized carry cost booked at close rather than marked to market). Sizing, Kelly,
    Monte-Carlo and the reported return must all read the SAME stream, or the headline return is
    net while the risk statistics are gross (#10).
    """
    r: np.ndarray = trades["r"].to_numpy(dtype=float)
    if "swap_r" in trades.columns:
        r = r + trades["swap_r"].to_numpy(dtype=float)  # signed: carry can pay or cost
    return r


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
    policy: FlatRisk | ThrottleRisk,  # KellyRisk is sized flat upstream, so it never reaches here
    cap_frac: float,
    *,
    compound: bool = False,
    daily_low_high: dict[str, tuple[pd.Series, pd.Series]] | None = None,
) -> PolicyResult:
    """Run ``policy`` over the trade stream day by day and report its honest return / drawdown.

    Uses the path-dependent daily simulation (:func:`sizing.simulate`), which sizes each
    trade as it opens from how much of the drawdown budget is already used -- so a throttle really
    runs bigger with a fresh buffer and brakes near the wall, while a flat policy is the constant
    special case. PnL is booked from ``r`` at the flat base risk, so nothing compounds.
    """
    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    t["pnl_base"] = flat_base_pnl(t, account)  # linear in R: safe to scale by a risk multiple
    if "swap_r" in t.columns:  # realized cost of carry, booked at close (never marked to market)
        base = account.base_risk_frac * account.start_balance
        t["swap_base"] = t["swap_r"].to_numpy(dtype=float) * base
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}
    # #15: the day's extremes drive the intraday limit check; without them it degrades to the old
    # end-of-day comparison rather than silently claiming intraday coverage.
    adverse = (
        (
            {m: align_prices(daily_low_high[m][0], d0, d1) for m in t["market"].unique()},
            {m: align_prices(daily_low_high[m][1], d0, d1) for m in t["market"].unique()},
        )
        if daily_low_high
        else None
    )

    resolved = policy.resolve(cap_frac, account)
    realized, equity, sizes, min_equity = simulate(
        t, prices, d0, d1, account.start_balance, account.trailing_hard, resolved.risk_fn,
        compound=compound, adverse=adverse,
    )
    # #15: the daily-limit gate reads the worst INTRADAY mark, not the end-of-day equity -- a day
    # that dips 3% and closes at -0.5% breaches live but was invisible to an EOD-only series.
    breached = bool(
        evaluate(equity, realized, account.start_balance, account.trailing_hard).breached
        or daily_breach(min_equity, account.daily_hard, prior=equity)
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
        # #10: the SAME net stream simulate() books -- realized += (pnl + swap) * size. Handing a
        # gross per-trade PnL downstream would run Monte-Carlo and the edge stats on gross while
        # this result's own return/drawdown are net.
        trade_pnl=(t["pnl_base"].to_numpy(dtype=float) + _swap_base(t)) * sizes,
    )


def _swap_base(t: pd.DataFrame) -> np.ndarray:
    """The per-trade swap in EUR at base risk, or zeros when the stream carries no swap."""
    if "swap_base" in t.columns:
        swap: np.ndarray = t["swap_base"].to_numpy(dtype=float)
        return swap
    return np.zeros(len(t), dtype=float)
