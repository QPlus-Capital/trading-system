"""Monte-Carlo robustness analysis from a backtest's per-trade PnLs.

Given the realized PnL of each closed trade, we bootstrap many alternative trade
sequences (sampling trades with replacement) and build an equity path for each.
The spread of these paths estimates how much the result depends on the exact order
and selection of trades -- i.e. how robust (or lucky) the backtest was.

These are pure functions (NumPy only); no backtest engine is involved.
"""

from collections.abc import Sequence

import numpy as np


def equity_curve(trade_pnls: Sequence[float], start_equity: float) -> np.ndarray:
    """Return the actual equity curve: start equity then cumulative trade PnL."""
    pnls = np.asarray(trade_pnls, dtype=float)
    return start_equity + np.concatenate([[0.0], np.cumsum(pnls)])


def max_drawdown(equity: np.ndarray) -> float:
    """Return the maximum peak-to-trough drawdown of an equity path (0..1+)."""
    if equity.size == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    return float(np.max((running_max - equity) / running_max))


def monte_carlo_paths(
    trade_pnls: Sequence[float],
    *,
    n_sims: int,
    start_equity: float,
    seed: int = 42,
) -> np.ndarray:
    """Bootstrap ``n_sims`` equity paths by resampling trades with replacement.

    Returns an array of shape ``(n_sims, n_trades + 1)`` (each row starts at
    ``start_equity``). Deterministic for a given ``seed``.
    """
    pnls = np.asarray(trade_pnls, dtype=float)
    n_trades = pnls.size
    rng = np.random.default_rng(seed)
    sampled = rng.choice(pnls, size=(n_sims, n_trades), replace=True)
    cumulative = np.cumsum(sampled, axis=1)
    start_column = np.zeros((n_sims, 1))
    return start_equity + np.concatenate([start_column, cumulative], axis=1)


def summarize(paths: np.ndarray, start_equity: float) -> dict[str, float]:
    """Summarize Monte-Carlo paths: final-equity percentiles, drawdown, hit rate."""
    finals = paths[:, -1]
    drawdowns = np.array([max_drawdown(path) for path in paths])
    return {
        "final_median": float(np.median(finals)),
        "final_p05": float(np.percentile(finals, 5)),
        "final_p95": float(np.percentile(finals, 95)),
        "prob_profit": float(np.mean(finals > start_equity)),
        "max_dd_median": float(np.median(drawdowns)),
        "max_dd_p95": float(np.percentile(drawdowns, 95)),
    }
