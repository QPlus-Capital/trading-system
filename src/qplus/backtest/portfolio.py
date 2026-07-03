"""Stage 3/4 -- portfolio feasibility scorecard under the prop-firm hybrid rule.

Given the combined, timestamped OOS trade stream for the selected universe (at base risk)
plus each market's daily close, this answers the feasibility question:

* the largest **flat** risk multiple that never breaches the hybrid drawdown rule, and its
  resulting return;
* the best **throttled** (dynamic) sizing over a grid of base multiples, and how much extra
  return it buys at the same hard limit.

Ties together :mod:`portfolio_sim` (daily curves), :mod:`portfolio_dd` (the hybrid rule)
and :mod:`sizing` (policies). Pure given the trade stream + prices; the compute cost is in
producing that trade stream upstream. See ``docs/backtesting-framework.md`` (Stages 3-4).
"""

from dataclasses import dataclass

import pandas as pd

from qplus.backtest.portfolio_dd import evaluate, max_flat_risk
from qplus.backtest.portfolio_sim import align_prices, base_curves, to_day
from qplus.backtest.sizing import throttle, throttle_curves

_DEFAULT_BASES = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)


@dataclass(frozen=True)
class PortfolioResult:
    """Feasibility scorecard for one account trading the selected universe."""

    n_trades: int
    years: float
    flat_risk: float  # max safe flat risk multiple (1.0 = the base risk)
    flat_return_pct: float  # total OOS return at that risk
    flat_ann_pct: float
    throttle_base: float  # best non-breaching throttle base multiple
    throttle_return_pct: float
    throttle_ann_pct: float
    throttle_gain_pct: float  # extra return of throttle vs flat, same hard limit


def score(
    trades: pd.DataFrame,
    daily_close: dict[str, pd.Series],
    *,
    start_balance: float = 200_000.0,
    limit_frac: float = 0.06,
    throttle_bases: tuple[float, ...] = _DEFAULT_BASES,
    throttle_floor: float = 0.15,
) -> PortfolioResult:
    """Score a trade stream (columns: market, ts_opened, ts_closed, pnl_1pct, entry, exit)."""
    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}

    realized, unrealized = base_curves(t, prices, d0, d1)
    equity = realized + unrealized

    flat_m = max_flat_risk(realized, equity, start_balance, limit_frac)
    flat_ret = flat_m * float(realized[-1]) / start_balance

    best_base, best_ret = 0.0, 0.0
    for base in throttle_bases:
        rb, eq = throttle_curves(
            t, prices, d0, d1, start_balance, limit_frac, throttle(base, throttle_floor)
        )
        if not evaluate(eq, rb, start_balance, limit_frac).breached:
            ret = (float(rb[-1]) - start_balance) / start_balance
            if ret > best_ret:
                best_ret, best_base = ret, base

    years = (d1 - d0) / 365.25
    gain = (best_ret - flat_ret) / flat_ret if flat_ret > 0 else 0.0
    return PortfolioResult(
        n_trades=len(t),
        years=round(years, 2),
        flat_risk=round(flat_m, 4),
        flat_return_pct=round(flat_ret * 100, 1),
        flat_ann_pct=round(flat_ret / years * 100, 1) if years > 0 else 0.0,
        throttle_base=best_base,
        throttle_return_pct=round(best_ret * 100, 1),
        throttle_ann_pct=round(best_ret / years * 100, 1) if years > 0 else 0.0,
        throttle_gain_pct=round(gain * 100, 1),
    )
