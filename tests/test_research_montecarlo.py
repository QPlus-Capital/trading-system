"""Tests for the Monte-Carlo helpers (pure NumPy, no backtests)."""

import numpy as np
from research.engine.montecarlo import (
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


def test_day_blocks_keep_correlated_losses_together() -> None:
    """#16: four markets that lose together on a gap day must stay together when resampled.

    Stream: many small winners on ordinary days, plus ONE day where four correlated positions
    all lose hard. IID resampling scatters those four losses across the path so they rarely
    compound; day-block resampling keeps them in one day, which is what the account actually
    experiences -- so the block bootstrap must report the deeper drawdown.
    """
    pnls = [10.0] * 80 + [-200.0] * 4  # 80 ordinary winners, then one 4-position gap day
    days = list(range(80)) + [999] * 4  # the four losers all close on the SAME day

    iid = monte_carlo_paths(pnls, n_sims=400, start_equity=10_000.0, seed=3)
    blocked = monte_carlo_paths(
        pnls, n_sims=400, start_equity=10_000.0, seed=3, days=days, block_days=1
    )
    iid_dd = float(np.median([max_drawdown(p) for p in iid]))
    blocked_dd = float(np.median([max_drawdown(p) for p in blocked]))
    assert blocked_dd > iid_dd  # clustering deepens the drawdown -> IID was optimistic


def test_block_bootstrap_keeps_shape_and_determinism() -> None:
    pnls = [1.0, -2.0, 3.0, -1.0, 2.0]
    days = [0, 0, 1, 2, 2]
    a = monte_carlo_paths(pnls, n_sims=20, start_equity=500.0, seed=11, days=days)
    b = monte_carlo_paths(pnls, n_sims=20, start_equity=500.0, seed=11, days=days)
    assert a.shape == (20, len(pnls) + 1)
    assert np.array_equal(a, b)
    assert np.all(a[:, 0] == 500.0)


def test_a_correlated_day_bundle_is_never_split_by_the_path_length() -> None:
    """Codex round-5 P2: truncating the concatenated blocks at n_trades could cut through the
    very gap-day bundle the block bootstrap exists to preserve -- e.g. keeping 2 of 4 correlated
    losses, understating drawdown in exactly the macro-gap scenario being tested."""
    pnls = [10.0] * 50 + [-200.0] * 4  # one 4-position correlated gap day
    days = list(range(50)) + [99] * 4
    paths = monte_carlo_paths(
        pnls, n_sims=300, start_equity=10_000.0, seed=5, days=days, block_days=1
    )
    steps = np.diff(paths, axis=1)
    losses_per_path = np.count_nonzero(steps == -200.0, axis=1)
    assert (losses_per_path % 4 == 0).all()  # the gap day appears whole or not at all
