"""Selection-bias / overfitting statistics (Bailey & Lopez de Prado).

When many parameter combinations are tried, the best one looks good partly by luck.
These metrics correct for that:

- **Probabilistic Sharpe Ratio (PSR)**: probability the true Sharpe exceeds a
  benchmark, given the sample length and the returns' skew/kurtosis.
- **Deflated Sharpe Ratio (DSR)**: PSR against the *expected maximum* Sharpe that N
  zero-skill trials would produce -- i.e. corrected for multiple testing.
- **Probability of Backtest Overfitting (PBO)** via combinatorially symmetric
  cross-validation (CSCV): how often the in-sample-best trial is below the median
  out-of-sample.

Pure NumPy + the standard library (``statistics.NormalDist`` for the normal CDF /
its inverse); no SciPy dependency.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from statistics import NormalDist
from typing import Any

import numpy as np

from research.engine.grid import expand_grid

_NORMAL = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: Sequence[float]) -> float:
    """Per-observation (non-annualized) Sharpe ratio of a returns series."""
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    std = float(arr.std(ddof=1))
    return float(arr.mean()) / std if std > 0 else 0.0


def probabilistic_sharpe_ratio(returns: Sequence[float], sr_benchmark: float = 0.0) -> float:
    """Probability that the true (per-observation) Sharpe exceeds ``sr_benchmark``."""
    arr = np.asarray(returns, dtype=float)
    n = arr.size
    if n < 3:
        return float("nan")
    std = float(arr.std(ddof=1))
    if std == 0:
        return float("nan")
    sr = float(arr.mean()) / std
    z = (arr - arr.mean()) / std
    skew = float((z**3).mean())
    kurtosis = float((z**4).mean())  # non-excess kurtosis (3 for normal)
    denom = math.sqrt(1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr**2)
    stat = (sr - sr_benchmark) * math.sqrt(n - 1) / denom
    return _NORMAL.cdf(stat)


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected maximum Sharpe of ``n_trials`` independent zero-skill strategies."""
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    std = math.sqrt(sharpe_variance)
    a = _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
    b = _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return std * ((1.0 - _EULER_MASCHERONI) * a + _EULER_MASCHERONI * b)


def deflated_sharpe_ratio(
    returns: Sequence[float],
    n_trials: int,
    sharpe_variance: float,
) -> float:
    """PSR against the expected-max Sharpe from ``n_trials`` -- corrected for selection."""
    benchmark = expected_max_sharpe(n_trials, sharpe_variance)
    return probabilistic_sharpe_ratio(returns, sr_benchmark=benchmark)


def pbo(performance_matrix: Sequence[Sequence[float]], n_splits: int = 10) -> float:
    """Probability of backtest overfitting via CSCV.

    Parameters
    ----------
    performance_matrix : array-like, shape (n_time_slices, n_trials)
        Performance (e.g. per-slice return) of each trial in each time slice.
    n_splits : int
        Number of (even) contiguous time groups to combine into IS/OOS halves.

    Returns
    -------
    float
        Fraction of IS/OOS splits where the in-sample-best trial lands below the
        out-of-sample median (0 = never overfit, ~0.5 = no better than chance).
    """
    matrix = np.asarray(performance_matrix, dtype=float)
    n_time, n_trials = matrix.shape
    if n_trials < 2 or n_splits < 2 or n_splits % 2 != 0 or n_time < n_splits:
        raise ValueError("need >=2 trials and an even n_splits <= number of time slices")

    groups = np.array_split(np.arange(n_time), n_splits)
    overfit = 0
    total = 0
    for is_groups in combinations(range(n_splits), n_splits // 2):
        is_rows = np.concatenate([groups[g] for g in is_groups])
        oos_rows = np.concatenate([groups[g] for g in range(n_splits) if g not in is_groups])
        is_perf = matrix[is_rows].sum(axis=0)
        oos_perf = matrix[oos_rows].sum(axis=0)
        best = int(np.argmax(is_perf))
        # Relative OOS rank of the IS-best trial: 1.0 = best OOS, 0.0 = worst.
        rank = int((oos_perf < oos_perf[best]).sum())
        relative_rank = rank / (n_trials - 1)
        if relative_rank < 0.5:
            overfit += 1
        total += 1
    return overfit / total


# --- Multiple-testing budget: how many configurations were effectively searched? ---
# The deflated Sharpe ratio only corrects for selection luck if told the TRUE trial count.
# The study searches variations x train-lengths x grid-combos; the product is the honest
# (conservative) budget -- correlated trials mean the real independent count is lower, which
# only makes the deflation bar safer.


@dataclass(frozen=True)
class TrialBudget:
    """The effective number of configurations searched, broken down by dimension."""

    variations: int
    train_lengths: int
    param_combos: int
    manual: int = 0  # hand-made choices (universe, stop re-fit, risk policy) -- see MANUAL_TRIALS

    @property
    def total(self) -> int:
        """Effective trial count: the searched grid PLUS the decisions made by hand.

        The grid dimensions multiply (every combination was really evaluated); manual choices
        add, because each was one additional look at the data by a human rather than another
        axis of the sweep. Leaving them out understates the search and deflates too little (#13).
        """
        return self.variations * self.train_lengths * self.param_combos + self.manual

    def summary(self) -> str:
        """One-line human breakdown for the report."""
        manual_txt = f" + {self.manual} manual" if self.manual else ""
        return (
            f"{self.total} effective trials = "
            f"{self.variations} variations x {self.train_lengths} train-lengths "
            f"x {self.param_combos} param-combos{manual_txt}"
        )


def study_trial_budget(cfg: Any) -> TrialBudget:
    """Derive the multiple-testing budget from a study config's search dimensions."""
    variations = len(getattr(cfg, "VARIATIONS", {"baseline": {}}))
    train_cfg = getattr(cfg, "TRAIN_MONTHS", 24)
    train_lengths = len(train_cfg) if isinstance(train_cfg, list | tuple) else 1
    param_combos = len(expand_grid(getattr(cfg, "PARAM_GRID", {})))
    manual = len(getattr(cfg, "MANUAL_TRIALS", ()))
    return TrialBudget(
        max(variations, 1), max(train_lengths, 1), max(param_combos, 1), manual
    )
