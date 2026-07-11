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


def test_variation_pbo_dominant_variation_is_not_overfit() -> None:
    from qplus.backtest.edge.characterize import variation_pbo

    # Three variations over two (instrument, train) cells; "good" dominates every cell, so the
    # in-sample-best is always best out-of-sample -> PBO 0.
    good_rows = []
    for inst in ("A", "B"):
        good_rows += [
            {"variation": "good", "instrument": inst, "train_months": 36, "window_oos": [0.02] * 6},
            {"variation": "mid", "instrument": inst, "train_months": 36, "window_oos": [0.005] * 6},
            {"variation": "bad", "instrument": inst, "train_months": 36, "window_oos": [-0.01] * 6},
        ]
    assert variation_pbo(good_rows) == 0.0


def test_variation_pbo_aligns_over_common_cells_when_one_variation_is_short() -> None:
    from qplus.backtest.edge.characterize import variation_pbo

    # "partial" only ran on instrument A; the matrix must fall back to the common cell (A) rather
    # than crash on the ragged shape.
    rows = []
    for inst in ("A", "B"):
        rows += [
            {"variation": "full", "instrument": inst, "train_months": 36, "window_oos": [0.01] * 8},
            {"variation": "other", "instrument": inst, "train_months": 36, "window_oos": [0.0] * 8},
        ]
    rows.append(
        {"variation": "partial", "instrument": "A", "train_months": 36, "window_oos": [0.02] * 8}
    )
    value = variation_pbo(rows)
    assert 0.0 <= value <= 1.0


def test_variation_pbo_nan_with_fewer_than_two_variations() -> None:
    import math

    from qplus.backtest.edge.characterize import variation_pbo

    rows = [{"variation": "only", "instrument": "A", "train_months": 36, "window_oos": [0.01] * 10}]
    assert math.isnan(variation_pbo(rows))
