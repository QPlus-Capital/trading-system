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

from qplus.backtest.foundation.montecarlo import monte_carlo_paths, summarize
from qplus.backtest.portfolio.curves import align_prices, base_curves, to_day, worst_unrealized
from qplus.backtest.portfolio.drawdown import daily_breach, evaluate, max_flat_risk
from qplus.backtest.portfolio.sizing import throttle, throttle_curves

# Throttle base multipliers, RELATIVE to the feasible flat risk: the throttle's whole point
# is to run a higher base at the highs and taper near the wall, so absolute bases would miss
# it entirely when the feasible flat risk is small (e.g. 0.2x).
_DEFAULT_MULTS = (1.0, 1.5, 2.0, 3.0, 4.0, 6.0)


@dataclass(frozen=True)
class PortfolioResult:
    """Feasibility scorecard for one account trading the selected universe.

    The ``live_*`` fields are the HONEST planning numbers: the return of trading at the fixed
    flat live risk (``live_risk_pct``), booked linearly in R off the fixed start balance -- the
    same methodology as :mod:`equity_report`. The ``flat_*``/``throttle_*`` fields are the
    max-feasible CEILING (largest risk the drawdown limit *allows*); they compound with the
    growing equity and are NOT what we trade -- keep them only as a headroom reference.
    """

    n_trades: int
    years: float
    flat_risk: float  # max safe flat risk multiple (1.0 = the base risk) -- the CEILING, not traded
    flat_return_pct: float  # total OOS return at that ceiling risk (compounded -- reference only)
    flat_ann_pct: float
    throttle_base: float  # best non-breaching throttle base multiple
    throttle_return_pct: float
    throttle_ann_pct: float
    throttle_gain_pct: float  # extra return of throttle vs flat, same hard limit
    # -- HONEST flat sizing at the chosen live risk (what we actually plan/trade) --
    live_risk_pct: float = 0.0  # flat risk sized at, as % of the start balance (e.g. 0.15)
    live_ann_pct: float = 0.0  # annualised return at that flat risk (linear in R -- no compounding)
    live_return_pct: float = 0.0  # total return over the window at that flat risk
    live_return_eur: float = 0.0  # EUR per year on the start balance
    live_max_dd_pct: float = 0.0  # worst peak-to-trough of the flat-sized equity (floating-incl.)
    live_fits_limit: bool = True  # does the live risk sit within the drawdown ceiling?


def score(
    trades: pd.DataFrame,
    daily_close: dict[str, pd.Series],
    *,
    daily_high: dict[str, pd.Series] | None = None,
    daily_low: dict[str, pd.Series] | None = None,
    start_balance: float = 200_000.0,
    limit_frac: float = 0.06,
    day_loss_frac: float = 0.03,
    throttle_base_mults: tuple[float, ...] = _DEFAULT_MULTS,
    throttle_floor: float = 0.15,
    live_risk_pct: float = 0.15,
    base_risk_frac: float = 0.01,
) -> PortfolioResult:
    """Score a trade stream (columns: market, ts_opened, ts_closed, pnl_base, entry, exit).

    Respects both the trailing max drawdown (``limit_frac``) and the daily loss limit
    (``day_loss_frac``, TTP's 3%). When ``daily_high``/``daily_low`` are given, the drawdown
    breach test marks open positions at each day's *adverse* extreme (intraday-worst equity,
    H1) instead of the close -- the honest, stricter feasibility. Without them it falls back to
    the close-based equity (EOD resolution, which can miss an intraday breach).
    """
    t = trades.copy()
    t["od"] = [to_day(x) for x in t["ts_opened"]]
    t["cd"] = [to_day(x) for x in t["ts_closed"]]
    d0, d1 = int(t["od"].min()), int(t["cd"].max())
    prices = {m: align_prices(daily_close[m], d0, d1) for m in t["market"].unique()}

    realized, unrealized = base_curves(t, prices, d0, d1)
    equity = realized + unrealized

    if daily_high is not None and daily_low is not None:
        highs = {m: align_prices(daily_high[m], d0, d1) for m in t["market"].unique()}
        lows = {m: align_prices(daily_low[m], d0, d1) for m in t["market"].unique()}
        equity_breach = realized + worst_unrealized(t, highs, lows, d0, d1)  # intraday-worst (H1)
    else:
        equity_breach = equity  # EOD close-based fallback

    flat_m = max_flat_risk(
        realized, equity_breach, start_balance, limit_frac, day_loss_frac=day_loss_frac
    )
    flat_ret = flat_m * float(realized[-1]) / start_balance

    best_base, best_ret = 0.0, 0.0
    for mult in throttle_base_mults:
        base = flat_m * mult  # base risk at the highs, tapered toward the wall
        rb, eq = throttle_curves(
            t, prices, d0, d1, start_balance, limit_frac, throttle(base, throttle_floor)
        )
        if evaluate(eq, rb, start_balance, limit_frac).breached or daily_breach(eq, day_loss_frac):
            continue  # breaches the trailing max or the daily loss limit
        ret = (float(rb[-1]) - start_balance) / start_balance
        if ret > best_ret:
            best_ret, best_base = ret, base

    years = (d1 - d0) / 365.25
    gain = (best_ret - flat_ret) / flat_ret if flat_ret > 0 else 0.0

    # -- HONEST flat sizing at the chosen live risk (the planning numbers) --
    # The base curves are at the backtest's base risk (``base_risk_frac``, i.e. multiple 1.0).
    # Trading flat at ``live_risk_pct`` scales every trade's contribution linearly -- so scale the
    # whole PnL curve by (live_risk / base_risk). No compounding: this is what we actually trade.
    scale = (live_risk_pct / 100.0) / base_risk_frac
    live_realized = realized * scale
    live_equity = start_balance + (realized + unrealized) * scale
    live_ret = float(live_realized[-1]) / start_balance
    live_peak = pd.Series(live_equity).cummax().to_numpy()
    live_dd = float(((live_equity - live_peak) / live_peak).min())
    # The live risk fits the limit iff it is at or below the max-feasible flat risk (ceiling).
    live_fits = (live_risk_pct / 100.0) <= flat_m * base_risk_frac

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
        live_risk_pct=live_risk_pct,
        live_ann_pct=round(live_ret / years * 100, 1) if years > 0 else 0.0,
        live_return_pct=round(live_ret * 100, 1),
        live_return_eur=round(float(live_realized[-1]) / years, 0) if years > 0 else 0.0,
        live_max_dd_pct=round(live_dd * 100, 2),
        live_fits_limit=live_fits,
    )


