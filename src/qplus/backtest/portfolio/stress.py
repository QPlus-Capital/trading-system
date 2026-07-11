"""Sizing (Stage 5) -- the tail cap: does the sized account survive a WORSE-than-history gap?

Fitting the risk to the worst path *seen in the sample* is unsafe: the next crisis can be worse than
the worst historical gap, so a risk fit to a benign window would be killed by a COVID-repeat.

This models the binding real constraint for a gap-exposed reversal strategy: a single catastrophic
day gapping through the stops. The worst historical single-DAY loss in R (several positions gapping
together, which the hard *daily* limit sees as one loss) is amplified by a ``stress_mult`` (headroom
for a worse-than-history gap), and that stressed loss must stay inside the hard daily limit at the
chosen flat risk. The truly-safe risk is the MIN of this tail cap and the risk-constrained-Kelly
drawdown bound (see :mod:`qplus.backtest.portfolio.risk`) -- so a worse-than-history gap never
breaches.

Works in **R-multiples** (the scale-invariant per-trade risk unit) via the trade stream's ``r``
column -- NOT ``pnl_base``, which compounds with the growing equity over a long history and would
explode. Run it on the FULL history (all crises), not the reserved holdout (which omits the worst
tails -- exactly why a holdout-fit risk is unsafe).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_DAY_NS = 86_400_000_000_000
_DAILY_HARD = 0.03  # TTP hard daily loss limit (account death)
_TRAILING_HARD = 0.06  # TTP hard trailing max-drawdown limit


def worst_trade_r(trades: pd.DataFrame) -> float:
    """The worst single-trade loss in R (most negative ``r``)."""
    r = np.asarray(trades["r"], dtype=float)
    return float(r.min()) if r.size else 0.0


def worst_day_r(trades: pd.DataFrame) -> float:
    """The worst single-day realized loss in R (``r`` summed by close day) -- captures several
    positions gapping on the same day, which the hard *daily* limit sees as one loss."""
    if len(trades) == 0:
        return 0.0
    day = (trades["ts_closed"].to_numpy() // _DAY_NS).astype(int)
    by_day = pd.Series(trades["r"].to_numpy(dtype=float)).groupby(day).sum()
    return float(by_day.min())


def tail_safe_risk(
    worst_r: float,
    *,
    stress_mult: float,
    daily_hard: float = _DAILY_HARD,
    trailing_hard: float = _TRAILING_HARD,
) -> float:
    """Largest flat risk fraction whose ``stress_mult x worst_r`` single-event loss stays inside
    the hard limits. A single event is a same-day loss, so the tighter daily limit binds."""
    loss_r = stress_mult * abs(worst_r)
    return min(daily_hard, trailing_hard) / loss_r if loss_r > 0 else float("inf")


@dataclass(frozen=True)
class StressResult:
    """Tail-stress ceiling for the trade stream at a given stress multiple."""

    worst_trade_r: float
    worst_day_r: float
    stress_mult: float
    tail_safe_risk_pct: float  # max flat risk % surviving the stressed worst single-day gap


def stress_ceiling(
    trades: pd.DataFrame,
    *,
    stress_mult: float = 1.5,
    daily_hard: float = _DAILY_HARD,
    trailing_hard: float = _TRAILING_HARD,
) -> StressResult:
    """The tail-stress-safe flat risk (%): survives ``stress_mult`` x the worst historical
    single-day gap without breaching the hard daily limit. Uses the worst DAY (not just the worst
    trade) so concurrent gaps are counted as the hard limit would count them. Requires an ``r``
    column and the FULL history (so the worst crisis tail is present)."""
    wt = worst_trade_r(trades)
    wd = worst_day_r(trades)
    safe = tail_safe_risk(
        wd, stress_mult=stress_mult, daily_hard=daily_hard, trailing_hard=trailing_hard
    )
    return StressResult(
        worst_trade_r=round(wt, 2),
        worst_day_r=round(wd, 2),
        stress_mult=stress_mult,
        tail_safe_risk_pct=round(safe * 100, 4),
    )


def survives(
    trades: pd.DataFrame,
    risk_frac: float,
    *,
    stress_mult: float = 1.5,
    daily_hard: float = _DAILY_HARD,
    trailing_hard: float = _TRAILING_HARD,
) -> bool:
    """Whether ``risk_frac`` (flat risk as a fraction) survives a ``stress_mult`` x worst-day gap
    without breaching the hard limits -- the acceptance-gate form of :func:`stress_ceiling`."""
    ceiling = tail_safe_risk(
        worst_day_r(trades),
        stress_mult=stress_mult,
        daily_hard=daily_hard,
        trailing_hard=trailing_hard,
    )
    return risk_frac <= ceiling
