"""Walk-forward window scheme.

Walk-forward validation splits history into rolling (train, test) windows: parameters
are optimized on each *train* window and then evaluated on the immediately following
*test* window, which the optimizer never saw. Stitching the test windows together
gives an out-of-sample track record -- the honest estimate of future performance.

This module only computes the window boundaries; running and scoring them lives in
the walk-forward runner (built on top of this).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from qplus.backtest.foundation.montecarlo import equity_curve, max_drawdown


@dataclass(frozen=True)
class WalkForwardWindow:
    """One rolling window: optimize on [train_start, train_end), test on [test_start, test_end)."""

    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    @property
    def label(self) -> str:
        """Short human label for the out-of-sample period, e.g. ``2013-02..2013-08``."""
        return f"{self.test_start:%Y-%m}..{self.test_end:%Y-%m}"


def walk_forward_windows(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    train_months: int,
    test_months: int,
    step_months: int,
    embargo_days: int = 0,
) -> list[WalkForwardWindow]:
    """Return rolling walk-forward windows spanning ``start``..``end``.

    Each window trains on ``train_months`` and tests on the following ``test_months``;
    the window origin advances by ``step_months`` (non-anchored: the train length is
    constant). Windows whose test period would run past ``end`` are dropped.

    ``embargo_days`` inserts a gap between ``train_end`` and ``test_start`` (F5): it purges
    the boundary so trailing-window indicators / positions straddling the split cannot leak
    train information into the test (Lopez de Prado, purged/embargoed CV).

    Parameters
    ----------
    start, end : str or pd.Timestamp
        The overall data span.
    train_months, test_months, step_months : int
        Window sizing, in whole months. All must be positive.
    embargo_days : int
        Gap in days between train and test (>= 0).

    Returns
    -------
    list[WalkForwardWindow]
    """
    if train_months <= 0 or test_months <= 0 or step_months <= 0:
        raise ValueError("train_months, test_months and step_months must be positive")
    if embargo_days < 0:
        raise ValueError("embargo_days must be >= 0")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    windows: list[WalkForwardWindow] = []
    train_start = start_ts
    while True:
        train_end = train_start + pd.DateOffset(months=train_months)
        test_start = train_end + pd.Timedelta(days=embargo_days)
        test_end = test_start + pd.DateOffset(months=test_months)
        if test_end > end_ts:
            break
        windows.append(WalkForwardWindow(train_start, train_end, test_start, test_end))
        train_start = train_start + pd.DateOffset(months=step_months)
    return windows


def split_windows(
    windows: Sequence[WalkForwardWindow], data_end: pd.Timestamp, holdout_months: int
) -> tuple[list[WalkForwardWindow], list[WalkForwardWindow]]:
    """Split windows into (selection, holdout) at ``data_end - holdout_months``.

    Selection windows lie fully before the cutoff (``test_end <= cutoff``); holdout windows
    test on/after it (``test_start >= cutoff``). With ``holdout_months <= 0`` everything is
    selection and the holdout is empty. Reserving a holdout that no stage ever uses for
    selection is what lets the final chosen config be scored once on genuinely untouched
    data -- the honest guard against selecting on out-of-sample results.
    """
    if holdout_months <= 0:
        return list(windows), []
    cutoff = data_end - pd.DateOffset(months=holdout_months)
    selection = [w for w in windows if w.test_end <= cutoff]
    holdout = [w for w in windows if w.test_start >= cutoff]
    return selection, holdout


def calmar_score(
    trade_pnls: Sequence[float],
    start_equity: float,
    *,
    min_trades: int = 10,
) -> float:
    """Drawdown-adjusted score: total return divided by max drawdown (Calmar-style).

    Returns ``-inf`` if there are fewer than ``min_trades`` trades, so thin, unreliable
    parameter sets are never selected.
    """
    if len(trade_pnls) < min_trades:
        return float("-inf")
    equity = equity_curve(trade_pnls, start_equity)
    total_return = (float(equity[-1]) - start_equity) / start_equity
    return total_return / max(max_drawdown(equity), 1e-6)


@dataclass(frozen=True)
class WalkForwardResult:
    """Outcome of one walk-forward window: chosen params and their OOS performance."""

    window: str
    best_params: dict[str, Any]
    is_return: float  # in-sample return of the chosen params on the train window
    oos_return: float  # out-of-sample return on the test window
    oos_trades: int
    oos_max_dd: float
    oos_returns: list[float]  # per-trade OOS returns (pnl / window start equity)


# Optimize on a train window -> (best params, that set's in-sample return).
Optimize = Callable[[pd.Timestamp, pd.Timestamp], tuple[dict[str, Any], float]]
# Evaluate params on a test window -> (out-of-sample trade PnLs, starting equity).
EvaluateOOS = Callable[[dict[str, Any], pd.Timestamp, pd.Timestamp], tuple[list[float], float]]


def run_walk_forward(
    windows: Sequence[WalkForwardWindow],
    optimize: Optimize,
    evaluate: EvaluateOOS,
) -> list[WalkForwardResult]:
    """Optimize per train window and score the chosen params on the next test window."""
    results: list[WalkForwardResult] = []
    for window in windows:
        best_params, is_return = optimize(window.train_start, window.train_end)
        pnls, start_equity = evaluate(best_params, window.test_start, window.test_end)
        equity = equity_curve(pnls, start_equity)
        oos_return = (float(equity[-1]) - start_equity) / start_equity
        results.append(
            WalkForwardResult(
                window=window.label,
                best_params=best_params,
                is_return=is_return,
                oos_return=oos_return,
                oos_trades=len(pnls),
                oos_max_dd=max_drawdown(equity),
                oos_returns=[p / start_equity for p in pnls] if start_equity else [],
            ),
        )
    return results


def walk_forward_efficiency(results: Sequence[WalkForwardResult]) -> float:
    """Walk-forward efficiency: mean out-of-sample return / mean in-sample return.

    Note this raw ratio is biased low whenever the train window is longer than the test
    window (the in-sample return spans more months): use :func:`normalized_wfe` to judge
    generalization. Values near/above ~0.5 (normalized) suggest the edge generalizes.
    """
    if not results:
        return float("nan")
    is_mean = sum(r.is_return for r in results) / len(results)
    oos_mean = sum(r.oos_return for r in results) / len(results)
    return oos_mean / is_mean if is_mean != 0 else float("nan")


def normalized_wfe(
    results: Sequence[WalkForwardResult], train_months: int, test_months: int
) -> float:
    """Length-normalized walk-forward efficiency (per-month), unbiased by window lengths.

    The raw WFE compares an out-of-sample return over ``test_months`` against an in-sample
    return over ``train_months``; when train is longer the raw ratio looks too low purely
    because the in-sample period is longer. Scaling by ``train_months / test_months``
    removes that bias, giving the true per-month generalization ratio. ~0.5+ is healthy.

    This is exact for a *per-month total-return rate* (F8): it equals ``mean(oos/test) /
    mean(is/train)`` since the window lengths are constant -- it does not assume returns
    compound linearly, only that a per-month return rate is a sensible efficiency unit.
    """
    if test_months <= 0:
        raise ValueError("test_months must be positive")
    return walk_forward_efficiency(results) * train_months / test_months
