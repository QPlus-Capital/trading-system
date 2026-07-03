"""Tests for the overfitting statistics (PSR, DSR, PBO)."""

import numpy as np

from qplus.backtest.foundation.overfitting import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pbo,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)


def test_sharpe_ratio_basic() -> None:
    assert sharpe_ratio([1.0, 1.0, 1.0]) == 0.0  # no variance
    assert sharpe_ratio([1.0]) == 0.0  # too short


def test_psr_high_for_consistent_positive_returns() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.01, 0.01, size=500).tolist()  # positive mean, low vol
    psr = probabilistic_sharpe_ratio(returns, sr_benchmark=0.0)
    assert 0.9 < psr <= 1.0


def test_expected_max_sharpe_grows_with_trials() -> None:
    low = expected_max_sharpe(5, sharpe_variance=0.25)
    high = expected_max_sharpe(500, sharpe_variance=0.25)
    assert 0.0 < low < high  # more trials -> higher expected max by luck


def test_deflated_sharpe_below_undeflated() -> None:
    rng = np.random.default_rng(1)
    returns = rng.normal(0.01, 0.01, size=500).tolist()
    raw = probabilistic_sharpe_ratio(returns, sr_benchmark=0.0)
    deflated = deflated_sharpe_ratio(returns, n_trials=100, sharpe_variance=0.25)
    assert deflated < raw  # correcting for 100 trials lowers confidence


def test_pbo_zero_for_a_dominant_trial() -> None:
    # Trial 0 is best in every time slice -> IS-best is always best OOS -> no overfit.
    n_time, n_trials = 20, 5
    matrix = np.tile(np.arange(n_trials, dtype=float), (n_time, 1))  # col j == j everywhere
    assert pbo(matrix.tolist(), n_splits=10) == 0.0


def test_pbo_around_half_for_noise() -> None:
    rng = np.random.default_rng(2)
    matrix = rng.normal(size=(40, 8)).tolist()  # pure noise -> no persistent edge
    value = pbo(matrix, n_splits=10)
    assert 0.2 < value < 0.8