@dataclass(frozen=True)
class Verdict:
    """Stage 5 accept/reject gate on the holdout portfolio result."""

    passed: bool
    prob_profit: float  # Monte-Carlo probability of profit at the feasible flat risk
    reasons: list[str]  # one PASS/FAIL line per check


def acceptance_verdict(
    result: PortfolioResult,
    trades: pd.DataFrame,
    *,
    start_balance: float = 200_000.0,
    min_trades: int = 30,
    min_prob_profit: float = 0.6,
    n_sims: int = 1000,
    stress_trades: pd.DataFrame | None = None,
    stress_mult: float = 1.5,
    base_risk_frac: float = 0.01,
) -> Verdict:
    """Stage 5 gate: is the holdout result tradeable? (F3)

    Bootstraps the holdout trades (at the feasible flat risk) for a probability of profit,
    then requires: enough trades, a flat risk that fits the drawdown limit, a positive
    holdout return, and a Monte-Carlo profit probability above ``min_prob_profit``.

    If ``stress_trades`` (ideally the FULL-history stream, with an ``r`` column) is given, also
    require that the feasible flat risk survives a ``stress_mult`` x worse-than-history single-day
    gap -- so a risk fit to a benign holdout is rejected if a worse crisis would breach the hard
    limit (the tail is what really binds; see :mod:`qplus.backtest.portfolio.stress`).
    """
    # Everything is judged at the LIVE flat risk we actually trade (not the max-feasible ceiling).
    live_scale = (result.live_risk_pct / 100.0) / base_risk_frac
    checks: list[tuple[bool, str]] = [
        (result.n_trades >= min_trades, f"trades {result.n_trades} >= {min_trades}"),
        (result.live_fits_limit, f"live risk {result.live_risk_pct}% within the DD ceiling"),
        (result.live_ann_pct > 0.0, f"holdout return positive ({result.live_ann_pct}%/yr)"),
    ]
    pnls = (trades["pnl_base"].to_numpy() * live_scale).tolist()
    if len(pnls) >= 2:
        paths = monte_carlo_paths(pnls, n_sims=n_sims, start_equity=start_balance)
        prob = float(summarize(paths, start_balance)["prob_profit"])
    else:
        prob = 0.0
    checks.append(
        (prob >= min_prob_profit, f"MC prob of profit {prob:.0%} >= {min_prob_profit:.0%}")
    )
    if stress_trades is not None:
        from qplus.backtest.portfolio.stress import survives

        ok = survives(stress_trades, result.live_risk_pct / 100.0, stress_mult=stress_mult)
        checks.append((ok, f"live risk survives a {stress_mult}x worse-than-history gap"))

    reasons = [f"{'PASS' if ok else 'FAIL'}: {msg}" for ok, msg in checks]
    return Verdict(passed=all(ok for ok, _ in checks), prob_profit=prob, reasons=reasons)
