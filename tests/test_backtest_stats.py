"""Tests for the shared portfolio statistics (R-multiples + edge metrics)."""

import numpy as np
from research.portfolio.stats import edge_stats, r_multiples


def test_r_multiples_recover_size_invariant_return() -> None:
    # First trade risks 1% of 200k = 2000; a +2000 PnL is exactly +1R.
    rs = r_multiples([2000.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9


def test_r_multiples_walk_the_equity_forward() -> None:
    # After a +2000 win, equity is 202k -> next trade risks 2020; a -2020 loss is -1R.
    rs = r_multiples([2000.0, -2020.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9
    assert abs(rs[1] + 1.0) < 1e-9


def test_edge_stats_count_metrics() -> None:
    # 4 trades: +100, -50, +200, -50 -> 2 wins / 2 losses.
    s = edge_stats(np.array([100.0, -50.0, 200.0, -50.0]))
    assert s["trades"] == 4.0
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert abs(s["payoff"] - 3.0) < 1e-9  # avg win 150 / avg loss 50
    assert abs(s["profit_factor"] - 3.0) < 1e-9  # 300 won / 100 lost
    assert abs(s["expectancy"] - 50.0) < 1e-9  # (100-50+200-50)/4
