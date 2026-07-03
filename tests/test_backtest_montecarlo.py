"""Tests for the Monte-Carlo helpers (pure NumPy, no backtests)."""

import numpy as np

from qplus.backtest.foundation.montecarlo import (
    equity_curve,
    max_drawdown,
    monte_carlo_paths,
    summarize,
)


def test_equity_curve_is_cumulative() -> None:
    curve = equity_curve([10.0, -5.0, 20.0], start_equity=100.0)
    assert curve.tolist() == [100.0, 110.0, 105.0, 125.0]


def test_max_drawdown_peak_to_trough() -> None:
    equity = np.array([100.0, 120.0, 90.0, 130.0])
    assert max_drawdown(equity) == (120.0 - 90.0) / 120.0


def test_monte_carlo_paths_shape_and_determinism() -> None:
    pnls = [5.0, -3.0, 8.0, -2.0]
    a = monte_carlo_paths(pnls, n_sims=50, start_equity=1000.0, seed=7)
    b = monte_carlo_paths(pnls, n_sims=50, start_equity=1000.0, seed=7)
    assert a.shape == (50, len(pnls) + 1)
    assert np.array_equal(a, b)  # deterministic for a fixed seed
    assert np.all(a[:, 0] == 1000.0)  # every path starts at the start equity


def test_summarize_keys_and_ranges() -> None:
    paths = monte_carlo_paths([5.0, -3.0, 8.0], n_sims=100, start_equity=1000.0)
    stats = summarize(paths, start_equity=1000.0)
    assert set(stats) == {
        "final_median",
        "final_p05",
        "final_p95",
        "prob_profit",
        "max_dd_median",
        "max_dd_p95",
    }
    assert 0.0 <= stats["prob_profit"] <= 1.0
    assert stats["final_p05"] <= stats["final_median"] <= stats["final_p95"]
